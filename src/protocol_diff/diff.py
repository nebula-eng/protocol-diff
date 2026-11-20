"""Behavioural diffing of two Mealy machines.

Because the machines are deterministic and complete, the product graph is
finite.  A breadth-first traversal over pairs of states therefore computes
the *shortest* input sequence on which the two machines disagree, and if it
finds none, proves equivalence.  No sampling, no depth bound.
"""

from __future__ import annotations

from collections import deque

from .protocol import Mealy


def distinguishing_sequence(a: Mealy, b: Mealy, alphabet=None) -> tuple[str, ...] | None:
    symbols = tuple(alphabet) if alphabet else a.alphabet
    start = (a.init, b.init)
    queue: deque[tuple[tuple[str, str], tuple[str, ...]]] = deque([(start, ())])
    seen = {start}
    while queue:
        (sa, sb), prefix = queue.popleft()
        for symbol in symbols:
            out_a, next_a = a.step(sa, symbol)
            out_b, next_b = b.step(sb, symbol)
            if out_a != out_b:
                return prefix + (symbol,)
            state = (next_a, next_b)
            if state not in seen:
                seen.add(state)
                queue.append((state, prefix + (symbol,)))
    return None


def transcript(machine: Mealy, sequence: tuple[str, ...]) -> list[tuple[str, str, str]]:
    state = machine.init
    rows = []
    for symbol in sequence:
        output, state = machine.step(state, symbol)
        rows.append((symbol, output, state))
    return rows


def diff_summary(a: Mealy, b: Mealy) -> dict:
    witness = distinguishing_sequence(a, b)
    return {
        "equivalent": witness is None,
        "witness": list(witness) if witness else [],
        "witness_length": len(witness) if witness else 0,
        "states_a": a.state_count(),
        "states_b": b.state_count(),
        "alphabet": len(a.alphabet),
        "product_states": a.state_count() * b.state_count(),
    }
