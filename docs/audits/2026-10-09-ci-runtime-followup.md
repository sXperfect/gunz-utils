# CI and runtime follow-up audit — 2026-10-09

## Scope and baseline

This focused audit follows the fake-clock regression correction on
`fix/ci-rate-limiter-clock@a44731baaa04ad81394feae3f8edd16e01043aaa`.
The repository's `main` was
`80bde76a641ce4577574fde60ec957251aee2ba0`.

Reviewed areas: retry deadlines, token-bucket numerical validation, Linux process
profiling, local/hosted test dispatch, import-origin checks, packaging isolation,
and pull-request packaging selection. This is not an exhaustive audit of all
package subsystems or a claim of exact OS resource accounting.

The method follows the [algorithm audit guide](../guides/algorithm-correctness-audit.md)
and [method audit protocol](../design/audit/algorithm-method-audit.md).

## Confirmed findings and corrections

| ID | Finding and consequence | Correction / evidence |
|---|---|---|
| RT-01 | All six retry paths checked time before `on_retry`, then slept using a stale budget. A 2 s hook could still be followed by a 1 s sleep under a 1.5 s timeout. | Recheck the complete requested delay after the callback; preserve the last exception/result without sleeping when it no longer fits. |
| RT-02 | Post-sleep retry checks accepted equality with the deadline, starting an attempt with zero remaining time. | Require positive remaining time before another attempt; cover exact equality and oversleep separately. |
| RT-03 | Token validation rounded a request before comparing capacity, but later arithmetic used the original integer. Capacity `2**53` incorrectly accepted request `2**53 + 1`, allowing a zero-delay retry loop. | Compare the original request to capacity, then consistently use its normalized float value. Exact integer oracles cover rejection and valid paired requests. |
| RT-04 | Huge integer timing/token parameters raised `OverflowError` while attempting float conversion instead of failing validation. | Check finite representable bounds before conversion; retain `ValueError`, positive/nonnegative domains, and boolean rejection. |
| PROC-01 | A container's process IDs can differ from the IDs exposed by its procfs mount. Looking up the local child PID could select an unrelated outer process or yield no samples. | Compare `/proc/self/stat` to `os.getpid()` before launching and before a direct snapshot; reject unavailable or mismatched procfs with `NotImplementedError`. |
| PROC-02 | Sampling failure cleanup targeted only the root; descendants could survive, and a signaling race could replace the original interruption. | Launch an owned POSIX session, reuse process-group termination, attempt a bounded root reap, and preserve the original exception with type-only cleanup notes. |
| PROC-03 | Strict text decoding silently omitted valid processes whose command name contained non-UTF-8 bytes. | Decode proc stat records with `surrogateescape`; verify preserved command bytes, process membership, threads, and RSS. |
| PROC-04 | Incomplete private-memory rollups were reported as zero or a partial sum. | Report `None` unless both private-memory fields are available; retain a measured zero when both are present and zero. |
| CI-01 | Clearing `PYTHONPATH` did not clear pytest's `pythonpath = ["src"]`. Isolation tests could pass against a good checkout despite a bad installed artifact. | Pass `-o pythonpath=` to stdlib/extra pytest runners. Regression fixtures deliberately disagree between source and installed copies. |
| CI-02 | The wheel/sdist gate built both archives but only installed and checked the wheel. | Independently install the sdist in a fresh environment with cache reuse disabled; validate external import origin and `py.typed` for both artifacts. |
| CI-03 | String-prefix origin checks accepted sibling paths, traversal, and symlink escapes. Compatibility verification also bypassed the canonical test dispatcher. | Use resolved path containment and route compatibility through `ci.py test`. Regressions execute the actual child import guard. |
| CI-04 | Nine dispatcher tests under `scripts/tests/` were absent from canonical `testpaths = ["tests"]`. | Move them to `tests/test_core/test_ci_cli.py` so both supported interpreter suites collect them. |
| CI-05 | PR packaging selection considered optional integrations but omitted core imports, `py.typed`, isolation tests, and other artifact inputs. | Include all `src/`, `scripts/`, `tests/`, workflows, metadata, README/license, and ignore configuration in packaging selection. Execute the workflow's classifier against representative paths. |

## Timing and token-bucket proof packet

Families: **ALG-014** and **ALG-021**. Risk: incorrect rate admission, unnecessary
work after deadline exhaustion, and nontermination at large numerical values.

### Contract and parameter domains

| Parameter | Accepted domain / units | Boundary semantics |
|---|---|---|
| Limiter rate/capacity/request | Positive `int` or `float` representable as a finite float; tokens or tokens/s | Reject bool, NaN, infinity, out-of-range integers, zero, negatives, and requests above stored capacity before mutation. |
| Limiter timeout | `None` or finite nonnegative representable seconds | Zero retains immediate acquisition behavior; positive timeout retains the existing limiter boundary semantics. |
| Retry attempts | Positive integer, excluding bool | At most the configured number of operation calls. |
| Retry delays/overrides | Finite nonnegative representable seconds | Zero is allowed; an override may return `None` to request the configured policy. |
| Retry timeout | `None` or finite nonnegative representable seconds | Initial attempt remains permitted at zero; subsequent waits must fit, and another attempt requires positive remaining time after sleep. |

Retry timeouts decide whether additional waits/attempts may begin. They do not
preempt a running operation or synchronous callback. Callback, predicate, and
delay-override execution time counts against the available retry budget.
Exception paths preserve the original failure; result paths preserve the last
result. Async cancellation propagates. Explicit broad exception-policy behavior
for `KeyboardInterrupt` and `SystemExit` is unchanged.

The independent oracle is a fixed timeline: a 1 s backoff under a 1.5 s budget
cannot follow a callback consuming 0.75 s or more. Exact integer arithmetic
proves `2**53 + 1 > 2**53` before float normalization. Tests cover positive
remaining budget, exhausted budget, exact deadline, oversleep, zero timeout,
finite extremes, invalid domains, and absence of state mutation on rejection.

Complexity remains O(attempts) time and O(1) auxiliary space for retries, excluding
caller work. Limiter operations retain O(1) state and per-iteration work; requests
above capacity are rejected before entering the wait loop. This does not add an
arbitrary-precision token accounting API.

Evidence: `tests/test_core/test_deadline_regressions.py` plus the existing retry,
resilience, acquisition-context, and numerical-contract suites. Focused execution
passed on Python 3.11.17 and 3.12.14: **155 tests and 75 subtests** per interpreter.
Twenty-seven actual new test cases failed against the pre-change implementation
loaded into memory, covering all six adapters and numerical boundary failures.
Mocks replace local module references and preserve the event loop's real clock.

## Process profiling proof packet

Families: **ALG-044** and **ALG-045**. Risk: sampling the wrong process, silently
omitting observed processes, fabricating known memory values, or leaking work
after cancellation.

The profiler accepts structured executable arguments, finite positive sampling
intervals, a positive integer detailed-memory cadence, and the existing
`rss`/`pss`/`full` modes. It requires readable Linux procfs in the caller's PID
namespace. Rejection occurs before subprocess creation. Observations remain
sampled snapshots with stable PID order, optional unknown-memory fields, and no
fabricated empty tail after process exit.

A deterministic procfs fixture supplies independently specified root, child, and
unrelated process records. Known byte strings, fixed page counts, and complete
versus incomplete rollups are the measurement oracle. A mismatch fixture proves
that an unsupported procfs view launches no command.

On sampling failure, cancellation, or other interruption, the profiler sends
SIGKILL to the POSIX process group it created and attempts to reap the root with a
1 s bound. Cleanup errors do not replace the original exception or copy arbitrary
exception text into notes. A real parent/grandchild regression uses pipe EOF to
prove group termination without depending on procfs visibility. Mocked races
cover signaling failure, process exit, reap timeout, and original exception
identity.

This changes failure cleanup from root-only graceful termination to immediate
termination of the owned group. Commands now run in a new POSIX session, so
interactive controlling-terminal assumptions are not preserved. Normal completion
still follows the root command; descendants that create another session are
outside the failure cleanup group.

The snapshot implementation still scans P procfs entries and expands their parent
relationships; worst-case expansion is O(P²), with O(P) snapshot space. S retained
snapshots require space proportional to the retained observations. This audit adds
constant-sized procfs identity checks, not a bounded-retention or event-stream API.

Focused evidence: **34 passed, 6 capability skips, 48 subtests passed** on each
supported interpreter, including all 18 new regressions. Native test capability
guards cover six actual procfs-dependent integration cases; mocked and process-group
regressions remain active.

### Why local integration tests previously failed

The local probe observed `os.getpid() == 5` while `/proc/self/stat` reported
`16512`, with `NSpid: 16512 5`. Its child reported local PID 6 but procfs PID
16513. Earlier `/proc/6` reads could therefore accidentally refer to an unrelated
outer process. This establishes a namespace mismatch rather than a general lack
of permission or merely a short-lived-command timing problem.

The capability guard skips only real integration cases requiring compatible
procfs, with a diagnostic. Compatible Linux hosted runners still execute them.
Before the correction, the same five failures reproduced on unchanged `main`.

## CI verification proof packet

Risk: successful verification of the wrong source/artifact, omitted tests, and
inappropriately skipped packaging checks. Inputs are repository paths, executable
paths, gate names, and normal subprocess exit statuses. Containment uses resolved
filesystem relationships. Failures propagate through the canonical dispatcher;
aggregate verification retains independent failures instead of replacing them
with a later successful suite.

Regression tests create conflicting source and installed packages, execute pytest
under the original `pythonpath` configuration, exercise failing sdist installation
and missing-marker cases, and invoke the workflow's actual shell classifier.
These are observable behavior tests rather than copies of expected command lists.
The nine existing dispatcher tests are now collected normally.

Focused CI evidence: **53 passed** on each interpreter. New CI and classifier
regressions produced **22 expected failures** against baseline scripts/workflow.
The workflow's main-only push and PR-to-main triggers, action pins, read-only
permissions, concurrency cancellation, timeout, and retention settings are retained.

## Focused reproduction commands

Run these selections from the repository root. Each command below passed with
Python 3.11; the identical selection also passed using
`tmp/ci-venv-py312/bin/python`.

```bash
tmp/ci-venv-py311/bin/python -m pytest \
  tests/test_core/test_deadline_regressions.py \
  tests/test_core/test_resilience_next.py \
  tests/test_core/test_retry.py \
  tests/test_core/test_retry_delay_override.py \
  tests/test_core/test_foundation_io_retry.py \
  tests/test_core/test_acquisition_context.py \
  tests/test_core/test_p0_resilience.py \
  tests/test_core/test_security_numeric_contracts.py -q

tmp/ci-venv-py311/bin/python -m pytest \
  tests/test_core/test_process_profile_regressions.py \
  tests/test_core/test_process_sampling.py \
  tests/test_core/test_benchmark.py \
  tests/test_core/test_deep_audit_round2.py \
  tests/test_core/test_deep_process_profile.py \
  tests/test_core/test_native_benchmark_mechanisms.py -q

tmp/ci-venv-py311/bin/python -m pytest \
  tests/test_core/test_ci_runner_regressions.py \
  tests/test_core/test_ci_cli.py \
  tests/test_core/test_ci_policy.py \
  tests/test_core/test_audit_ci.py -q
```

## Combined verification

Run the canonical aggregate verifier with both configured interpreters and the
full packaging matrix on the combined revision:

```bash
tmp/ci-venv-py311/bin/python scripts/audit_ci.py \
  --compat-python "$PWD/tmp/ci-venv-py312/bin/python" \
  --summary-json tmp/ci-summary.json
```

The aggregate verifier completed with exit code **0** on 2026-10-09. Its JSON
summary reports `passed: true` and exit code 0 for every gate:

| Gate | Combined result |
|---|---|
| Release metadata | Passed; the existing next-release fragment/version advisory remains non-failing. |
| Ruff and mypy | Passed; mypy checked 97 source files. |
| Python 3.11.17 | 1,272 passed, 28 skipped, one existing benchmark deprecation warning. |
| Strict Sphinx documentation | Passed. |
| Fresh packaging matrix | All eight cases passed: zero-dependency, stdlib, validation, project, observability, secure, plot, and wheel/sdist. |
| Python 3.12.14 compatibility | 1,272 passed, 28 skipped, the same deprecation warning. |

Each interpreter collected 1,300 cases: 137 new regressions and nine previously
uncollected dispatcher cases augment the prior 1,154. The 28 skips consist of the
existing 22 uncompiled native-extension cases and six procfs capability cases
described above. Every new deterministic regression and the real process-group
cleanup regression executed.

The installed-package subsets passed 19 stdlib, 14 validation, 11 project, four
observability (plus four subtests), and 64 secure tests. The plot case produced a
real headless image. Both built archives were independently installed in fresh
environments and imported from their own site-packages outside the checkout;
both retained `py.typed`. The sdist install rebuilt with cache reuse disabled.

The registry conservatively retains A3 for the reviewed families. This successful
local aggregate does not eliminate the documented capability and sampling limits
or substitute for a hosted run with matching procfs and process PID namespaces.

## Follow-up resolution: observed lifetime counters

GAP-009 was corrected on the same branch after the initial aggregate run.
The profiler now retains the greatest observed monotonic CPU, I/O, fault, and
context-switch counters for each Linux process identity keyed by
`(pid, start_time_ticks)`. A child that was sampled and later exits therefore
continues to contribute to final profile totals. If Linux reuses its numeric PID,
the different start time creates a separate lifetime and its counters are added
independently rather than merged with the earlier process.

The public `ProcessProfile` and `ProcessSample` schemas are unchanged. The
lifetime ledger is private implementation state; per-snapshot samples still report
the processes visible at that observation. Two deterministic regressions cover
PID reuse and a sequence where exited child lifetimes would previously have been
lost by maximum-snapshot aggregation. The focused reconstructed package execution
passed both regressions. A new full aggregate run is still required before
promoting this follow-up evidence beyond A3.

## Follow-up resolution: run-directory rollback

GAP-004 was also resolved in this follow-up. `save_run_directory` now tracks
artifact files created by the current publication attempt. If a later artifact
copy, artifact registration, or `run.json` publication fails, those newly created
files are removed in reverse order. Newly created empty `artifacts/` and run
directories are then removed when possible. Pre-existing artifacts and directories
are not deleted.

Rollback failures do not replace the initiating publication/copy error. Their
exception types are attached as notes instead, avoiding accidental disclosure of
arbitrary cleanup exception text. A partial-copy cleanup failure follows the same
rule. Regression coverage includes later-copy failure after an earlier successful
copy, preservation of a pre-existing artifact, outer rollback failure, and
partial-copy rollback failure.

This is transactional rollback for files created by one failed publication call;
it does not garbage-collect older unreferenced artifacts already present from
earlier successful calls.

## Follow-up resolution: durability and content-store publication

The filesystem durability distinction tracked as GAP-005 was already covered by
injected tests on this branch. A file-level `fsync` failure before `os.replace`
leaves the old target intact and removes the temporary file. A parent-directory
`fsync` failure after replacement raises while the new target remains visible,
because publication has already happened and only persistence of the directory
entry is uncertain. This is now treated as an explicit contract rather than an
unresolved atomicity promise.

GAP-006 was corrected by serializing cooperating content-store publishers with a
symlink-safe advisory lock in each fanout directory. The hard-link path and its
`os.replace` fallback now share the same publication critical section. A second
writer therefore rechecks and verifies the winning target instead of replacing it
after observing an earlier absence. The lock uses POSIX `flock` or Windows
`msvcrt.locking`; persistent lock files avoid inode-replacement races between
waiters. Deterministic concurrency coverage forces hard-link failure, blocks the
first fallback replacement, starts a second writer, and verifies that only one
replacement occurs.

The content-store guarantee remains scoped to cooperating writers using this
implementation. An unrelated process that ignores the advisory lock can still
race filesystem operations directly.

## Remaining limits and follow-up

- **Sampling:** short-lived descendants may start and exit between observations.
  Exact event-complete resource accounting remains outside this sampler's contract.
- **Wall time:** the reported duration includes observation and sleep overhead;
  it is not an independent OS-recorded command-exit timestamp.
- **Cleanup:** new-session descendants may escape the owned process group, and
  normal root completion does not imply all descendants have exited.
- **Coverage:** the audit does not establish repository-wide correctness or
  replace an actual hosted run on a compatible procfs environment.
