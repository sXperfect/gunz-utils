# AR-01: CAS publication, materialization, and digest validation

**Date:** 2026-10-08
**Status:** Done — scoped repair and final integration verified
**Priority:** P1
**Parent:** [Audit follow-up](2026-10-08-audit-follow-up.md)
**Evidence:** AU-01 findings F1, F2, F5; see the corresponding AU-01/02/03 active review packet.

## Goal and ownership

Repair the reproduced contract failures while preserving existing package/API
invariants. Proposed exclusive ownership: content_store.py; new tests/test_core/test_audit_cas_publication_regressions.py.

## Implementation approach

Define the writable-root/parent threat model; anchor fanout publication and verification to opened directory descriptors; retain the reserved staging inode/descriptor during copy; bind source identity to the opened object; reject digest characters outside ASCII hexadecimal while preserving uppercase normalization.

## Meaningful regression checks

Reproduce fanout swap and temporary symlink insertion without overwriting an outside synthetic victim; assert returned artifacts stay inside the anchored store and published output is regular. Exercise copy/link failure cleanup, no-overwrite destination behavior, strict malformed digest rejection, and all current supported digest lengths.

## Dependencies and integration

Coordinate shared security helpers with AR-04; same-digest fallback inode semantics require a documented contract before expansion.

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

Not started. Existing focused suites passing does not verify this repair.


## Implemented repair — 2026-10-08

Status: implemented on `audit/follow-up-20261008`; focused validation complete,
coordinator integration gates pending. Source and dedicated regression tests are
owned by AR-01; no shared security helper edits were needed.

- Fanout directory creation, opens, links, replacements, and cleanup use opened
  directory descriptors with no-follow component traversal on supported POSIX.
  Verification hashes an opened regular-file descriptor rather than reopening
  checked paths. Postpublication directory identity checks reject swapped fanout
  names. A detached original directory can retain published bytes after an
  adversarial rename; the operation raises and never redirects publication to
  the attacker's outside inode.
- Materialization keeps the reserved staging descriptor/inode during copy and
  copies from the already-opened verified source. Replacing a source name during
  copying cannot change the bytes copied. Hardlink staging checks the linked
  inode against the pinned source and never deletes a colliding filename it did
  not create. Copy mode/timestamps are retained where descriptor support exists.
- Strict ASCII hex validation preserves uppercase normalization and all five
  supported digest lengths. Descriptor construction failures close duplicates
  and remove owned staging. Source validation precedes destination creation.
- POSIX root and destination ancestors are trusted anchors. Platforms without
  descriptor-relative no-follow operations require trusted directory trees;
  normal fallback functionality remains covered. Concurrent stored-inode content
  mutation must be prevented by callers. Returned Paths are snapshots, so later
  filesystem mutation cannot be prevented by this API. Optional hardlinks retain
  their documented read-only-consumer requirement.
- Same-digest fallback can replace a concurrent winner inode; content rather
  than winner inode preservation is now documented. This does not silently
  introduce a stronger portable atomic no-replace promise.

New regressions cover malformed hex, supported digest normalization, fanout
swaps during ordinary/fallback publication, staging symlink substitution,
verified-source substitution, hardlink source substitution, copy/link/replace
failure cleanup, competing destinations, trusted platform fallback, fdopen
setup failure, colliding hardlink names, and missing descriptor chmod support.
Outside synthetic victims remain unchanged in adversarial cases.

Verification commands use dedicated tests plus existing CAS/algorithm/security
suites. Initial installed environment: 67 passing tests, then 76 passing tests
with extra cleanup/platform regressions; focused mypy initially found a file
handle yield annotation mismatch, corrected with explicit BinaryIO cast.
Pinned environment rerun evidence follows below. No commit or external disclosure
performed; full aggregate verification and shared ledger updates belong to the
coordinator. Re-audit confirms copying never reopens a removed reservation and
no-follow links do not traverse substituted staging symlinks. Hostile directory
writers can still cause denial of service or mutate returned paths after the
operation; these are explicitly bounded trust/identity limitations.

Pinned validation: Python 3.11, pytest 9.0.3, Ruff 0.14.10, mypy 1.19.1 from
`/tmp/gunz-utils-audit-20261008/bin`: 104 passed in 12.02 seconds across the
new CAS suite, existing content-store, A1 proof/audit, security audit/static
modules. Focused mypy: success in one source file. Pinned Ruff: passed after
organizing the dedicated test imports. No skips in the focused test run.

### Residual publication identity limitation

Coordinator adversarial review requested final-link/replace staging substitution
proofs. Both new tests confirm the retained descriptor prevents an outside victim
write and postpublication identity verification raises ValueError, but a staging
name replaced immediately before link/replace can leave a substituted symlink at
the final name. No automatic final-name unlink occurs: that could delete a
concurrent legitimate entry. Thus F2's redirected-copy overwrite is repaired and
successful results require a regular matching inode, while failure-side final
identity under an arbitrary mutable parent remains a residual boundary. Stronger
publication identity needs fd-based publication or protected private staging with
a specified platform/threat contract. Trusted ancestors do not imply immutable
destination entries. Public materialize docstring now states this limit explicitly.

Final-publication residual tests and all dedicated CAS regressions rerun with
pinned pytest: **26 passed in 0.41 seconds**. Pinned Ruff passes on owned source
and tests after the public residual contract was added. The earlier 104-test
aggregate focused run preceded these two added adversarial final-publication
cases; no inflated combined test count is claimed.

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
