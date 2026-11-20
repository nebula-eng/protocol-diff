# protocol-diff

Differential automata learning for protocol bugs.

[![CI](https://github.com/nebula-eng/protocol-diff/actions/workflows/ci.yml/badge.svg)](https://github.com/nebula-eng/protocol-diff/actions/workflows/ci.yml)
[![License: MIT](https://img.shields.io/badge/license-MIT-blue.svg)](LICENSE)
[![Python](https://img.shields.io/badge/python-3.11%20%7C%203.12%20%7C%203.13-3776ab.svg)](pyproject.toml)

Learning a protocol's state machine from the outside, then proving where two
implementations disagree.

A black-box learner infers a Mealy machine from input/output traces. Two learned
models are compared by exact product-machine traversal, which yields the *shortest*
input sequence on which they diverge. That sequence is then replayed against both
implementations to confirm the divergence is real. No source access, no symbol
tables, no hard-coded test cases.

## Results

Five injected defects, three alphabets, one 10-symbol session protocol:

| defect | states (learned / true) | shortest witness | verified |
|---|---|---:|---|
| stale privilege after RESET | 7 / 7 | `HELO AUTH_GOOD RESET GET_PRIV` | yes |
| admin role survives RESET | 7 / 7 | `HELO AUTH_GOOD ADMIN AUTH_GOOD RESET ADMIN` | yes |
| failed auth treated as success | 6 / 6 | `HELO AUTH_BAD` | yes |
| BYE does not close the session | 6 / 6 | `HELO BYE HELO` | yes |
| closed session serves public data | 6 / 6 | `BYE GET_PUB` | yes |

Alphabet size buys visibility, and the curve is monotone:

| alphabet | symbols | reference states | membership queries | verified detections |
|---|---:|---:|---:|---:|
| core | 6 | 4 | 948 | 3/5 |
| mid | 8 | 6 | 1,301 | 4/5 |
| full | 10 | 6 | 1,861 | 5/5 |

The 6-symbol alphabet collapses the reference model from 6 states to 4 and makes the
`ADMIN` and `GET_PUB` defects structurally invisible. The 8-symbol alphabet recovers
the 6-state reference and finds four defects, but still misses `admin_persist`: the
latent admin state is only reachable through a 6-symbol access path, which the bounded
conformance test does not exercise. The resulting model has 6 states instead of 7, and
the witness it produces is rejected by the replay check (a false positive, reported as
such). Only the 10-symbol alphabet recovers the 7th state and turns that into a
verified witness.

## Why latent state matters

Two of the defects are only observable through *latent state*: after `RESET`, the
session is anonymous again, but a privilege bit survives. A single-state-override diff
cannot express that. The learner discovers it as an extra state, and the diff then
locates the four-symbol sequence that exposes it. The other three are transition or
output defects, and the same pipeline finds them without being told what to look for.

The alphabet experiment is the honest caveat: the method's power is bounded both by
the input alphabet the analyst chooses and by the depth of the conformance test, and
neither is free.

## Install

Not on PyPI. Install from a clone:

```bash
git clone https://github.com/nebula-eng/protocol-diff.git
cd protocol-diff
python -m pip install -e ".[plots]"
```

The learner and the diff are standard library only. `matplotlib` sits behind the
`plots` extra and is needed by `make figures` alone. Python 3.11 or newer.

## Quickstart

```bash
make test     # 19 tests
make eval     # learn + diff every variant over 3 alphabets -> results/results.json
make figures  # -> results/fig_*.png
```

```bash
PYTHONPATH=src python -m protocol_diff.cli bench
PYTHONPATH=src python -m protocol_diff.cli explain --variant clearance_persist
PYTHONPATH=src python -m protocol_diff.cli learn --variant admin_persist
```

`explain` prints the witness and both transcripts, including the state each side
lands in after every symbol.

## Layout

```
src/protocol_diff/
  protocol.py   6-state reference machine, 5 defective variants, black-box SUT
  learner.py    L* for Mealy machines with cached membership queries
  diff.py       product-machine BFS, shortest distinguishing sequence
  bench.py      learn/diff/verify pipeline + alphabet ablation
  cli.py        bench / explain / learn
tests/          19 tests (transition semantics, learner, exact diff, verification,
                byte-stability of results.json)
scripts/        make_figures.py, check_repro.py
results/        results.json (3 alphabets), timing.json, fig_detection.png,
                fig_witness.png
```
## Method

1. Membership queries. `SUT.query(sequence)` resets the implementation and returns
   the output sequence. Results are cached by sequence, so the table's `T(s, e)` cells
   share one execution.
2. L\*. Observation table over prefixes `S` and suffixes `E`; rows are output
   sequences. Closedness and consistency are repaired by adding prefixes and
   distinguishing suffixes; counterexamples from conformance testing add all prefixes
   and all suffixes.
3. Conformance testing. Exhaustive over all sequences of length <= 3, plus 600
   random walks of length 4-14, seeded for reproducibility. This is the weak link: a
   real deployment would use the W-method with a state-cover set.
4. Diff. BFS over the product of the two learned machines. Because both are
   deterministic and complete, the first output mismatch is the shortest witness, and
   exhaustion is a proof of equivalence.
5. Verification. Replay the witness on the ground-truth machines and require the
   output sequences to differ. Unverified detections are reported as failures.

## Documentation

- [`docs/DESIGN.md`](docs/DESIGN.md): L\* for Mealy machines, the observation table,
  the product construction, alphabet ablation.
- [`docs/THREAT_MODEL.md`](docs/THREAT_MODEL.md): assumptions, what the method cannot
  find, operational safety.
- [`docs/EVALUATION.md`](docs/EVALUATION.md): witnesses, alphabet ladder, cost,
  threats to validity.
- [`CONTRIBUTING.md`](CONTRIBUTING.md): the design rules a patch has to keep.
- [`SECURITY.md`](SECURITY.md): what counts as a vulnerability here, and how to report.
- [`CHANGELOG.md`](CHANGELOG.md): release notes.
## Limitations

- The reference SUT is in-process; a networked deployment adds timeouts, retries and
  non-determinism that this artifact does not model.
- Conformance testing is random plus bounded-exhaustive, not W-method complete, so a
  learned model can miss a state. The benchmark reports state counts so this is
  visible rather than hidden.
- Five defects, one protocol family. The detection rate is not an estimate of
  real-world recall.
- No counterexample minimisation beyond BFS shortest-path; witnesses are minimal in
  symbols, not in semantic steps.

## License

MIT, see [`LICENSE`](LICENSE).
