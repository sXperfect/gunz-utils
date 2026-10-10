# AR-09: Validate sync timeout before success-marker mutation

**Date:** 2026-10-08
**Status:** Done — scoped repair and final integration verified
**Priority:** P2
**Parent:** [Audit follow-up](2026-10-08-audit-follow-up.md)
**Evidence:** AU-05 invalid timeout marker side-effect probe; full packet in [AU-05](2026-10-08-audit-graph-input-bounds.md).

## Ownership and implementation

Proposed owner scope: sync.py and dedicated rsync failure-atomicity regressions.

Validate the timeout's finite/type/range contract before invalidating marker or performing other filesystem/subprocess actions. Reuse existing validation conventions and preserve intended marker lifecycle for valid execution.

## Regression checks

NaN, infinity, bool and negative timeout inputs must reject before marker deletion or subprocess launch. Existing marker bytes and metadata remain unchanged on invalid arguments. Test valid timeout, dry-run, and failure/success marker behavior.

## Integration and acceptance

- [x] Confirm the recorded trigger against the current source and state the contract.
- [x] Coordinator assigns exclusive source/test ownership before changes.
- [x] Repair and meaningful focused regressions pass.
- [x] Preserve user edits and public compatibility; add appropriate changelog fragment.
- [x] Applicable lint/type/docs checks and canonical full gate pass before integration.
- [x] Shared evidence reconciliation records actual execution without unsupported A4 promotion.

## Implementation result and contract

Sync entry now rejects nonfinite timeout before executable lookup, directory/lock
creation, success-marker deletion or command launch. Timeout remains positive
finite or None; bool/zero/negative retain rejection. Added
changes/20261008-sync-timeout-validation.fixed.md.

Fourteen invalid-input cases exercise NaN, positive/negative infinity, True/False,
negative and zero against existing and absent destination directories. Existing
marker bytes/stat metadata and directory contents remain identical, and mocked
executable lookup/process execution are not called. Valid dry-run/success creates
the ordinary marker, while a valid failing command removes the stale marker as
before. No unrelated source/marker/publication policy was changed.


## Execution evidence

Coordinator-authorized exclusive ownership applied on branch
`audit/follow-up-20261008`, preserving preexisting and other agents' edits.
Pinned tools: `/tmp/gunz-utils-audit-20261008/bin/` Python 3.11.14,
Ruff 0.14.10, mypy 1.19.1, pytest 9.0.3. Executed:

```bash
ruff check src/gunz_utils/subprocess.py src/gunz_utils/sync.py tests/test_core/test_audit_subprocess_deadline_regressions.py tests/test_core/test_audit_sync_timeout_regressions.py src/gunz_utils/pipeline.py src/gunz_utils/leases.py tests/test_core/test_audit_pipeline_lifecycle_regressions.py tests/test_core/test_audit_lease_setup_regressions.py
# All checks passed
mypy src/gunz_utils/subprocess.py src/gunz_utils/sync.py tests/test_core/test_audit_subprocess_deadline_regressions.py tests/test_core/test_audit_sync_timeout_regressions.py src/gunz_utils/pipeline.py src/gunz_utils/leases.py tests/test_core/test_audit_pipeline_lifecycle_regressions.py tests/test_core/test_audit_lease_setup_regressions.py
# Success: no issues found in 8 source files
pytest -q tests/test_core/test_audit_subprocess_deadline_regressions.py tests/test_core/test_audit_sync_timeout_regressions.py tests/test_core/test_subprocess.py tests/test_core/test_sync.py tests/test_core/test_audit_pipeline_lifecycle_regressions.py tests/test_core/test_audit_lease_setup_regressions.py
# 58 passed, 14 subtests passed in 1.18s; no skips
git diff --check
# Passed
PYTHONPATH=src python tmp/au05/probe.py
# bounded subprocess: TimeoutExpired in 0.051s for 0.05s timeout
# sync invalid timeout: ValueError; marker remains True
```

One combined matrix covers multiple repairs; counts must not be summed as
independent coverage. Source re-audit checked shared output retention cap,
separate original-error propagation, cleanup ownership on partial setup,
argv-based process launch and preserved process-group behavior. No public exports,
dependencies or packaging boundaries changed. No commits, installs or publishing.
Full canonical verification and shared evidence reconciliation remain coordinator
responsibilities; no unsupported A4 claim is made.

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
