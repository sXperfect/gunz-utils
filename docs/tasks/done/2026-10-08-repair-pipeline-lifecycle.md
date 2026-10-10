# AR-05: Worker pipeline setup ownership and child cancellation

**Date:** 2026-10-08
**Status:** Done — scoped repair and final integration verified
**Priority:** P1
**Parent:** [Audit follow-up](2026-10-08-audit-follow-up.md)
**Evidence:** AU-03 findings F1, F2; see the corresponding AU-01/02/03 active review packet.

## Goal and ownership

Repair the reproduced contract failures while preserving existing package/API
invariants. Proposed exclusive ownership: pipeline.py; new tests/test_core/test_audit_pipeline_lifecycle_regressions.py.

## Implementation approach

Move all setup inside ownership cleanup; track created tasks incrementally and close rejected coroutines. Supervise terminal child outcomes so worker/producer self-cancellation propagates without leaving outgoing.get waiting indefinitely.

## Meaningful regression checks

Task creation failure at producer, first and later worker leaves no live owned task or unawaited warning. Worker and producer CancelledError, caller cancellation, early close, queued work, simultaneous completion/failure, and ordinary worker bounds behave consistently.

## Dependencies and integration

Source independent of storage fixes; coordinate repeated-cancellation contract with AU-03/AU-05 rather than expanding it silently.

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

Implementation: all producer/worker task submission is under cleanup ownership,
with a start barrier, incremental task registration and explicit closure of rejected
coroutines. Bounded queue publication wakes a supervisor event; terminal child
cancellation is observed before waiting for another queue result. Cleanup cancels
owned work once and shields the drain across repeated caller cancellation,
preserving the initiating exception/cancellation. Queue capacity/worker bounds
are unchanged. Added eight focused regression cases including setup rejection at
producer/first/later worker, producer/worker self-cancel, original caller cancellation
through repeated cancellation, simultaneous result/cancel, and early close with
full queues. Fragment: changes/20261008-pipeline-lifecycle.fixed.md.

Baseline main HEAD 80bde76a641ce4577574fde60ec957251aee2ba0 on coordinator-created
branch audit/follow-up-20261008 with preserved preexisting edits and concurrent
owned repairs. Python 3.11.14/pytest 9.0.2 from existing gunz-utils environment.
Commands executed:

```bash
python -m pytest -q tests/test_core/test_audit_pipeline_lifecycle_regressions.py tests/test_core/test_audit_lease_setup_regressions.py tests/test_core/test_a1_algorithm_audit.py tests/test_core/test_a1_algorithm_proofs.py tests/test_core/test_leases.py tests/test_core/test_concurrency.py
# 81 passed in 0.37s; no skips
python -m mypy src/gunz_utils/pipeline.py src/gunz_utils/leases.py tests/test_core/test_audit_pipeline_lifecycle_regressions.py tests/test_core/test_audit_lease_setup_regressions.py
# Success: no issues found in 4 source files
ruff check src/gunz_utils/pipeline.py tests/test_core/test_audit_pipeline_lifecycle_regressions.py tests/test_core/test_audit_lease_setup_regressions.py
# All checks passed (Ruff 0.4.9 at /home/adhisant/.local/bin/ruff)
git diff --check
# Passed
PYTHONPATH=src python tmp/au03/probe.py
# setup orphan tasks: 0; setup warnings: []; worker self cancellation: CancelledError
# lease setup warnings: []; original setup RuntimeErrors retained
```

Initial combined suite failure was unrelated concurrent CAS fallback test-double
kwargs compatibility. Coordinator authorized narrow kwargs pass-through updates
to no_hardlinks/record_replace in test_a1_algorithm_audit.py; rerun above passed.
Those changes preserve fault injection. Full file Ruff with old 0.4.9 reports
preexisting UP038 on leases.py:42/135 and existing proof-file import order;
leases.py passes with that obsolete rule ignored. Aggregate coordinator gate
with pinned tools remains required; no A4 claim, no source outside assigned
ownership changed, and no commit/publishing. Repository registry/index is left
for coordinator reconciliation.



Subsequent pinned verification (Ruff 0.14.10/mypy 1.19.1/pytest 9.0.3) supersedes
the earlier old-Ruff limitation: all four owned repair sources and four new
regression modules pass Ruff/mypy (8 source files); combined subprocess/sync/
lifecycle matrix passes 58 tests and 14 subtests. Shared original proof-suite
81-test result remains recorded above. Coordinator full aggregate gate pending.

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
