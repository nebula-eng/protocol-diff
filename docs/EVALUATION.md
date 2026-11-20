# Evaluation

## 1. Setup

| item | value |
|---|---|
| host | Windows 11, Python 3.13.14, CPython |
| protocol | 10 input symbols, 6 reference states |
| variants | 5 injected defects |
| alphabets | full (10 symbols), core (6 symbols) |
| repetitions | none needed: every step is deterministic |
| runtime | 0.2-0.3 s for the entire grid (measured; machine-dependent) |

Every decision is deterministic: the learner's cache, the conformance random walks
(seeded `0x5EED`) and the product BFS produce identical states, witnesses and query
counts on every run, so there is nothing to average over and no confidence interval
appears below. Wall-clock measurements are written to `results/timing.json`; the
committed `results.json` holds only deterministic fields and is byte-identical across
runs.

## 2. Primary results (full alphabet)

| defect | states learned | states true | membership queries | conformance checks | witness length | verified |
|---|---:|---:|---:|---:|---:|---|
| `clearance_persist` | 7 | 7 | 3,662 | 3,082 | 4 | yes |
| `admin_persist` | 7 | 7 | 4,506 | 3,362 | 6 | yes |
| `auth_inverted` | 6 | 6 | 1,861 | 1,724 | 2 | yes |
| `close_ignored` | 6 | 6 | 1,861 | 1,724 | 3 | yes |
| `pub_leak_closed` | 6 | 6 | 1,861 | 1,724 | 2 | yes |

Reference model: 6 states, 1,861 membership queries, 1,724 conformance checks.

Detection rate 5/5, with zero false positives. Verification is not a formality:
a witness only counts if replaying it on the two ground-truth implementations produces
different output sequences. All five did.

## 3. Witnesses

| defect | witness | reference output | variant output |
|---|---|---|---|
| `clearance_persist` | `HELO AUTH_GOOD RESET GET_PRIV` | `... 220_READY 530_DENY` | `... 220_READY 150_DATA` |
| `admin_persist` | `HELO AUTH_GOOD ADMIN AUTH_GOOD RESET ADMIN` | `... 530_DENY` | `... 230_OK` |
| `auth_inverted` | `HELO AUTH_BAD` | `220_READY 530_DENY` | `220_READY 230_OK` |
| `close_ignored` | `HELO BYE HELO` | `... 421_CLOSED` | `... 220_READY` |
| `pub_leak_closed` | `BYE GET_PUB` | `221_BYE 421_CLOSED` | `221_BYE 200_PUB` |

The two latent-state defects need 4 and 6 symbols; the shallow ones need 2-3. None of
the witnesses were supplied to the tool: each is the BFS shortest path in the product
of the two *learned* models.

## 4. Alphabet ablation

| metric | core (6) | mid (8) | full (10) |
|---|---:|---:|---:|
| reference states learned | 4 | 6 | 6 |
| reference membership queries | 948 | 1,301 | 1,861 |
| detection rate | 3/5 | 4/5 | 5/5 |
| `clearance_persist` | found | found | found |
| `admin_persist` | missed | unverified witness | found |
| `auth_inverted` | found | found | found |
| `close_ignored` | found | found | found |
| `pub_leak_closed` | missed | found | found |

Detection is monotone in alphabet size, and so is cost: 948 -> 1,301 -> 1,861 reference
queries for 6 -> 8 -> 10 symbols (2.0x end to end).

The mid row needs care. `admin_persist` produces a witness at mid, but the witness does
not reproduce on the ground-truth implementations, so it is recorded as unverified
and excluded from the detection count. The cause is the oracle, not the alphabet: the
defect is only observable after a six-symbol access path, and the conformance test
(exhaustive to length 3 plus random walks) never reaches that state. The learned model
has 6 states where the truth has 7. This is exactly the failure mode the verification
step exists to catch, and it is reported rather than smoothed over.

## 5. State-space recovery

Learned state counts match ground truth in all five full-alphabet cases (7,7,6,6,6).
This matters more than the detection count: a model with the wrong number of states
can still detect a defect by accident, but it cannot explain the protocol. Under the
core alphabet the reference collapses to 4 states, which is the correct minimal model
for that alphabet. The collapse is a property of the observation, not a learner
bug.

## 6. Cost model

| phase | cost |
|---|---|
| membership queries | 1,861-4,506 per variant |
| conformance checks | 1,724-3,362 per variant |
| wall clock, whole grid | 0.2-0.3 s (machine-dependent) |

Cost grows with the number of states (7-state variants need ~2-2.4x the queries of
6-state ones), which is the expected `O(|S|·|A|·|E|)` behaviour.

## 7. Threats to validity

1. Conformance testing is incomplete. Exhaustive to length 3 plus 600 random walks
   is not the W-method. A learned model may miss a state, and the benchmark would then
   report a missed detection without distinguishing "learner failed" from "defect
   invisible under this alphabet". State counts are published to make this auditable.
2. In-process SUT. No timeouts, retries, message loss or reordering. A networked
   SUT would make membership queries noisy and the learner would need a stabilisation
   strategy.
3. Five defects, one protocol. The defects were written to span classes
   (latent state, transition inversion, output leak, lifecycle), but five is five.
   The 5/5 rate is not an estimate of real-world recall.
4. Alphabet chosen by the analyst. The ablation quantifies the sensitivity but does
   not solve it. Automatic alphabet discovery is the obvious next step and is not
   implemented.
5. Witness minimality is syntactic. Shortest in symbols, not in wall-clock or in
   operator effort; a 6-symbol witness may be cheaper to execute than a 4-symbol one in
   a real deployment.
