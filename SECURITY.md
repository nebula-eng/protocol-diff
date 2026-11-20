# Security policy

## Reporting a vulnerability

Report privately through GitHub's [security advisory
form](https://github.com/nebula-eng/protocol-diff/security/advisories/new). The
report is visible only to the maintainer. There is no mailing list, so nothing sent
to an address at this project's name reaches anyone.

Include the command you ran, the input that triggers the problem, and the Python
version. You will get an acknowledgement within 72 hours.

## What counts here

This project learns a Mealy machine from black-box queries, diffs two learned machines by exact product-machine traversal, and replays the shortest witness against both implementations. That shapes what a vulnerability is:

- The SUT is in-process. A networked deployment adds timeouts, retries and non-determinism that this artifact does not model.
- Conformance testing is bounded-exhaustive plus seeded random walks, not W-method complete, so a learned model can miss a state. State counts are reported so the gap is visible.
- Five defects in one protocol family. The detection rate is not an estimate of real-world recall.

A wrong verdict with no crash is in scope. In a measurement artifact a silently wrong
number is worse than an exception, because nothing prompts a reader to check it.

## Out of scope

- Anything that requires modifying the repository before running it.
- Differences caused by the host, where the README already states that a number is
  machine-dependent.
- The limits listed under Limitations in the README. They are known and written
  down; a report that restates one is not a finding.

## Data handling

The system under test is an object in the same process. No socket is opened, and nothing is written outside `results/`.
