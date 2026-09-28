# Design Audits

Durable audit methodology and evidence live here. Security and algorithm
correctness are separate review dimensions and both remain part of the
repository's maintained engineering policy.

## Security audits

- [Security audit methodology](security-audit-methodology.md)
- [Deep security audit — 2026-09-28](security-audit-2026-09-28.md)

The security methodology covers trust boundaries, dependencies, diagnostics,
filesystem identity, subprocesses, secrets, cryptography, and related
adversarial behavior.

## Algorithm correctness audits

- [Algorithm method audit](algorithm-method-audit.md)
- [Proof-test catalogue](proof-test-catalogue.md)
- [Single-process CI strategy](ci-strategy.md)
- [Algorithm correctness audit guide](../../guides/algorithm-correctness-audit.md)
- [Algorithm evidence registry](../../audits/algorithm-registry.md)

Algorithm audits record contracts, admissible parameter domains, invariants,
independent oracles, adversarial cases, complexity/boundedness, failure
atomicity, and execution evidence.

Audit documents record evidence and residual assumptions. Current executable
policy remains defined by repository code/configuration, `AGENTS.md`,
`CONTRIBUTING.md`, and `SECURITY.md`.
