"""Tests for the protocol, the learner, and the differential analysis."""

from __future__ import annotations

import unittest

from protocol_diff.bench import CORE_ALPHABET
from protocol_diff.diff import distinguishing_sequence, transcript
from protocol_diff.learner import learn
from protocol_diff.protocol import (
    ANON,
    AUTHED,
    CLOSED,
    NEW,
    VARIANTS,
    Mealy,
    SUT,
    reference,
)


class TestProtocol(unittest.TestCase):
    def setUp(self):
        self.ref = reference()

    def test_initial_state_is_new(self):
        self.assertEqual(self.ref.init, NEW)

    def test_helo_moves_to_anon(self):
        self.assertEqual(self.ref.step(NEW, "HELO"), ("220_READY", ANON))

    def test_private_data_denied_when_anonymous(self):
        self.assertEqual(self.ref.step(ANON, "GET_PRIV"), ("530_DENY", ANON))

    def test_authentication_then_private_access(self):
        self.assertEqual(self.ref.run(("HELO", "AUTH_GOOD"))[1], AUTHED)
        self.assertEqual(self.ref.run(("HELO", "AUTH_GOOD", "GET_PRIV"))[0][-1], "150_DATA")

    def test_admin_requires_second_factor(self):
        self.assertEqual(self.ref.run(("HELO", "AUTH_GOOD", "ADMIN"))[0][-1], "331_CHALLENGE")

    def test_closed_is_absorbing(self):
        for symbol in self.ref.alphabet:
            self.assertEqual(self.ref.step(CLOSED, symbol)[1], CLOSED)

    def test_incomplete_table_rejected(self):
        with self.assertRaises(ValueError):
            Mealy("broken", ("a",), "a", {("a", "HELO"): ("220_READY", "a")}, ("HELO", "PING"))


class TestSUT(unittest.TestCase):
    def test_query_resets_state(self):
        sut = SUT(reference())
        first = sut.query(("HELO", "AUTH_GOOD", "GET_PRIV"))
        second = sut.query(("GET_PRIV",))
        self.assertEqual(first[-1], "150_DATA")
        self.assertEqual(second[-1], "530_DENY")

    def test_query_counter(self):
        sut = SUT(reference())
        self.assertEqual(sut.queries, 0)
        sut.query(("HELO",))
        self.assertEqual(sut.queries, 1)
        self.assertEqual(sut.steps, 1)


class TestLearner(unittest.TestCase):
    def test_recovers_reference_state_count(self):
        model, stats = learn(reference())
        self.assertEqual(model.state_count(), 6)
        self.assertLess(stats.table_queries, 5000)

    def test_learned_model_matches_on_random_walk(self):
        model, _ = learn(reference())
        seq = ("HELO", "AUTH_GOOD", "ADMIN", "AUTH_GOOD", "GET_PRIV", "RESET", "GET_PUB")
        self.assertEqual(model.run(seq)[0], reference().run(seq)[0])

    def test_learns_latent_state_variant(self):
        model, _ = learn(VARIANTS["clearance_persist"]())
        self.assertEqual(model.state_count(), 7)

    def test_core_alphabet_collapses_admin_state(self):
        model, _ = learn(reference(), CORE_ALPHABET)
        self.assertLess(model.state_count(), 6)


class TestDiff(unittest.TestCase):
    def test_self_equivalence(self):
        self.assertIsNone(distinguishing_sequence(reference(), reference()))

    def test_renamed_machine_is_equivalent(self):
        ref = reference()
        renaming = {state: f"s_{state}" for state in ref.states}
        delta = {
            (renaming[s], a): (out, renaming[next_state])
            for (s, a), (out, next_state) in ref.delta.items()
        }
        clone = Mealy("clone", tuple(renaming.values()), renaming[ref.init], delta)
        self.assertIsNone(distinguishing_sequence(ref, clone))

    def test_detects_every_variant(self):
        ref_model, _ = learn(reference())
        for name, factory in VARIANTS.items():
            if name == "reference":
                continue
            with self.subTest(variant=name):
                model, _ = learn(factory())
                witness = distinguishing_sequence(ref_model, model)
                self.assertIsNotNone(witness, name)
                out_ref, _ = reference().run(witness)
                out_var, _ = factory().run(witness)
                self.assertNotEqual(out_ref, out_var, "witness must be verified on ground truth")

    def test_shortest_witness_for_auth_bypass(self):
        ref_model, _ = learn(reference())
        model, _ = learn(VARIANTS["auth_inverted"]())
        self.assertEqual(distinguishing_sequence(ref_model, model), ("HELO", "AUTH_BAD"))

    def test_transcript(self):
        rows = transcript(reference(), ("HELO", "AUTH_BAD"))
        self.assertEqual(rows[0][1], "220_READY")
        self.assertEqual(rows[1][1], "530_DENY")


if __name__ == "__main__":
    unittest.main()


class TestReproducibility(unittest.TestCase):
    """The committed table has to be byte-stable, or it cannot be diffed."""

    def test_results_json_excludes_wall_clock(self):
        import json
        import tempfile
        from pathlib import Path

        from protocol_diff.bench import run_bench

        outputs = []
        for _ in range(2):
            with tempfile.TemporaryDirectory() as tmp:
                path = Path(tmp) / "results.json"
                run_bench(out_path=path, alphabets=("core",))
                outputs.append(path.read_bytes())
                timing = json.loads((Path(tmp) / "timing.json").read_text(encoding="utf-8"))
                self.assertIn("elapsed_s", timing["summary"])

        self.assertEqual(outputs[0], outputs[1])
        payload = json.loads(outputs[0])
        self.assertNotIn("elapsed_s", payload["summary"])
        for block in payload["variants"].values():
            for row in block["rows"].values():
                self.assertNotIn("seconds", row)
