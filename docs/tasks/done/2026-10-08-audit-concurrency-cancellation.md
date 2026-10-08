# AU-03: Concurrency state machines and cancellation

**Date:** 2026-10-08
**Role:** Audit researcher
**Status:** Done — initial review; scoped repair results recorded below
**Priority:** P1
**Parent:** [Audit follow-up](2026-10-08-audit-follow-up.md)
**Baseline:** `80bde76a641ce4577574fde60ec957251aee2ba0` plus existing dirty tree

## Question and scope

Do the current implementations uphold their documented security, correctness,
boundedness, and failure contracts? Scope: cache.py, concurrency.py, resilience.py, dag.py, leases.py, pipeline.py, retry.py, rate_limit.py, async_utils.py.

## Review obligations

SingleFlight simultaneous completion, shared waiter cancellation, cache population/expiry races, breaker generations and half-open recovery, repeated DAG cancellation and compensation, partial task setup cleanup, lease loss, limiter conservation, and deadline expiry before/after await.

## Method and verification

Review current race, DAG, retry, limiter, resilience, and chaos regression tests. Prefer events/barriers and virtual clocks over sleep-based stress. Verify no leaked tasks/coroutines, stale success publication, swallowed cancellation, or unbounded queued work.

Read and obey the parent's shared execution contract. During the initial review,
this file is the worker's only permitted tracked write. Implementation repairs
are proposed for a separately coordinated follow-up.

Existing audit environment candidate:
`/home/adhisant/tmp/miniforge3/envs/gunz-utils/bin/python`.
The coordinator confirmed Python 3.11, pytest, mypy, and cryptography are
available; Ruff is absent. Record actual tool versions and results yourself.

## Deliverables and acceptance

- [x] Source and relevant test inventory reviewed.
- [x] Contract/trust model and parameter domains recorded.
- [x] Findings separated into confirmed defects, proof gaps, stale records,
      and accepted limitations, with source locations and severity rationale.
- [x] Executed commands, results, skips, and reproducible trigger recorded.
- [x] Follow-up repairs specify file ownership, dependencies, and regression checks.
- [x] Coordinator receives a concise findings summary.

## Findings

### Inventory and contract

Read all nine scoped implementation files: `cache.py`, `concurrency.py`,
`resilience.py`, `dag.py`, `leases.py`, `pipeline.py`, `retry.py`,
`rate_limit.py`, and `async_utils.py`. Reviewed the focused tests listed below,
plus the relevant DAG/lease/pipeline adversarial tests and registry entries.

Trust model: callbacks, iterators, cache mappings, and task factories are
caller-provided and may fail; cancellation is a control signal. These helpers
coordinate cooperative tasks inside one event loop; they do not sandbox callbacks
or prevent a callback from suppressing cancellation or blocking the loop.

Input domains inspected: concurrency/worker/queue/capacity counts are positive
integers with bool rejected; TTL is finite nonnegative; breaker threshold positive
integer and recovery delay finite nonnegative; limiter rate/capacity/token request
finite positive with request <= capacity; timeout finite nonnegative except DAG
rollback timeout strictly positive; retries positive integer attempts and finite
nonnegative delays; lease heartbeat finite positive with cadence < duration in
`LeaseTiming`. Bounds are caller-selected, with no fixed package maximum.

Expected invariants: cache retained results <= maxsize; concurrent work <= limit
or workers; pipeline buffers <= queue_size each; shared producers survive individual
waiter cancellation; stale breaker generations cannot close an opened circuit;
lease loss wins simultaneous completion; rollback follows reverse completion;
cancellation and setup failure drain owned tasks and release permits. Ordered
`gather_limited` retains O(n) outputs; unordered mapping bounds active tasks;
`worker_map` uses O(workers + queue_size) tasks/buffers. DAG concurrency_limit
bounds running stages but creates one task/event per stage (O(n)).

### AU-03-F1 — pipeline setup failure escapes cleanup (medium, confirmed)

Location: `src/gunz_utils/pipeline.py:63`, task creation before the cleanup
`try` at line 66. Contract: partial setup must drain created work and close an
unsubmitted coroutine. Trigger: third `asyncio.create_task` call raises, after
producer and first worker creation, for workers=3 and queue_size=1. Observed:
original RuntimeError propagates, **two live owned tasks remain**, and
`coroutine 'worker_map.<locals>.worker' was never awaited` is emitted. Both
orphans were cancelled/awaited by the probe, not by the implementation.

Medium because a failed orchestration call leaves callbacks/source iteration
running and retains inputs/resources until external cleanup. Requires exceptional
task creation (e.g. failing task factory); ordinary setup passes. Existing
`test_worker_pipeline_respects_worker_bound` and worker-failure/producer-failure
proofs cover steady state; initial iteration cleanup proofs apply to
`gather_limited`/`map_unordered`, not pipeline task creation.

### AU-03-F2 — pipeline child cancellation deadlocks consumer (medium, confirmed)

Locations: `src/gunz_utils/pipeline.py:56` and `:68` (also producer `:40`).
Contract: docstring promises failure and cancellation propagation. Trigger:
single work item and one worker; callback raises `asyncio.CancelledError` itself.
Observed: worker terminates without reporting completion/error to outgoing;
consumer remains waiting on `outgoing.get()` until the probe's 50ms watchdog
cancels it, yielding TimeoutError rather than the callback's CancelledError.
No scheduling race is required. A producer iterator raising CancelledError has
the same missing terminal signal by inspection; that variant was not executed.

Medium because legitimate cancellation within a callback can leave the caller
waiting indefinitely, despite all useful work ending. Existing pipeline proofs
cover RuntimeError from worker/producer and early close, but not self-cancellation.
Distinguish this from caller cancellation, which normally reaches `finally`.

### AU-03-F3 — lease setup leaks unsubmitted heartbeat coroutine (low, confirmed)

Location: `src/gunz_utils/leases.py:150`. Trigger: heartbeat `create_task` raises
without closing its supplied coroutine. Observed:
`coroutine '_heartbeat_loop' was never awaited`. Existing operation task is
cancelled/awaited by finally; no live operation orphan was observed in this probe.
Low severity because the remaining artifact is an unstarted coroutine/warning,
while operation ownership cleanup succeeds.

Coverage gap: `tests/test_core/test_a1_algorithm_audit.py:62` explicitly closes
the supplied coroutine inside `fail_heartbeat` at line 75. This masks production's
missing closure obligation. DAG's setup-failure test deliberately does not close
the coroutine and is the better pattern.

### Proof gaps and accepted limitations

- SingleFlight and async cache cleanup/coalescing regressions pass; event-barrier
  proofs for same-key shared waiter cancellation and simultaneous completion
  remain useful. Distinct-key in-flight producers are not bounded by maxsize and
  survive all waiter cancellations until operation completion; retained cache
  capacity is not a producer concurrency guarantee. Add/document an external
  admission bound when callers handle untrusted key volume.
- `cache_clear` clears retained entries but does not invalidate running producers;
  these can subsequently repopulate the cache. Sync misses can also repopulate
  after a clear. Record/document this concurrency contract or add a generation
  barrier if invalidation must fence old results. No stronger documented contract
  was found, so this is not classified as a confirmed defect here.
- Breaker generation logic and half-open cancellation/predicate cleanup have
  passing focused regressions. More complete event-driven histories and a small
  independent state-machine oracle remain proof work; no new breaker failure
  confirmed in this pass.
- Retry timeout bounds retry admission/delays, not the duration of a single
  operation. DAG budget checks occur before stage dispatch, not after stage awaits;
  running stages require an outer timeout/cooperative budget enforcement.
- Cancellation-resistant stages/operations can prevent draining indefinitely.
  DAG rollback timeout can return with `rollback_unfinished` and a still-running
  resistant compensation; its existing test explicitly releases that task after
  inspecting the diagnostic. Cooperative cancellation is a necessary limitation,
  not a guarantee that Python can forcibly terminate arbitrary async code.
- Repeated cancellation while draining pipeline/lease/concurrency cleanup is not
  protected with the same shielded drain pattern as DAG; needs separate bounded
  fault-injection review before extending their lifecycle contract.
- Deep DAG recursion and input-depth bounds are AU-05's ownership.

### Stale/overbroad audit evidence

`docs/audits/algorithm-registry.md` ALG-056 claims A4 initial-scheduling cleanup
for `concurrency.*`, `pipeline.*`; pipeline fault injection above disproves the
family-wide coverage implication. ALG-022 setup-failure cleanup has a narrower
passing regression but misses unsubmitted coroutine closure. These entries need
reconciliation by AU-06 after coordinated repairs; this worker did not change
the registry and makes no new A3/A4 claim.

## Verification evidence

Interpreter: `/home/adhisant/tmp/miniforge3/envs/gunz-utils/bin/python`,
Python **3.11.14**, pytest **9.0.2**. Baseline HEAD confirmed:
`80bde76a641ce4577574fde60ec957251aee2ba0`. No scoped implementation/test file
was dirty at capture. Existing dirty files outside scope: CHANGELOG.md,
pyproject.toml, enums.py, models.py, task index; release fragments already deleted;
coordinator task files newly created. These were preserved.

Sandbox command startup failed with `bwrap: loopback: Failed RTM_NEWADDR:
Operation not permitted`; narrow elevated read/probe/test execution succeeded.
No package installation or network lookup performed.

Executed from repository root with the interpreter above:

```bash
python -m pytest -q tests/test_core/test_cache.py tests/test_core/test_concurrency.py tests/test_core/test_dag.py tests/test_core/test_leases.py tests/test_core/test_retry.py tests/test_core/test_retry_delay_override.py tests/test_core/test_resilience.py tests/test_core/test_resilience_next.py tests/test_core/test_p0_resilience.py tests/test_core/test_a1_algorithm_proofs.py tests/test_core/test_chaos_fault_injection.py
```

Result: **116 passed, 47 subtests passed**, 1.19s; no skips.

```bash
python -m pytest -q tests/test_core/test_orchestration.py tests/test_core/test_deep_audit_round2.py tests/test_core/test_a1_algorithm_audit.py tests/test_core/test_foundation_io_retry.py
```

Result: **76 passed, 20 subtests passed**, 0.98s; no skips. One expected
DeprecationWarning importing the outgoing benchmark namespace. Total: **192 tests,
67 subtests passed**; this is focused execution, not the canonical full gate.

Reproduction: `PYTHONPATH=src <interpreter> tmp/au03/probe.py` (exit 0).
Probe remains ignored temporary evidence; it deliberately prints observed failures
rather than treating them as successful invariant assertions. Output:

```text
setup exception: injected task setup failure
setup orphan tasks: 2
setup warnings: ["coroutine 'worker_map.<locals>.worker' was never awaited"]
worker self cancellation observed: TimeoutError
lease setup exception: heartbeat task setup failed
lease setup warnings: ["coroutine '_heartbeat_loop' was never awaited"]
```

The probe uses task-creation failure injection, event-blocked callbacks and a
bounded watchdog; created orphan tasks are explicitly cancelled and joined.

## Proposed follow-up tasks

1. **AU-03-R1: pipeline lifecycle repair (P1)**. Own `src/gunz_utils/pipeline.py`
   and focused pipeline regression additions in a separately assigned test file.
   Combine F1/F2 in one worker to prevent overlapping edits. Put complete setup
   under ownership cleanup, retain successfully created tasks incrementally,
   close any rejected coroutine, and propagate child cancellation through a
   terminal signal/supervised task completion. Verify task-factory failure at
   producer/first/later worker, no warnings/orphans, worker and producer
   self-cancellation, caller cancellation, early close, bounded queues, and
   simultaneous failure/completion. Preserve original cancellation signal.
2. **AU-03-R2: lease unsubmitted-coroutine cleanup (P2)**. Own
   `src/gunz_utils/leases.py` and its lease setup test in
   `tests/test_core/test_a1_algorithm_audit.py`. Remove coroutine.close() from
   fault injection so production owns cleanup. Verify original failure survives,
   no RuntimeWarning, operation cancelled/joined, Future support and lease-loss
   simultaneous precedence unchanged. Coordinate shared test-file ownership if
   R1 uses a new test file; the two source fixes are independent.
3. **AU-03-R3: contract/proof expansion (P2)**. After lifecycle repairs, add
   event-driven cache/breaker histories and repeated cleanup cancellation probes;
   explicitly document cache invalidation/in-flight limits and cooperative
   cancellation/deadline semantics. Coordinate DAG/graph overlaps with AU-05.
4. **AU-06 reconciliation dependency**. Update ALG-022/ALG-056 evidence and
   record uncovered lifecycle cases only after repair checks actually execute.
   Changelog fragments for user-visible repairs and applicable Ruff/mypy,
   pytest/docs/full canonical gate remain required before integration.

Initial review is complete; confirmed defects remain **unrepaired**. Full
implementation completion requires applicable repository gates and evidence
reconciliation; a completed review alone does not satisfy it.


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
