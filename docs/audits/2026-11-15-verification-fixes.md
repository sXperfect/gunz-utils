# Utils implementation follow-up

Branch: `codex/utils-verification-fixes`, starting from local `main` at `436fcbd`.
This follows the merged utility additions and the earlier async cleanup repair.

## Implemented fixes

- `gather_with_concurrency` owns its semaphore-wrapper tasks, cancels and drains
  siblings on error or caller cancellation, and closes submitted coroutine
  objects that never started. It retains ordered results and support for
  general awaitables. Invalid concurrency limits close submitted coroutines
  before returning the validation error.
- `async_throttle` always executes its first call, including at clock zero.
  Only successful calls update the cached result and throttle timestamp.
  Non-finite and negative intervals are rejected before execution.
- Cleanup passes exception classes separately to `contextlib.suppress`.
  Passing a tuple previously raised `TypeError` while handling the intended
  exception. Signal restoration, lease exit, process-group cleanup and governor
  reads now exercise their intended exception paths.
- Lease exit shields background-task draining, waits for cleanup under caller
  cancellation, and then propagates that caller cancellation. The controlled
  cancellation regression failed before this repair. Unexpected heartbeat
  worker errors still propagate; expected lease loss is handled.
- Process metrics use the supported `itertools.pairwise` signature and correctly
  integrate RSS over sample intervals.
- L2 norms use `math.hypot`; general positive finite orders use magnitude
  scaling. Normalization and cosine calculations scale coordinates before
  reduction, including vectors whose unscaled norm exceeds float range.
  Dot products use compensated `math.fsum` reduction. Invalid norm orders are
  rejected even for empty vectors; zero-vector cosine remains zero.
- Execution-context defaults use an immutable empty mapping. Missing annotation
  imports and generic return annotations are repaired without bulk root exports.
- The native activation fixture now represents all current dispatch hooks;
  POSIX build tests retain the C11 and warning flags; project tests isolate and
  restore `sys.path`; strict JSON tests distinguish forbidden constants from
  numeric overflow. None of these repairs relaxes runtime validation.
- Ruff import/syntax findings and long lines are repaired. Safe signature,
  banner and comment fixes use gunz-style. Layout-only edits were checked for
  unchanged Python syntax trees; docstring wrapping preserves executable code.
  Four SQL forwarding warnings in fault-injection tests have documented,
  line-specific suppressions. Blanket rule exclusions were not added.
- Dataclass constructor field documentation avoids duplicate Sphinx entries.
- The optional C extension compiles after removing a duplicate local declaration;
  explicit module-definition fields remove the missing-initializer warning.
  The documented `scripts/verify.sh` entry point is now executable.

## Inputs, bounds and failure behavior

`gather_with_concurrency` accepts a positive integer concurrency limit, excluding
booleans, and a finite tuple of awaitables. Its active work is bounded by the
limit, but wrapper tasks and ordered results remain O(n), matching the earlier
eager API. This repair does not make it a streaming scheduler. Task cleanup is
cooperative; a worker that never completes cancellation can still delay return.
Awaitables already scheduled by the caller cannot be made concurrency-limited
retroactively. Unscheduled Future objects remain caller-owned; submitted
coroutine objects are consumed or closed by the helper.

Vector operations remain O(n). General norms scale intermediate powers into
[0, 1]. A mathematically unrepresentable final norm can still overflow; direction
calculations avoid requiring that norm. Invalid/non-finite coordinates are
rejected for normalization. Dot-product multiplication itself can overflow for
extreme inputs; compensated reduction does not provide arbitrary precision.

## Evidence

`tests/test_core/test_verification_fixes.py` checks scale invariance, a
cancellation-sensitive dot product with independent expected value, extreme
finite directions, invalid orders, failed and cancelled worker cleanup,
unstarted coroutine closure, startup throttling, lease exit, unsupported loop
signal removal, already-exited process groups, unreadable governor files and a
closed-form RSS integral. Existing tests check ordering and concurrency bounds.

| Final check | Result |
| --- | --- |
| Python 3.11 full suite | 2,340 passed, 55 skipped |
| Python 3.12 full suite, including async plugin coverage | 2,340 passed, 55 skipped |
| Forced fallback, on each interpreter | 114 passed, 48 native-only cases skipped |
| Asserted native activation, on each interpreter | 162 passed |
| Ruff, package-wide mypy, strict Sphinx, release metadata | Passed |
| Full optional-extras/package-isolation matrix | Passed |
| Rebuilt wheel/sdist installs and zero-dependency check after final lease fix | Passed |
| gunz-style | 0 errors, 220 advisory warnings; strict lint gate fails |

Each full pytest run has one expected legacy benchmark deprecation warning.
The final native builds emit no compiler warnings. Native Windows/macOS
execution is not claimed by a Linux run.

The first aggregate run exposed the duplicate C declaration. Its packaging
matrix passed. After the native and final lease fixes, the aggregate verifier
reran release, lint, both full test/native gates and strict docs, while fresh
wheel/sdist installs and zero-dependency isolation ran separately. Unchanged
optional-extra suites were not repeated. Logs are
`/tmp/gunz-utils-implementation-final-ci-20261115.log` and
`/tmp/gunz-utils-implementation-final-packaging.log`; machine results are in
`tmp/utils-implementation-final-ci-20261115.json` and
`tmp/utils-implementation-final-results-20261115.json`.

Remaining style advisories include exact-value comparisons, timeout/style
preferences, async construction checks and security heuristics. They have not
all been classified and must not all be called false positives. Strict lint
still fails because it treats advisories as errors. No blanket suppressions or
weaker checks were added. Evidence remains A3; historical A4 entries do not
certify this working tree.
