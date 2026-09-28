# Algorithm audit design

This directory defines the durable design for correctness auditing in
`gunz-utils`. It complements the operational guide in
`docs/guides/algorithm-correctness-audit.md` and the evidence ledger in
`docs/audits/algorithm-registry.md`.

The audit is intentionally method-oriented. Every maintained algorithm,
state machine, parser, bounded-resource helper, and deterministic transform
should be explainable in terms of its contract, admissible parameter domain,
invariants, independent oracle, adversarial cases, and execution evidence.

Documents:

- [Method audit protocol](algorithm-method-audit.md) — how an implementation is
  inspected and what evidence is required before its audit level may increase.
- [Single-process CI strategy](ci-strategy.md) — how one hosted verification job
  collects as many independent failures as practical before returning failure.
- [Proof-test catalogue](proof-test-catalogue.md) — reusable unit-test patterns
  for numerical, graph, binary, stateful, concurrent, filesystem, and parsing
  algorithms.

Canonical evidence remains in `docs/audits/algorithm-registry.md`. These
documents define the method; the registry records which methods have actually
satisfied it.
