# AR-03: Atomic-write descriptor ownership on setup failure

**Date:** 2026-10-08
**Status:** Done — scoped repair and final integration verified
**Priority:** P2
**Parent:** [Audit follow-up](2026-10-08-audit-follow-up.md)
**Evidence:** AU-01 finding F4; see the corresponding AU-01/02/03 active review packet.

## Goal and ownership

Repair the reproduced contract failures while preserving existing package/API
invariants. Proposed exclusive ownership: io.py; new tests/test_core/test_audit_atomic_setup_regressions.py.

## Implementation approach

Track raw descriptor ownership from mkstemp until fdopen successfully assumes it. Close descriptors on fchmod/fdopen setup failures while preserving the original exception and removing staging.

## Meaningful regression checks

Inject both fchmod and fdopen failure; fstat of the captured descriptor must raise EBADF, target bytes remain unchanged, and staging disappears. Preserve ordinary atomic publication and documented post-replace fsync visibility.

## Dependencies and integration

Coordinate behavioral changes with AR-04's atomic-write use; keep post-replace durability semantics unchanged.

Do not start overlapping source/test work until coordinator assigns ownership.
Preserve pre-existing edits in enums.py, models.py, metadata, and release files.
Use a focused branch based on current main for implementation; never reset the
user's working tree. Add a uniquely named fixed/security fragment as appropriate.
Security details stay local until SECURITY.md disclosure requirements are met.

## Acceptance

- [x] Original probe reproduced and contract stated.
- [x] Focused typed repair and meaningful regression tests implemented.
- [x] Relevant tests, Ruff/mypy and applicable docs/packaging checks pass.
- [x] Parent's shared registry reconciliation records actual repaired revision.
- [x] Canonical full gate passes before integration; no unsupported A4 claim.

## Execution evidence

### Repair evidence

Raw descriptor ownership remains with atomic_write for the entire operation;
fdopen uses closefd=False and the raw fd closes exactly once in final cleanup.
Both fchmod and fdopen injection tests assert EBADF, unchanged old target and
removed staging; the original failure object is preserved. Independent review
found CPython encoding setup can close a wrapper before raising; a real invalid
codec regression now checks the raw descriptor remains owned until our cleanup.

Pinned combined coordinator suite: 76 passed; initial atomic/network focused suite: 48 passed. Counts overlap with other coordinator records; do not sum them.
Pinned Ruff 0.14.10 and mypy 1.19.1 pass the coordinator-owned sources and
new tests under Python 3.11.14/pytest 9.0.3. Full aggregate gate is pending.

No change to documented post-replace fsync visibility. New fragment: changes/20261008-atomic-setup-descriptor.fixed.md.

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
