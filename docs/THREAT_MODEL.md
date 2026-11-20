# Threat model and scope

## 1. What is modelled

A remote service that speaks a session-oriented request/response protocol. The analyst
can send messages and observe responses. Nothing else: no source, no binary, no symbol
table, no server logs.

The adversary in the offensive sense is the analyst: given only the wire behaviour, can
they reconstruct the state machine and find the shortest input that separates a
defective implementation from a reference one?

## 2. Assumptions

| assumption | consequence if violated |
|---|---|
| deterministic responses | learner needs stabilisation / repetition; not implemented |
| reset available between queries | membership queries leak state across tests; a real protocol would need a fresh connection per query |
| complete transition table | product BFS assumes a defined output for every (state, symbol) |
| single session at a time | concurrency would add interleavings the Mealy model cannot express |
| no rate limiting | 1,861-4,506 queries per variant is far above what most services tolerate |
| bounded message alphabet | alphabet choice bounds what can be discovered (Section 4 of EVALUATION) |

## 3. What the method can and cannot find

Can find: wrong transition targets, wrong response codes, missing lifecycle
enforcement (close, reset, privilege drop), output leaks in states that should be
silent, and defects that require latent state to observe.

Cannot find: memory-safety bugs, injection flaws whose trigger is inside a single
message payload, timing side channels, concurrency bugs, cryptographic weaknesses, or
any defect whose distinguishing behaviour lies outside the chosen alphabet.

## 4. Non-claims

- No claim that the protocol is representative of TLS, SSH, or any deployed protocol.
- No claim of novelty for L* or for automata-based protocol inference. The contribution
  is the end-to-end pipeline (learn, diff, verify) and the quantified alphabet
  trade-off.
- No claim that 5/5 detection generalises. Five hand-written defects cannot estimate a
  recall rate.

## 5. Operational safety

The SUT is an in-process Python object. No sockets are opened, no external host is
contacted, nothing is written outside `results/`, and the "attack" is a list of strings
replayed against a local model. The design is deliberately non-weaponisable: to point
it at a real service you would have to replace `SUT` with a network client, and the
query volume would be immediately detectable.

## 6. Ethics

Protocol state-machine inference against systems you do not own is intrusive and, in
many jurisdictions, unlawful even when no data is exfiltrated. This artifact exists to
study *detection of implementation divergence*, not to provide a scanning tool. The
reference implementation and all defects are synthetic.
