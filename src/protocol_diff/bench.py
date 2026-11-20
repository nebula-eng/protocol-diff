"""Benchmark: learn, diff, verify.

Detection has to survive three sceptical checks before it counts:

1. The variant model must be learned **through the SUT interface only**;
   the learner never sees the transition table.
2. The witness must be produced by diffing two *learned* models, not a
   learned model against ground truth.
3. The witness must be replayed on both implementations and must actually
   produce different outputs there.

A run that fails (3) is reported as a false positive rather than silently
dropped.
"""

from __future__ import annotations

import json
import time
from pathlib import Path

from .diff import distinguishing_sequence, transcript
from .learner import learn
from .protocol import INPUTS, VARIANTS, Mealy

CORE_ALPHABET = ("HELO", "AUTH_GOOD", "AUTH_BAD", "GET_PRIV", "RESET", "BYE")
# Core plus the two symbols that separate the authenticated and admin states.
MID_ALPHABET = CORE_ALPHABET + ("GET_PUB", "ADMIN")
ALPHABETS = {
    "core": CORE_ALPHABET,   # 6 symbols
    "mid": MID_ALPHABET,     # 8 symbols
    "full": INPUTS,          # 10 symbols
}


def _verify(witness, reference: Mealy, variant: Mealy) -> tuple[bool, list[str], list[str]]:
    out_ref, _ = reference.run(witness)
    out_var, _ = variant.run(witness)
    return out_ref != out_var, list(out_ref), list(out_var)


def run_bench(out_path: str | Path | None = None, alphabets: tuple[str, ...] = ("core", "mid", "full")) -> dict:
    started = time.perf_counter()
    payload: dict = {"variants": {}, "config": {"alphabets": list(alphabets)}}
    timing: dict = {"variants": {}, "summary": {}}

    for alphabet_name in alphabets:
        alphabet = ALPHABETS[alphabet_name]
        ref_model, ref_stats = learn(VARIANTS["reference"](), alphabet)
        rows = {}
        timing["variants"][alphabet_name] = {}
        for name, factory in VARIANTS.items():
            if name == "reference":
                continue
            t0 = time.perf_counter()
            model, stats = learn(factory(), alphabet)
            witness = distinguishing_sequence(ref_model, model, alphabet)
            detected = witness is not None
            verified = False
            out_ref: list[str] = []
            out_var: list[str] = []
            if witness:
                verified, out_ref, out_var = _verify(witness, VARIANTS["reference"](), factory())
            rows[name] = {
                "detected": detected,
                "verified": verified,
                "witness": list(witness) if witness else [],
                "witness_length": len(witness) if witness else 0,
                "states_learned": model.state_count(),
                "states_truth": factory().state_count(),
                "membership_queries": stats.table_queries,
                "conformance_checks": stats.eq_queries,
                "counterexamples": stats.counterexamples,
                "sut_steps": int(stats.notes[1].split("=")[1]) if len(stats.notes) > 1 else 0,
                "outputs_reference": out_ref,
                "outputs_variant": out_var,
            }
            # Wall clock goes to `timing.json`, not into the committed table.
            timing["variants"][alphabet_name][name] = round(time.perf_counter() - t0, 4)
        payload["variants"][alphabet_name] = {
            "reference_states_learned": ref_model.state_count(),
            "reference_table_queries": ref_stats.table_queries,
            "reference_conformance_checks": ref_stats.eq_queries,
            "reference_alphabet_size": len(alphabet),
            "detections": sum(1 for r in rows.values() if r["verified"]),
            "rows": rows,
        }

    payload["summary"] = {
        f"{name}_detection_rate": round(block["detections"] / max(len(block["rows"]), 1), 4)
        for name, block in payload["variants"].items()
    }
    timing["summary"]["elapsed_s"] = round(time.perf_counter() - started, 3)
    payload["timing"] = timing

    if out_path is not None:
        path = Path(out_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        # `results.json` holds the deterministic projection only, so a re-run
        # produces a byte-identical file that can be diffed.
        path.write_text(
            json.dumps({k: v for k, v in payload.items() if k != "timing"},
                       indent=2, sort_keys=True),
            encoding="utf-8", newline="\n",
        )
        path.with_name("timing.json").write_text(
            json.dumps(timing, indent=2, sort_keys=True), encoding="utf-8", newline="\n"
        )
    return payload


def explain(variant_name: str) -> dict:
    """Full trace for one variant, used by the CLI and by humans."""
    ref = VARIANTS["reference"]()
    var = VARIANTS[variant_name]()
    ref_model, _ = learn(ref)
    var_model, stats = learn(var)
    witness = distinguishing_sequence(ref_model, var_model)
    if witness is None:
        return {"variant": variant_name, "detected": False, "states": var_model.state_count()}
    return {
        "variant": variant_name,
        "detected": True,
        "witness": list(witness),
        "states_learned": {"reference": ref_model.state_count(), "variant": var_model.state_count()},
        "queries": stats.table_queries,
        "trace_reference": [list(row) for row in transcript(ref, witness)],
        "trace_variant": [list(row) for row in transcript(var, witness)],
    }
