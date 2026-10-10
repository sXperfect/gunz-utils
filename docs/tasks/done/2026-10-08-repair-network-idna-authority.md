# AR-07: Validate URI authority after IDNA normalization

**Date:** 2026-10-08
**Status:** Done — scoped repair and final integration verified
**Priority:** P1
**Parent:** [Audit follow-up](2026-10-08-audit-follow-up.md)
**Evidence:** AU-05 Unicode delimiter normalization probe; full packet in [AU-05](2026-10-08-audit-graph-input-bounds.md).

## Ownership and implementation

Proposed owner scope: network.py and a dedicated URI normalization regression test file.

Validate the final ASCII hostname after IDNA conversion, before composing the authority. Reject normalized user-info/path/query/fragment/port delimiters and control/backslash characters while preserving legitimate internationalized DNS and IPv6 handling.

## Regression checks

Test fullwidth @, slash and colon, other normalization-sensitive delimiters, ASCII injection, legitimate IDNA names, IPv4/IPv6 and explicit ports. Parse every accepted output independently and assert hostname/userinfo/port match intended inputs.

## Integration and acceptance

- [x] Confirm the recorded trigger against the current source and state the contract.
- [x] Coordinator assigns exclusive source/test ownership before changes.
- [x] Repair and meaningful focused regressions pass.
- [x] Preserve user edits and public compatibility; add appropriate changelog fragment.
- [x] Applicable lint/type/docs checks and canonical full gate pass before integration.
- [x] Shared evidence reconciliation records actual execution without unsupported A4 promotion.

### Repair evidence

Encoded ASCII DNS hostname is revalidated for authority/port/path delimiters and invalid characters before composition. Nine fullwidth delimiter cases reject; independent parsed-host checks preserve legitimate IDNA names, IPv4/IPv6, encoded userinfo, explicit port/path/query.

Pinned combined coordinator suite: 76 passed; initial atomic/network focused suite: 48 passed. Counts overlap with other coordinator records; do not sum them.
Pinned Ruff 0.14.10 and mypy 1.19.1 pass the coordinator-owned sources and
new tests under Python 3.11.14/pytest 9.0.3. Full aggregate gate is pending.

New fragment: changes/20261008-network-idna-authority.security.md. Destination allowlisting remains caller-owned.

## Final integration evidence — 2026-10-08

The scoped repair work passed the canonical aggregate verifier on
`audit/follow-up-20261008`, based on `80bde76a641ce4577574fde60ec957251aee2ba0`
plus the preserved user changes and this local repair tree. No commit, merge,
release, or publication was performed.

- Python 3.11.14 and 3.12.13: **1,244 passed, 22 intentional native-absent skips**
  per main suite; each interpreter also ran **57 compiled-native tests with zero
  skips**, and 35 fallback tests with 22 expected native skips. Counts overlap.
- Ruff 0.14.10 and mypy 1.19.1: pass across the complete configured scope
  (97 Python source files for mypy).
- Release metadata, strict Sphinx, all optional isolation cases, real plot,
  wheel/sdist separate installs, extracted-sdist wheel rebuild/install, and
  optional C activation: pass. Separate compiler-hidden sdist install: pass.
- Full aggregate result: all six gates return zero. Local evidence:
  `tmp/audit-20261008-final-summary.json` and
  `tmp/audit-20261008-final-verification.log`.
- Execution-input fingerprint: `b872b0f9f251f431f83f3e7433d2789e947be3a91f8144fa81d32690e882b222` (238 source/test/config,
  doc-source and package metadata files; excludes evolving audit records and
  generated files). Manifest: `tmp/audit-20261008-final-tree.json`.

Earlier pending/failed statements in the chronological review/repair evidence
refer to intermediate attempts. This final run followed the subprocess type
correction and the interpreter-independent native depth cutoff. Historical A4
levels are not blanket-promoted. The repository-wide algorithm proof program
remains active for the documented deeper graph, concurrency, crypto, platform,
resource-budget and cross-process proof obligations.
