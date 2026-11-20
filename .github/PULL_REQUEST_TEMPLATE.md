## What this changes

<!-- One paragraph. If it moves a reported number, give the before and after. -->

## Kind

- [ ] Defect fix
- [ ] New protocol, parser or detector
- [ ] New measurement or experiment
- [ ] Documentation
- [ ] Refactor with no behaviour change

## Design rules

- [ ] A detection counts only when the witness replays against both ground-truth machines and their outputs differ. An unverified witness is reported as a false positive.
- [ ] The learner is deterministic: cached membership queries, conformance walks seeded with `0x5EED`, breadth-first product traversal.
- [ ] `results/results.json` holds deterministic fields only; wall-clock measurements go to `results/timing.json`.
- [ ] The alphabet is part of the result. A patch that adds a symbol re-runs the whole ladder, not only the full alphabet.

- [ ] `PYTHONPATH=src python -m unittest discover -s tests -v` passes
- [ ] Reported numbers regenerated from `results/results.json`, not hand-edited
- [ ] Documentation updated where behaviour is user-visible

## Evidence

<!-- For a new detector or measurement: the input that triggers it, and one that must
not. False positives matter as much as detections. -->

## Notes for review

<!-- Ordering assumptions, overlap policy, performance trade-offs. -->
