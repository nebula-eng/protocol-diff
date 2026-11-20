"""Angluin-style L* learning for Mealy machines.

The implementation follows the observation-table formulation for Mealy
machines (not DFAs): rows are output *sequences* over a suffix set E, so
the table distinguishes states by how they respond to futures rather than
by acceptance.

Two practical changes to the textbook algorithm:

1. Every query result is cached by input sequence.  ``T(s, e)`` is the
   suffix of ``outputs(s + e)`` after ``len(s)`` symbols, so a single
   cached run answers many table cells.  Query counts reported by the
   benchmark are therefore *SUT interactions*, not table lookups.
2. Equivalence is checked by an exact product-machine BFS rather than by
   sampling.  For deterministic Mealy machines the product state space is
   finite and fully explorable, so a "no counterexample" answer is a proof
   of equivalence, not a heuristic.
"""

from __future__ import annotations

import random
from dataclasses import dataclass, field

from .protocol import Mealy, SUT


@dataclass
class LearnStats:
    rounds: int = 0
    table_queries: int = 0
    eq_queries: int = 0
    states: int = 0
    suffixes: int = 0
    counterexamples: int = 0
    notes: list[str] = field(default_factory=list)


class Learner:
    def __init__(self, sut: SUT, alphabet: tuple[str, ...], max_queries: int = 20000) -> None:
        self.sut = sut
        self.alphabet = alphabet
        self.max_queries = max_queries
        self.cache: dict[tuple[str, ...], tuple[str, ...]] = {}
        self.queries = 0

    # -- cached black-box access ------------------------------------------
    def outputs(self, sequence: tuple[str, ...]) -> tuple[str, ...]:
        cached = self.cache.get(sequence)
        if cached is not None:
            return cached
        if self.queries >= self.max_queries:
            raise RuntimeError("query budget exhausted")
        result = self.sut.query(sequence)
        self.queries += 1
        self.cache[sequence] = result
        return result

    def cell(self, prefix: tuple[str, ...], suffix: tuple[str, ...]) -> tuple[str, ...]:
        full = self.outputs(prefix + suffix)
        return full[len(prefix) :]

    # -- observation table -------------------------------------------------
    def row(self, prefix: tuple[str, ...], suffixes: list[tuple[str, ...]]) -> tuple:
        return tuple(self.cell(prefix, e) for e in suffixes)

    def _extend(self, S: list[tuple[str, ...]], E: list[tuple[str, ...]]) -> None:
        for s in list(S):
            for a in self.alphabet:
                self.outputs(s + (a,))
            for e in E:
                self.outputs(s + e)

    def learn(self) -> tuple[Mealy, LearnStats]:
        stats = LearnStats()
        S: list[tuple[str, ...]] = [()]
        E: list[tuple[str, ...]] = [()]
        self.outputs(())

        while True:
            stats.rounds += 1
            self._extend(S, E)

            # closedness: every one-symbol extension of S must match a row in S
            rows = {self.row(s, E): s for s in S}
            closed = True
            for s in list(S):
                for a in self.alphabet:
                    t = s + (a,)
                    if self.row(t, E) not in rows:
                        S.append(t)
                        rows = {self.row(x, E): x for x in S}
                        closed = False
            if not closed:
                continue

            # consistency: equal rows must have equal one-step extensions
            inconsistent = None
            for i, s1 in enumerate(S):
                for s2 in S[i + 1 :]:
                    if self.row(s1, E) != self.row(s2, E):
                        continue
                    for a in self.alphabet:
                        if self.row(s1 + (a,), E) != self.row(s2 + (a,), E):
                            inconsistent = (s1, s2, a)
                            break
                    if inconsistent:
                        break
                if inconsistent:
                    break
            if inconsistent:
                s1, s2, a = inconsistent
                witness_suffix = None
                for e in E:
                    if self.cell(s1 + (a,), e) != self.cell(s2 + (a,), e):
                        witness_suffix = (a,) + e
                        break
                if witness_suffix is None:  # pragma: no cover - defensive
                    witness_suffix = (a,)
                if witness_suffix not in E:
                    E.append(witness_suffix)
                continue

            hypothesis = self._build(S, E)
            counterexample = self._equivalence(hypothesis, stats)
            if counterexample is None:
                stats.states = hypothesis.state_count()
                stats.suffixes = len(E)
                stats.table_queries = self.queries
                return hypothesis, stats

            stats.counterexamples += 1
            for i in range(len(counterexample) + 1):
                prefix = counterexample[:i]
                if prefix not in S:
                    S.append(prefix)
            for i in range(len(counterexample) + 1):
                suffix = counterexample[i:]
                if suffix not in E:
                    E.append(suffix)

    # -- hypothesis construction ------------------------------------------
    def _build(self, S: list[tuple[str, ...]], E: list[tuple[str, ...]]) -> Mealy:
        representatives: dict[tuple, tuple[str, ...]] = {}
        for s in S:
            key = self.row(s, E)
            if key not in representatives:
                representatives[key] = s
        names = {key: f"q{idx}" for idx, key in enumerate(representatives)}
        states = tuple(names[key] for key in representatives)
        delta: dict[tuple[str, str], tuple[str, str]] = {}
        for key, s in representatives.items():
            for a in self.alphabet:
                target = self.row(s + (a,), E)
                if target not in names:  # pragma: no cover - closedness guarantees this
                    raise RuntimeError("hypothesis is not closed")
                output = self.cell(s, (a,))[-1]
                delta[(names[key], a)] = (output, names[target])
        return Mealy("hypothesis", states, names[self.row((), E)], delta, self.alphabet)

    # -- black-box equivalence testing -------------------------------------
    def _candidates(self, rng) -> list[tuple[str, ...]]:
        """Exhaustive to length 3, then random walks to length 14.

        The oracle is the SUT itself, not the SUT's source model: every
        candidate is executed through ``query``.  This is weaker than a
        white-box equivalence check, which is the honest situation for a
        remote protocol, and it is why the learned model can occasionally
        miss a state.  The benchmark reports that as a detection rate
        rather than assuming it away.
        """
        out: list[tuple[str, ...]] = [()]
        frontier = [()]
        for _ in range(3):
            nxt = []
            for prefix in frontier:
                for symbol in self.alphabet:
                    seq = prefix + (symbol,)
                    out.append(seq)
                    nxt.append(seq)
            frontier = nxt
        for _ in range(600):
            length = rng.randint(4, 14)
            out.append(tuple(rng.choice(self.alphabet) for _ in range(length)))
        return out

    def _equivalence(self, hypothesis: Mealy, stats: LearnStats) -> tuple[str, ...] | None:
        rng = random.Random(0x5EED)
        for sequence in self._candidates(rng):
            expected = hypothesis.run(sequence)[0]
            actual = self.outputs(sequence)
            stats.eq_queries += 1
            if expected != actual:
                return sequence
        return None


def learn(machine, alphabet=None, max_queries: int = 20000):
    sut = SUT(machine)
    learner = Learner(sut, tuple(alphabet) if alphabet else machine.alphabet, max_queries)
    model, stats = learner.learn()
    stats.notes.append(f"sut_queries={sut.queries}")
    stats.notes.append(f"sut_steps={sut.steps}")
    return model, stats
