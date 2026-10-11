# Remote audit: concurrency

Status: complete for scoped local review
Parent: [Integration task](2026-10-11-remote-audit-repairs.md)
Checkout: /tmp/gunz-utils-fix-audit-20261011-672bfb1

## Ownership
Production: concurrency.py and cache.py. Add dedicated tests without editing the shared existing
20261011 regression module. Update this task with evidence. Root owns shared docs.

## Scope
Process replay, iterator effects, worker allocation, parameter domains, finite close latency, cache generations, cancellation and loop ownership.
Reproduce before repairing; inspect maintained contracts and existing tests.
Use narrow compatible changes. Explicitly document unresolved contract choices.
Run focused pytest and Ruff, report commands and results. Do not commit or publish.

## Evidence
Pending agent review.

## Confirmed defects and focused repairs

Baseline independent regression execution on Python 3.11: **6 failed, 3 passed**
(0.54s). Six strict assertions exposed three defects:

- `process_imap` requested 128 automatic workers for nine finite inputs under an
  injected CPU-count oracle. The automatic branch now performs finite CPU-sized
  lookahead, then bounds worker count by available input (concurrency.py:400).
  Explicit worker requests remain authoritative; their existing input-consumption
  regression is preserved. No arbitrary hard worker limit was introduced.
- Valid thresholds `sys.maxsize` and `sys.maxsize + 1` failed on empty input due
  to `islice`'s platform-sized stop domain. `_take` (concurrency.py:231) uses
  finite `range`/`next` iteration and stops on input exhaustion; it also replaces
  window slicing so large configured chunk/window sizes do not overflow.
- `process_map` accepted negative, bool and noninteger thresholds, inconsistent
  with `process_imap`, and consumed input before option validation. Threshold
  validation (concurrency.py:296) and other option checks now precede iterator
  consumption, including empty workloads.

No cache algorithm repair was warranted. Cache/SingleFlight code changes document
one-live-event-loop ownership and preserve generation invalidation and shielded
producer semantics; the requested mechanical style pass preserves the AST.

## Independent positive proofs and resource limits

Dedicated file: `tests/test_core/test_remote_concurrency_audit.py` (**14 cases**).
Actual finite two-worker process-map and iterator-map failures record exactly one
acknowledged call per input and never replay serially. Separate subprocess tests
terminate a worker using `os._exit(23)` and assert `BrokenProcessPool`, exactly one
acknowledged call per input and parent survival, within an independent six-second
outer watchdog. Input failure after initial prefix propagates before an incomplete
submission window executes. Existing serial/unpicklable-fallback, ordered results,
iterator effects, repeat cancellation and rejected coroutine proofs remain strict.

A controlled old/new cache generation plus cancelled-waiter proof shows that old
producers cannot overwrite the fresh cache entry. Actual independent threads each
run their own asyncio loop: both TTL cache and SingleFlight reject sharing a pending
Task across loops (`RuntimeError: different loop`), while the original producer
completes after a finite release signal. Concurrent cross-loop use is an explicit
unsupported contract, not a memory leak. Sequential reuse without pending work is
not given an unconditional multi-loop guarantee.

`process_map` intentionally materializes its input. `process_imap` initial lookahead
is bounded by the configured threshold plus one and, for automatic workers, detected
CPU count; submitted windows are bounded by `2 * workers * (chunksize or 1)`. Caller
configuration can still select large budgets. Executor shutdown/iterator close waits
for already-running calls and has no deadline for arbitrary blocking user code.
These limits are now documented in the source docstrings, rather than represented
as hard memory or kill guarantees.

A single finite comparative observation on this Linux host used 1,000 ordered `abs`
inputs, two actual workers and threshold zero. Main: 0.0202s, 716145 peak traced parent
bytes; feature: 0.2525s, 156643 peak traced parent bytes. This reports the finite-window
memory/throughput tradeoff, not a stable benchmark or total worker RSS claim. It has
no timing assertion. Scratch main reference: `tmp/remote-concurrency/main_concurrency.py`.

## Final executed verification

With absolute worktree `PYTHONPATH` and `PYTEST_DISABLE_PLUGIN_AUTOLOAD=1`:

```text
python -m pytest -q tests/test_core/test_remote_concurrency_audit.py
  tests/test_core/test_audit_regressions_20261011.py tests/test_core/test_cache.py
  tests/test_core/test_concurrency.py tests/test_core/test_resource_lifetime_audit.py
Python 3.11: 70 passed, 11 subtests passed in 0.94s
Python 3.12: 70 passed, 11 subtests passed in 0.96s
```

Pinned Ruff passed for concurrency.py, cache.py and the dedicated new test file.
Pinned mypy: success, no issues in these three files. `gunz_style.cli` on the same
three files (`--jobs 1 --no-cache`): zero violations and warnings. Mechanical style
edits were checked with `ast.dump` equality before application. `git diff --check`
passed. No edits to main, shared existing tests, registry or package configuration;
no installs, commits, push, remote jobs or public disclosure. Root owns release
fragment/shared integration/full-gate acceptance. Assigned executable files are frozen.

## Integration follow-up: multiprocessing encoder parity

Root's full-suite gate exposed an inherited branch blocker: the unchanged strict
static security contract rejects direct `pickle` imports. Local primary-source
inspection of Python 3.11 `multiprocessing.reduction.ForkingPickler` showed its
dispatch table includes multiprocessing-specific registered reducers, so ordinary
encoding was also an incorrect preflight oracle. Two new real-worker proofs failed
before repair: a callable whose ordinary reducer rejects encoding but whose registered
multiprocessing reducer succeeds incorrectly took the serial path (parent PID).

Both helpers now call `ForkingPickler.dumps` directly. The explicit `_pickle` import
contains only the standard-library `PicklingError` exception type, as approved by the
coordinator; there is no serialization API import alias, dynamic import or decoder.
Fallback is documented and restricted to `PicklingError`, `AttributeError`, and
`TypeError` raised before execution. Resource errors, recursion errors, arbitrary
reducer RuntimeError, KeyboardInterrupt and asyncio cancellation propagate unchanged.
Worker/pool failures after execution never cause serial replay.

Added tests exercise both actual registered-reducer worker paths, the six resource/
signal exception identities for each mapper, the three accepted encoding rejections
for each mapper, and an independent AST check forbidding direct pickle imports,
non-exception `_pickle` imports and load/loads/Unpickler references. The existing
static security tests remain unchanged. Dedicated suite now contains **35 cases**.

Final focused command extends the previous five-file pytest matrix with
`tests/test_core/test_security_static_contracts.py`: **95 passed, 11 subtests passed**
on Python 3.11 (1.39s) and Python 3.12 (1.40s), no skips. Scoped Ruff and mypy on
concurrency.py plus the dedicated test module passed; gunz-style scanned both with
zero violations/warnings. `git diff --check` passed. Final test annotation correction
is type-only. Source and tests are frozen again; root must rerun invalidated full
integration gates before approval/commit.


## Coordinator integration
All six canonical local gates pass on the frozen corrected snapshot; see the
[completed parent](2026-10-11-remote-audit-repairs.md) and its source fingerprint.
