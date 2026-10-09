# RS-01: Memory retention and resource lifetime

**Status:** Complete for stated Linux audit/repair scope; follow-ups recorded
**Parent:** [Resource/security audit](2026-10-08-resource-security-audit.md)

Review dag.py, pipeline.py, concurrency.py, cache.py, resources.py and the current
subprocess cleanup contract. Prioritize task/queue/reader cleanup, callbacks,
exception tracebacks, reusable coordinator state, iterator early exit, repeated
cancellation and bounded-cache eviction. Consult ALG-022/039/056, prior lifetime
repairs and documented escaped-descendant/process sampling limitations.

Own this task and `tests/test_core/test_resource_lifetime_audit.py` only; production
source and shared registry are read-only until coordinator assigns a confirmed fix.
Follow the parent contract. Record reviewed paths, contracts, finite reproduction,
GC/weakref/tracemalloc/task/fd evidence, deliberate retention and residual gaps.

- [x] Current source and earlier evidence reviewed.
- [x] Meaningful bounded lifetime cases executed on Python 3.11/3.12.
- [x] Findings and focused repair proposals delivered.


## Initial review and contracts

Reviewed current dag.py, pipeline.py, concurrency.py, cache.py, resources.py and
subprocess.py against maintained AGENTS/security/algorithm methodology and registry
ALG-022/039/056 plus current repair packets. Baseline HEADa3f224ba5b14fe98b4f41833c9a73f297754a3af,
branch audit/native-platforms-20261008 with preserved user edits and completed
platform/async work. Production source was read-only throughout this packet.

Owner contract: a coordinator owns coroutine/task submission once it consumes or
creates the coroutine; rejected submission should release that coroutine while
preserving the original failure. Owned-task cancellation/draining should allow
cooperative asynchronous cleanup to finish, including repeated caller cancellation.
Input iterators/resources not transferred into a documented ownership contract,
caller-retained results/tasks/exceptions, and running shielded cache producers
remain separately caller-owned/intentional retention.

Added tests/test_core/test_resource_lifetime_audit.py:13 finite cases, using weak
references/GC, live task sets, native coroutine-frame closure, real descriptors
and actual Linux descriptor inventories. Payloads are8x1KiB per cache proof,
3 same-key SingleFlight callers,12 pipeline items/2 workers/queue1,2 DAG stages,
4 group iterations and4 ordinary child runs per sync/async mode. Event waits and
joins have1s/2s bounds; failed-probe coroutine/fd cleanup occurs in finally. No RSS
heuristic, huge allocation, indefinite children, external stores or secrets.

## Confirmed findings

### RS01-F1 — rejected consumed coroutine stays open (low)

concurrency.py:35 and:99 submit consumed/generated work without retaining and
closing the coroutine when asyncio.create_task raises. Both strict submission
regressions preserve original RuntimeError, then observe non-None cr_frame.
The probe explicitly closes the rejected coroutine afterward, preventing test
leak/warning contamination. Exceptional task-factory/allocation failure is needed;
no live task was created. This is coroutine-frame/payload lifetime and unawaited
warning cleanup, not proof of a permanently reachable coordinator heap leak.

### RS01-F2 — repeat caller cancellation interrupts owned fd cleanup (medium)

concurrency.py:59-63 and:115-119 cancel children, then await an unshielded gather.
An actual child is paused in asynchronous finally cleanup before os.close on a
synthetic file descriptor. Repeating cancellation of the caller propagates another
cancel into that drain, aborting the child's cleanup; os.fstat still succeeds
although all tasks terminated. Probe closes the descriptor afterward. This is a
realistic cooperative async cleanup path; actor/resource acquisition and every
wait are finite. Existing pipeline/DAG protected drains already preserve cleanup
under this schedule, but the older concurrency helpers do not.

Remediation: cancel owned tasks once, shield and finish a single owned drain across
repeated caller cancellations, preserving initiating cancellation/failure. Retain
cooperative-callback limits; do not invent forceful task termination or a new public
timeout API. Verify iterator failure, early close, simultaneous completion/failure,
ordering/return_exceptions, and cancellation signals using existing concurrency
suites plus these fd regressions.

### RS01-F3 — rejected internal cache producer coroutine stays open (low)

cache.py:215 async_ttl_cache and:277 SingleFlight create an internal producer/worker
coroutine inline without closing it on task submission failure. The2 strict cases
observe open native coroutine frames after the original refusal propagates. These
frames can retain captured arguments until discarded/collected and emit never-
awaited warnings. No permanent in-flight registry entry or running task is created
in this schedule. Capture the fresh coroutine explicitly and close it if task
submission rejects, before publishing any task entry; preserve original error.

## Positive evidence and accepted limits

Seven passing cases confirm: synchronous and asynchronous TTL/LRU caches retain
only2 of8 synthetic payloads at maxsize2, and clear releases them all; SingleFlight
releases completed producer payloads after canceled caller references are dropped;
pipeline early close releases queued/yielded payloads and tasks; canceled DAG
compensation releases completed output; reused sync/async ResourceGroup exit stacks
release callbacks/payloads; repeated ordinary sync/async subprocess runs return to
actual Linux fd baselines after event-loop/child-watcher warmup.

The initial SingleFlight weakref probe still held its last canceled caller Task
through a loop variable; that Task's traceback legitimately retained producer
state. Dropping the caller-owned variable made the test pass. No library fix or
weakened lifetime expectation was used; this illustrates why retained diagnostics/
Task objects are not automatically coordinator leaks.

TTL is eligibility/lookup expiry rather than a background destruction clock.
Async cache/SingleFlight distinct-key in-flight work is not bounded by retained
maxsize and survives waiter cancellation until producer completion; callers must
bound admission/operation lifetime. Cache clear does not fence already-running
producer publication. DAG rollback_timeout can report rollback_unfinished while
an explicitly cancellation-resistant compensation remains active; that documented
limit is distinct from cooperative cleanup being recanceled. Input iterators
are not promised ownership transfer. ResourceGroup uses stdlib exit-stack rules;
callback behavior is caller-defined. Windows/macOS reader/kernel lifetimes and
escaped descendants retain their documented limitations; Linux ordinary fd success
cannot certify those absent platforms.

## Executed pre-repair evidence

Pinned Python3.11.14/Python3.12.13, pytest9.0.3, Ruff0.14.10/mypy1.19.1:

```bash
ruff check tests/test_core/test_resource_lifetime_audit.py
# All checks passed
mypy --cache-dir tmp/rs01-mypy tests/test_core/test_resource_lifetime_audit.py
# Success: no issues found in1 source file
PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 /tmp/gunz-utils-audit-20261008/bin/python -m pytest -q --tb=no tests/test_core/test_resource_lifetime_audit.py
# 6 failed,7 passed in0.24s; strict defects above, no skipped/xfail cases
PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 /tmp/gunz-utils-audit-20261008-py312/bin/python -m pytest -q --tb=no tests/test_core/test_resource_lifetime_audit.py
# 6 failed,7 passed in0.57s; same strict defects, no skipped/xfail cases
```

Temporary finite diagnostic script tmp/rs01/probe.py independently printed both
rejected coroutine frames open and both descriptor cleanups incomplete with zero
pending tasks. It cleaned all opened resources. No source changes, commits,
public disclosure, installs or remote/hosted jobs. Registry/index/full gate and
repair assignment remain coordinator-owned; red regressions are kept strict and
this review does not promote A3/A4.

## Assigned repair proposal for coordinator

One concurrency/cache owner can fix concurrency.py submission/draining and
cache.py producer submission without overlapping RS02/RS03 secure/native owners.
Extend the existing dedicated lifetime tests rather than suppressing the6 red
cases; retain all7 positive GC/fd proofs. Add a unique fixed fragment for user-
visible cleanup and reconcile ALG-025/056 against executed repaired revision.
Run focused cache/concurrency/lifecycle suites on both interpreters, Ruff/mypy,
and coordinator canonical gate before any completion or level promotion. Current
review is complete; production source remains unchanged and defects unrepaired.

Standalone SingleFlight has no explicit registry row in the current ledger;
coordinator should assign it a family/proof link rather than assuming TTL entries
certify all standalone coalescing lifecycle behavior.

## Coordinator completion and retained limits

The three focused repair packets passed. Independent SecureStore review moved
policy/generation verification inside SQLite write exclusion; deterministic raw
writer probes cover owned and joined transactions. Original failing regressions
remain strict and pass. Prior failed audit evidence above is historical prepatch
evidence and must not be presented as a current source failure.

All six canonical gates passed: release, Ruff/mypy, full Python tests, strict
Sphinx, packaging isolation and Python 3.12 compatibility. JSON summary:
`tmp/resource-security-integrated-ci-summary.json`. Python 3.11 collected before
four final verifier exclusion regressions were added: 1,440 passed, 38 documented
skips. Python 3.12 collected the final tests: 1,444 passed, 38 skips. The final
41-case verifier suite also passed separately on BOTH versions, and final
Ruff/mypy/release reruns passed. No earlier result was rewritten to change counts.
Compiled-native proof suites pass 91 per version; fallback passes 60 with 31
explicit native-only exclusions. The maintained native gate now retains RS-03.

Stable-source harness JSON:
`tmp/np03/resource-security-linux-platform-evidence.json`. Both interpreters
pass 18 filesystem, 75 secure-store, 34 subprocess, 60 fallback and 91 native
cases. Only the fallback phases have 31 exactly matched expected exclusions;
zero unexplained gaps. Report status prepared, complete/source_unchanged true,
native_platform_complete false. Fingerprint (236 files, SHA-256):
`503ec4a63120b5817a37604248162a5de9ab71de87b18b150ba61ba08bd5d521`.
The first evidence runner was interrupted to integrate exact new native-only
fallback exclusions; the final run is the completed stable-source evidence.

Registry families ALG-025/050/056/077 and new scoped ALG-079 ownership evidence
are reconciled; historical levels are not blanket-promoted. Fixed key/salt input
admission is tracked separately in
[the pending task](../pending/2026-10-08-fixed-key-input-admission.md).
Real Windows/macOS execution, hostile roots, authenticated whole-snapshot
freshness, arbitrary caller payload budgets and sanitizer/allocator-failure
proofs remain outside this completed Linux repair scope. No leak-free or
security-certification claim follows from finite probes. Existing user edits
are preserved; no commit, push, release, remote execution or public report.
