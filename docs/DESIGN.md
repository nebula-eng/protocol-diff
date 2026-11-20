# Design

## 1. Goal

Recover a protocol implementation's observable state machine using only queries, then
compute the shortest input sequence on which two implementations disagree. The output
is not a verdict ("vulnerable") but a reproducible witness: an ordered list of
messages and the differing responses on each side.

## 2. Model

The protocol is a Mealy machine `(S, s0, A, O, delta, lambda)`:

- 10 input symbols: `HELO AUTH_GOOD AUTH_BAD GET_PUB GET_PRIV PUT ADMIN RESET BYE PING`
- 9 output symbols: `220_READY 331_CHALLENGE 230_OK 530_DENY 200_PUB 150_DATA
  250_STORED 221_BYE 421_CLOSED`
- 6 states in the reference: `NEW ANON AUTHED PENDING ADMIN CLOSED`

Mealy, not DFA, because protocol responses are produced on transitions and carry the
information an attacker needs. A DFA over a "success/failure" abstraction would erase
the difference between `530_DENY` and `421_CLOSED`, which is exactly the distinction
two of the defects turn on.

```
NEW --HELO--> ANON --AUTH_GOOD--> AUTHED --ADMIN--> PENDING --AUTH_GOOD--> ADMIN
               |                    |                  |
               |                    +------ RESET -----+--> ANON
               +------------------------ BYE --------------> CLOSED
```

`CLOSED` is absorbing. All ten symbols are defined in every state (the table is
complete), because a partial machine makes the product construction and the learner's
closedness check ambiguous.

## 3. Latent state

The two interesting defects are not transition typos. They keep a flag that the
protocol's *public* state does not expose:

| defect | latent bit | observable only after |
|---|---|---|
| `clearance_persist` | privilege survives RESET | an authenticated session is reset |
| `admin_persist` | admin role survives RESET | an admin session is reset |

This forces the learner to add a state. A model that merges `ANON` and
`ANON_TAINTED` cannot represent the bug, and the diff would report equivalence. The
benchmark therefore checks the learned state count, not just detection: both variants
are recovered with 7 states, matching ground truth.

## 4. L\* for Mealy machines

Observation table:

- `S`: prefix-closed set of input sequences, initially `{()}`
- `E`: suffix-closed set of input sequences, initially `{()}`
- `T(s, e)`: output sequence produced by running `e` after `s`

A row is `row(s) = (T(s, e) for e in E)`. Two prefixes are equivalent iff their rows
are equal.

Closedness. For every `s in S` and `a in A`, `row(s·a)` must equal `row(s')` for
some `s' in S`. Otherwise add `s·a` to `S`.

Consistency. If `row(s1) == row(s2)`, then for every `a`, `row(s1·a)` must equal
`row(s2·a)`. Otherwise find `e in E` with `T(s1·a, e) != T(s2·a, e)` and add `a·e`
to `E`.

Hypothesis. States are distinct rows of `S`; `delta(row(s), a) = row(s·a)`;
`lambda(row(s), a) = T(s, (a,))[-1]`.

Counterexample. All prefixes go to `S`, all suffixes go to `E`. This is the
standard treatment and it terminates because each counterexample adds at least one
distinguishing suffix.

### Query caching

`T(s, e)` is the suffix of `outputs(s + e)` after `len(s)` symbols. One cached run of
`s + e` therefore answers every cell that shares that concatenation. On the reference
machine the learner performs 1,861 membership queries and 1,724 conformance checks;
without caching the table alone would need roughly 9,400 executions.

## 5. Equivalence checking

Two different things are called "equivalence" in this project and they must not be
confused:

| step | method | guarantee |
|---|---|---|
| learner vs SUT | bounded exhaustive (length <= 3) + 600 random walks (length <= 14) | not a proof; a missed state is possible |
| learned model vs learned model | full product BFS | exact: deterministic, complete, finite state space |

The first is the honest cost of black-box access; the second is what makes the witness
trustworthy. The benchmark reports learned state counts precisely so that a failure of
the first step is visible.

## 6. Witness synthesis

```
frontier = {(init_a, init_b): []}
while frontier:
    (sa, sb), prefix = pop()
    for a in A:
        oa, na = a.step(sa, a); ob, nb = b.step(sb, a)
        if oa != ob: return prefix + [a]
        push (na, nb), prefix + [a]
return None   # equivalent
```

BFS order guarantees the shortest witness in symbols. Exhausting the product without a
mismatch proves equivalence, since every reachable pair has been compared.

## 7. Alphabet ablation

Three alphabets are measured. The core is
`{HELO, AUTH_GOOD, AUTH_BAD, GET_PRIV, RESET, BYE}`; mid adds `{GET_PUB, ADMIN}`;
full adds `{PUT, PING}`.

| alphabet | effect on the learned model |
|---|---|
| core (6) | `AUTHED` and `ADMIN` collapse (they differ only via `ADMIN`), reference drops to 4 states; `admin_persist` and `pub_leak_closed` become unobservable |
| mid (8) | reference recovers to 6 states; `pub_leak_closed` becomes observable, `admin_persist` still is not |
| full (10) | 7-state variant recovered, all five defects observable |

The mid result is the interesting one. Adding `ADMIN` makes the two *states*
distinguishable, but the *defect* still requires reaching `ANON_ADMIN`, whose shortest
access path is six symbols long (`HELO AUTH_GOOD ADMIN AUTH_GOOD RESET ADMIN`). The
conformance test is exhaustive only to length 3 plus random walks, so it never observes
that state; the learner returns a 6-state model, and the witness it derives is rejected
on replay as a false positive. Alphabet size is necessary but not sufficient: the
oracle must also reach the latent state.

Cost is monotone (948 -> 1,301 -> 1,861 reference queries, i.e. 2.0x from core to
full) and so is detection (3/5 -> 4/5 -> 5/5).

## 8. Complexity

- Learning: `O(|S| · |A| · |E|)` table cells, each `O(len(s) + len(e))` time and one
  cached query.
- Conformance: `O(|A|^3 + 600 · 14)` queries per round.
- Diff: `O(|S_a| · |S_b| · |A|)` time, `O(|S_a| · |S_b|)` space.

Measured: the whole grid (5 variants x 2 alphabets, learning plus diffing plus
verification) runs in 0.2-0.3 s depending on machine load.

## 9. Design trade-offs

| decision | alternative | why this one |
|---|---|---|
| Mealy | DFA over abstracted outputs | preserves response identity, needed to distinguish DENY from CLOSED |
| random + bounded exhaustive conformance | W-method | W-method needs a state-cover set and a characterization set, which requires knowing the state count in advance |
| product BFS | random differential testing | BFS gives the shortest witness and a proof of equivalence |
| in-process SUT | TCP daemon | determinism; a networked version is described in THREAT_MODEL as out of scope |
