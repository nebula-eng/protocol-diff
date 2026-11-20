"""CLI for the differential automata-learning experiments."""

from __future__ import annotations

import argparse
import json

from .bench import explain, run_bench
from .learner import learn
from .protocol import VARIANTS


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="protocol_diff")
    sub = parser.add_subparsers(dest="command", required=True)

    bench = sub.add_parser("bench", help="learn and diff every variant")
    bench.add_argument("--out", default="results/results.json")

    show = sub.add_parser("explain", help="trace one variant")
    show.add_argument("--variant", required=True, choices=sorted(VARIANTS))
    show.add_argument("--out", default="")

    learn_cmd = sub.add_parser("learn", help="learn one model and print its size")
    learn_cmd.add_argument("--variant", default="reference", choices=sorted(VARIANTS))

    args = parser.parse_args(argv)
    if args.command == "bench":
        payload = run_bench(args.out)
        for alphabet, block in payload["variants"].items():
            print(f"[{alphabet}] reference states={block['reference_states_learned']} "
                  f"queries={block['reference_table_queries']} detections={block['detections']}/5")
            for name, row in block["rows"].items():
                flag = "OK " if row["verified"] else "-- "
                print(f"  {flag}{name:20s} states={row['states_learned']}/{row['states_truth']} "
                      f"witness={row['witness_length']} q={row['membership_queries']}")
        print(json.dumps(payload["summary"], indent=2))
        return 0
    if args.command == "explain":
        payload = explain(args.variant)
        print(json.dumps(payload, indent=2))
        if args.out:
            with open(args.out, "w", encoding="utf-8", newline="\n") as handle:
                json.dump(payload, handle, indent=2)
        return 0
    model, stats = learn(VARIANTS[args.variant]())
    print(f"variant={args.variant} states={model.state_count()} queries={stats.table_queries} "
          f"rounds={stats.rounds} counterexamples={stats.counterexamples}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
