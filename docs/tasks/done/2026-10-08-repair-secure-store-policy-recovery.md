# AR-04: SecureStore authenticated format policy and rotation recovery

**Date:** 2026-10-08
**Status:** Done — scoped repair and final integration verified
**Priority:** P1
**Parent:** [Audit follow-up](2026-10-08-audit-follow-up.md)
**Evidence:** AU-02 findings F1, F2; see the corresponding AU-01/02/03 active review packet.

## Goal and ownership

Repair the reproduced contract failures while preserving existing package/API
invariants. Proposed exclusive ownership: ext/secure_store.py; new tests/test_secure/test_audit_policy_recovery_regressions.py.

## Implementation approach

Authenticate strict-format policy with key metadata; fail closed when modern policy is missing/corrupt; preserve an explicit trusted legacy migration route. Repair rotation cleanup by reconciling durable generation, restoring or reconnecting transaction state, preserving original failure, and retaining pending key material when recovery needs it.

## Meaningful regression checks

Replayed pre-migration token plus deleted/altered policy must fail for read/overwrite/delete/integrity; reopen and rotation preserve strictness; trusted legacy upgrade remains usable. Inject body/COMMIT/ROLLBACK failures both before and after durable commit; compare live and independent reopened instances and verify future writes/recovery.

## Dependencies and integration

Single owner for both fixes due to common source. Coordinate filesystem helper changes with AR-01/03. Whole authenticated snapshot rollback freshness remains outside this repair.

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

Implemented on audit/follow-up-20261008. Authenticated v2 key-check encodes strict
versus trusted migration policy; record operations/integrity/unlock reject missing
or inconsistent modern metadata, including with legacy opt-in. Existing v1 strict
stores upgrade automatically; genuine unbound legacy data requires explicit
unlock(allow_legacy=True) then migrate_records(). API docstring and approved
quickstart paragraph document this security compatibility change. The approved
legacy fixture now constructs genuine v1 metadata; modern corruption regression
remains covered. Complete authenticated snapshot rollback requires external
freshness state.

Rotation reconnects and compares durable generation/policy after failure,
restoring old state after abort or adopting new state and retaining pending key
material after commit. Original failures survive rollback/reconnect errors;
indeterminate state locks the store. Repeated rotation promotes a previously
committed pending key before staging another rotation.

Dedicated regression module adds 21 cases: saved legacy token plus marker
deletion/alteration for read/set/delete/integrity; modern reopen rejects even
legacy opt-in; trusted v1 upgrade/migration; automatic strict v1 upgrade;
body/COMMIT/ROLLBACK failures before/after durable commit; independent reopened
state and later writes; indeterminate recovery; second-rotation key preservation.

Executed using existing Python 3.11.14, pytest 9.0.2, cryptography 49.0.0:
- PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 timeout 60 .../bin/python -m pytest
  tests/test_secure -q -p no:cacheprovider: **85 passed in 18.80s**, no skips.
- timeout 45 .../bin/python -m mypy --follow-imports=silent --cache-dir
  tmp/au02/mypy-cache src/gunz_utils/ext/secure_store.py:
  **Success: no issues found in 1 source file**.
- PATH Ruff 0.4.9 qualified check excluding legacy UP038 passed owned source/new
  tests; pinned Ruff 0.14.10 check passed source/new tests/approved existing fixture.

Source/tests, approved quickstart paragraph, and unique security fragment were
changed. Shared registry/index/metadata/crypto/io/security were not edited.
Ruff formatting includes harmless formatting-only source changes. An optional
cleanup attempting to restore whole unchanged methods from HEAD was rejected by
automatic approval review because it could overwrite user edits; that operation
was abandoned, so no restoration occurred and no approval is needed to proceed.

Existing pytest/cryptography are below maintained floors. Canonical pinned-tool,
docs/packaging/full gate and registry reconciliation remain coordinator-owned.
Pinned environment rerun: pytest 9.0.3 / cryptography 50.0.2, same 85 secure tests
passed in 13.81s. Pinned Ruff 0.14.10 passed the changed source and both relevant
test files. Pinned mypy1.19.1 scoped source check also passed.
No A4, shared-environment install, commit, publish or release claim.



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
