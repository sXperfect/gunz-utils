# AR-08: Bound synchronous subprocess capture through pipe drain

**Date:** 2026-10-08
**Status:** Done — scoped repair and final integration verified
**Priority:** P1
**Parent:** [Audit follow-up](2026-10-08-audit-follow-up.md)
**Evidence:** AU-05 synchronous bounded-capture inherited-pipe probe; full packet in [AU-05](2026-10-08-audit-graph-input-bounds.md).

## Ownership and implementation

Proposed owner scope: subprocess.py and dedicated subprocess lifecycle regressions.

Apply one monotonic deadline to child execution and stdout/stderr drain, including descendants holding inherited pipes after the direct child exits. On expiry terminate the owned process group and join reader resources with bounded cleanup; preserve diagnostic/timeout and byte-cap semantics.

## Regression checks

Launch a synthetic parent that exits while a silent descendant retains pipes; the call must raise timeout within a bounded cleanup allowance rather than return delayed success. Cover ordinary completion, bounded output overflow, inherited stdout/stderr, and reader-thread cleanup. Assert owned processes are reaped.

## Integration and acceptance

- [x] Confirm the recorded trigger against the current source and state the contract.
- [x] Coordinator assigns exclusive source/test ownership before changes.
- [x] Repair and meaningful focused regressions pass.
- [x] Preserve user edits and public compatibility; add appropriate changelog fragment.
- [x] Applicable lint/type/docs checks and canonical full gate pass before integration.
- [x] Shared evidence reconciliation records actual execution without unsupported A4 promotion.

## Implementation result and contract

One monotonic deadline now spans direct child wait and all reader-thread joins.
On expiry, original TimeoutExpired is retained, owned process group is killed,
child is reaped, and reader shutdown is bounded by a 0.5s cleanup allowance.
Overflow observed before/in timeout cleanup preserves CommandOutputLimitError
precedence. POSIX readers use pipe readiness polling plus a stop event, allowing
silent escaped descendants' retained pipes to be closed without an unlimited
blocking read. Readers own/close their streams; cleanup closes only unsubmitted
readers' streams, avoiding cross-thread buffered-stream-lock deadlock. Partial
reader start failure also kills/reaps the process and drains already-started work.

Regression matrix verifies deadline and overflow against inherited pipes both
inside/outside the POSIX process group, direct process reaping, absence of reader
threads, shared stdout/stderr byte conservation, and failed second reader start.
Tests explicitly terminate synthetic escaped descendants after asserting helper
behavior. The helper does not claim to kill processes outside its owned group.

Windows limitation: anonymous pipes do not support the POSIX readiness selector;
bounded error cleanup avoids blocking cross-thread close, but unsupported
inherited-pipe descendants may retain a daemon reader until pipe EOF. This
platform/process-tree limit is documented in source and needs native Windows
verification; no universal forcible descendant/thread termination is claimed.

Added changes/20261008-subprocess-drain-deadline.fixed.md. Original observed
late-success probe is now TimeoutExpired within its configured deadline.


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

## Integration review follow-up: reader constructor ownership

Independent review reproduced that Thread construction still preceded cleanup,
leaving the running direct child and both pipes open if a constructor failed.
Coordinator authorized this additional focused repair. All buffer/synchronization
bookkeeping is now created before spawning the process; reader objects are
constructed incrementally inside the cleanup scope. Cleanup closes both streams
without started owners even when no reader object was constructed. Original
submission error remains intact; missing capture pipe errors also enter cleanup.

The regression setup matrix now rejects first/second reader construction and
first/second start, asserting original error identity, closed pipes, reaped direct
process and no surviving reader. Pinned focused execution:

```bash
pytest -q tests/test_core/test_audit_subprocess_deadline_regressions.py tests/test_core/test_subprocess.py
# 20 passed, 14 subtests passed in 0.96s; independent repeat also passed
ruff check src/gunz_utils/subprocess.py tests/test_core/test_audit_subprocess_deadline_regressions.py
# All checks passed
```

An initial type check caught reuse of a narrowed nonoptional stream loop variable
in optional cleanup traversal; renamed cleanup_pipe without ignores. Final
isolated-cache pinned type verification passed: `mypy --cache-dir
tmp/ar08-constructor-mypy src/gunz_utils/subprocess.py
tests/test_core/test_audit_subprocess_deadline_regressions.py` reported no issues
in 2 source files. Coordinator re-runs the aggregate lint gate on stable source. Fragment extended to describe constructor
and start cleanup. No unrelated source or shared proof files changed.

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
