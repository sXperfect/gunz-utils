# NP-04: Async subprocess exit and pipe-draining deadline

**Date:** 2026-10-08
**Status:** Verified on Linux and macOS; real Windows host pending
**Parent:** [Native platform verification](2026-10-08-platform-verification.md)
**Base:** `a3f224ba5b14fe98b4f41833c9a73f297754a3af` plus shared platform work/user edits
**Owner scope:** `src/gunz_utils/subprocess.py`, dedicated
`tests/test_core/test_audit_async_drain_regressions.py`, this record and unique
fixed fragment. Shared registry/index, CI, other sources and user edits untouched.

## Confirmed concern and independent reproduction

Before repair, two finite in-process controlled-process/StreamReader regressions
failed on Python 3.11:

1. Process exit is acknowledged with returncode 0 while both pipe writers remain
   open. `_communicate_bounded(timeout=0.01)` remains pending after an independent
   0.15-second watchdog because only process.wait is timed, not subsequent drain.
2. Cancellation is delivered after the process-wait acknowledgment while the
   process has not exited. Controlled stop confirms exit, but cleanup remains
   pending after the same watchdog because it waits for unowned pipe EOF.

These are deterministic scheduling proofs with independent exit/EOF events,
not timing stress or simulated native kernels. The watchdog uses asyncio.wait,
which does not itself wait for canceled cleanup. Every test finally feeds finite
EOF, releases any controlled exit, cancels pending work once, and requires task
settlement within 0.3 seconds. No real child existed during the initial
reproduction; both failures were recorded before source changes and reported to
coordinator before implementation.

## Contract and repair

- Public async timeout includes process exit and capture drain **after creation**;
  configured termination grace is additional cleanup time. Python/OS process
  creation itself cannot be assumed interruptible. Timeout None permits normal
  unlimited-duration capture, but overflow/read failures still terminate promptly.
- A monotonic deadline covers the complete bounded capture task: process wait
  plus both pipe drains. A separate failure event detects output overflow or
  reader failure without waiting for a silent opposite pipe. Combined retained
  stdout/stderr bytes remain at most max_output_bytes; simultaneous overflow is
  reported as CommandOutputLimitError rather than unverified success.
- All created reader, capture, and failure-wait tasks have one owner. Partial task
  construction closes unstarted coroutine objects and cleans already-created
  tasks. Normal success drains both streams and cancels/joins only the unused
  failure watcher.
- Timeout, cancellation, overflow and reader/setup errors cancel/join owned
  tasks, close owned capture read-end transports, and stop/reap the child using
  the existing termination/group primitive. Pipe EOF can belong to an escaped
  descendant; the helper no longer needs that EOF to complete cleanup.
- Cleanup remains shielded and explicitly joined across repeated caller
  cancellation. A later cancellation still propagates after cleanup; no cleanup
  task is abandoned in the background. Existing no-output-limit successful
  capture is unchanged, and its timeout/cancellation path uses the same owned
  pipe closure/reap mechanism.
- StreamReader has no public close operation. The implementation closes its
  CPython `_transport` when present, validated against actual subprocess streams
  on the maintained Python 3.11/3.12 versions. Alternative event-loop/process
  implementations without that transport remain a portability limitation.
- Owned POSIX groups are signaled with the existing helper; escaped descendants
  are outside group ownership and remain caller responsibility. No arbitrary
  descendant discovery, stronger all-descendant kill promise, or Windows job
  object support is introduced. No-output-limit generic communicate failures
  beyond timeout/cancellation retain their existing behavior.

Expected space: retained output O(max_output_bytes), plus the existing asyncio
stream buffers; exactly two readers, one capture task and one failure watcher.
Failure cleanup uses one explicitly joined task. No polling threads, unbounded
queue, automatic retry, or new dependency/public API was added.

## Meaningful regression coverage

Fourteen dedicated cases cover:

- acknowledged exit with silent pipes and global deadline;
- cancellation while waiting for exit and no dependency on foreign EOF;
- exact shared six-byte cap success with/without a timeout;
- overflow with no timeout and a silent opposite pipe;
- read failure while exit/opposite pipe remain pending;
- repeated cancellation during acknowledged owned cleanup;
- failures constructing the second reader, capture task and failure watcher;
- no-output-limit timeout/cancellation pipe closure;
- finite real Python child timeout with/without a cap, non-None returncode,
  closed pipe transports, and POSIX waitpid proving the leader was reaped.

Controlled tests assert no unexpected live asyncio task remains. The real child
sleeps only 0.4 seconds, has a 0.8-second independent watchdog and bounded finally
cleanup; no indefinitely running or escaped real descendant is created. Existing
sync inherited-pipe, normal async timeout/cancellation/output, domain, algorithm
proof/audit and security-static contracts are included in focused validation.

## Re-audit and failure boundaries

Reviewed final source diff for timeout reset, output-cap allocation, exception
precedence, partial construction/coroutine ownership, unused failure watchers,
repeated cancellation and no-cap compatibility. The deadline is created before
capture task setup and not reset after leader exit. Reader exceptions wake the
failure path even before the leader exits. Closing read transports occurs only
on failure/cancellation; normal successful bytes are fully drained. Task creation
failures cannot leave an unstarted coroutine or already-created reader behind.
No cancellation is converted into a result. Capture failure does not produce a
successful CommandResult. The synchronous implementation remained unchanged.

Process reaping retains existing OS/helper semantics: termination grace is
bounded before escalation, while the final OS process reap is awaited. These
checks do not claim a finite kernel deadline for an unkillable OS process, nor
native macOS/Windows execution. The private StreamReader transport dependency is
explicitly version tested, not declared universal.

## Executed evidence

Linux x86_64 only. Pinned pytest 9.0.3, Ruff 0.14.10, mypy 1.19.1.

```bash
PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 /tmp/gunz-utils-audit-20261008/bin/python \
  -m pytest -q tests/test_core/test_audit_async_drain_regressions.py \
  tests/test_core/test_subprocess.py \
  tests/test_core/test_audit_subprocess_deadline_regressions.py \
  tests/test_core/test_a1_algorithm_proofs.py \
  tests/test_core/test_a1_algorithm_audit.py \
  tests/test_core/test_security_static_contracts.py
PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 /tmp/gunz-utils-audit-20261008-py312/bin/python \
  -m pytest -q tests/test_core/test_audit_async_drain_regressions.py \
  tests/test_core/test_subprocess.py \
  tests/test_core/test_audit_subprocess_deadline_regressions.py \
  tests/test_core/test_a1_algorithm_proofs.py \
  tests/test_core/test_a1_algorithm_audit.py \
  tests/test_core/test_security_static_contracts.py
/tmp/gunz-utils-audit-20261008/bin/ruff check \
  src/gunz_utils/subprocess.py tests/test_core/test_audit_async_drain_regressions.py
/tmp/gunz-utils-audit-20261008/bin/python -m mypy \
  src/gunz_utils/subprocess.py tests/test_core/test_audit_async_drain_regressions.py
```

Final Python 3.11.14: **92 passed, 14 subtests passed, 2.17 s**.
Final Python 3.12.13: **92 passed, 14 subtests passed, 1.76 s**.
No skips. Pinned Ruff passes; mypy succeeds in two source files. Initial typing
issues in test coroutine annotations/introspection were corrected without
suppressions. Unique fixed fragment records the behavior change.

No source-external installations, remote execution, native-host claim,
commit/publish, shared registry/index edit or archived-record writes performed.
Narrow escalated local tools were used due to sandbox bwrap loopback initialization
failure. Root owns combined full gates, ALG-039 reconciliation and native runs.

## Acceptance

- [x] Concern reproduced with bounded independent evidence before repair.
- [x] Focused typed repair, meaningful regressions and fixed fragment implemented.
- [x] Cancellation, output cap, setup ownership and process reaping checked.
- [x] Both supported Python versions and pinned focused static checks pass.
- [x] Combined canonical gate/ALG-039 update — coordinator verified.
- [x] Actual macOS evidence — verified on Darwin 25.6.0 arm64 across Python 3.11 and 3.12 (34 passed, 14 subtests passed, 0 skipped).
- [ ] Actual Windows evidence — native Windows runner access pending.

## Coordinator integration

All six canonical aggregate gates passed on the integrated source: release,
Ruff/mypy, Python 3.11 tests, strict Sphinx, packaging isolation and Python 3.12
compatibility. Each main suite passed 1,370 tests with 29 documented skips;
compiled-native proofs passed 57 on each interpreter. Summary:
`tmp/platform-integrated-ci-summary.json`.

The platform verifier includes all 14 dedicated async drain cases; its subprocess
phase passed 34 tests on each version. Fresh stable-source JSON:
`tmp/np03/integrated-linux-platform-evidence.json`. It reports preparation complete,
unchanged source and native-platform completion false. ALG-039/GAP-009 now records
the repaired deadline and retained transport/reap/platform limits. User edits were
preserved; no commit, push, release or native-host execution was performed.

## Native macOS execution

Executed on Darwin 25.6.0 arm64 across Python 3.11.16 and Python 3.12.15:
- `tests/test_core/test_audit_async_drain_regressions.py`
- `tests/test_core/test_subprocess.py`
- `tests/test_core/test_audit_subprocess_deadline_regressions.py`

Result: **34 passed, 14 subtests passed in 1.07s (Python 3.11)** and **34 passed, 14 subtests passed in 0.99s (Python 3.12)** with zero skips and zero failures.
`scripts/verify_platform.py --platform macos` subprocess phase: **passed (complete=True)**.

