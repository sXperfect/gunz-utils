# AR-02: Transactional directory competing-publisher semantics

**Date:** 2026-10-08
**Status:** Done — scoped repair and final integration verified
**Priority:** P1/P2
**Parent:** [Audit follow-up](2026-10-08-audit-follow-up.md)
**Evidence:** AU-01 finding F3; see the corresponding AU-01/02/03 active review packet.

## Goal and ownership

Repair the reproduced contract failures while preserving existing package/API
invariants. Proposed exclusive ownership: fs.py; new tests/test_core/test_audit_directory_publication_regressions.py.

## Implementation approach

Specify atomic no-replace publication on supported platforms. Use an appropriate OS primitive where available; preserve clear fallback/platform limits rather than presenting check-then-replace as atomic rejection. Keep private staging and failure cleanup.

## Meaningful regression checks

Insert a competing empty destination immediately before publication and preserve its inode/content. Retain static existing target and dangling symlink rejection. Verify staging cleanup, non-empty target behavior and unsupported-platform outcome.

## Dependencies and integration

Choose platform behavior during implementation; any shared filesystem helper must be coordinated with AR-01.

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

Linux atomic renameat2 with RENAME_NOREPLACE implemented, with macOS renamex_np/RENAME_EXCL and Windows rename branches. Unsupported platforms/filesystems fail explicitly and clean staging. Linux competing-empty-target regression preserves the competing inode; dangling symlink and unsupported cleanup regressions pass. Platform branches other than Linux were inspected, not executed.

35 existing/publication tests passed; later pinned combined coordinator suite: 76 passed. Counts overlap with other coordinator records; do not sum them.
Pinned Ruff 0.14.10 and mypy 1.19.1 pass the coordinator-owned sources and
new tests under Python 3.11.14/pytest 9.0.3. Full aggregate gate is pending.

The API semantics were checked against [Linux rename documentation](https://www.man7.org/linux/man-pages/man2/rename.2.html) and [Apple exclusive rename support](https://developer.apple.com/documentation/foundation/urlresourcevalues/volumesupportsexclusiverenaming). Parent-directory identity remains a trusted boundary.

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
