# Bounded async cleanup follow-up

This repair targets `gather_limited`, `map_concurrent`, and
`as_completed_limited`. The input domain, positive integer limit validation,
ordered gather results, and completion-order iterator results remain the same.
No dependency, public namespace export, or package version changes. Implementation
return annotations now express both list result variants consistently with the
existing overloads; the public overload signatures are unchanged.

## Reproduced failures

Six of seven initial regression tests failed before the repair:

- A lazy coroutine producer was advanced during cleanup after worker failure.
  Its exception replaced the original worker error.
- Failed mapping invoked factories for all remaining, unscheduled inputs.
- The completed-results iterator consumed the rest of a lazy source on failure.
- An input error during cleanup prevented cancellation/draining of owned tasks.
- Simultaneously completed sibling failures could become unobserved exceptions.
- Invalid coroutine input replaced the useful TypeError with an AttributeError
  from trying to call `.close()` on a non-coroutine value.

Tests use finite producers, event-controlled workers, and an independent
all-completed schedule. No infinite producer or unbounded live child is required.

## Repair and ownership

A shared private cleanup helper closes unused coroutine objects that are already
held by a sequence. It does not call next on a lazy producer. It closes the
producer iterator when that operation is supported, then drains all owned tasks.
Objects not yet yielded by a lazy producer remain caller-owned. Iterator-finalizer
errors cannot skip draining; an existing worker failure remains primary and gets
a note naming the secondary cleanup error type, without copying arbitrary error
text into diagnostics. Cancellation and process-exit signals are not returned as
ordinary results.

The completion iterator retains tasks returned by wait until each result has
been observed. Cleanup therefore includes both unfinished workers and completed
siblings that have not yet been yielded. Repeated caller cancellation uses the
existing shielded cancellation/drain primitive. A failed task creation closes an
actual coroutine without masking TypeError for other input types.

## Bounds and limits

At most `limit` tasks are owned at once. Iterator cleanup does not schedule or
produce new work. Cleanup of an already-created sequence is O(remaining items);
closing a lazy generator does not enumerate its future items. Gather still
retains O(n) result storage; the completion iterator retains O(limit) tasks.

Cleanup is cooperative: a user coroutine or iterator finalizer that never
returns can still delay completion. This change does not promise a hard deadline
for arbitrary user code. Callers should explicitly close async iterators when
stopping early. Arbitrary lazy iterators may hold precreated coroutine objects;
those objects are caller-owned until yielded and must be closed by their owner.

## Verification

The initial seven-test run had six failures and one pass. The first focused
post-repair run passed 67 tests. The completed nine-test regression file also
covers repeated cancellation and secondary iterator-finalizer failures.

| Check | Result |
| --- | --- |
| Python 3.11 focused selection, including async aliases | 77 passed |
| Python 3.12 standard-library concurrency selection | 69 passed |
| Dedicated regression file, Python 3.11 | 9 passed |
| Full Python 3.11 test gate with documented optional extras | 2,308 passed, 55 skipped, 6 failed |
| Same six failing cases with original concurrency code in an isolated process | Same six failures |
| Focused Ruff 0.14.10 | Passed |
| Focused mypy 1.19.1 with other modules followed silently | Passed in both changed Python files |
| Release metadata | Passed; older pending additions require a minor release |
| Optional-package import check | Concurrency imports no optional packages |

The six full-suite failures concern benchmark result loading, native activation,
POSIX compiler preparation (two parameter cases), and project-root handling (two
cases). Replacing only the in-process concurrency implementation with the saved
pre-edit source reproduced all six, without reverting files. They are separate
from this repair. Skips cover uncompiled native extensions and unavailable native
OS operations. No native Windows/macOS or compiled-extension verification is
claimed.

The aggregate local checker was also run with its documented packaging skip,
since metadata/build boundaries were unchanged. Release passed. Repo-wide Ruff
reported 434 findings, mypy reported 58 errors in other modules, and strict Sphinx
reported four duplicate `DeepDifference` field descriptions. The first full-test
attempt lacked GitPython; installing documented extras in a dedicated temporary
environment allowed the complete test run above. None of the shared environments
was reinstalled. Packaging and a complete Python 3.12 suite were not run.

This is focused A3 evidence for ALG-056. Historical A4 evidence in the registry
does not certify the current shared dirty tree. Existing edits were preserved;
the repair is on `codex/utils-lazy-async-cleanup`, without a commit or release.

Reproduction commands from the utils root, with Python 3.11/3.12 environments
that contain the appropriate tools:

```text
python -m pytest tests/test_core/test_async_cleanup_regressions.py tests/test_core/test_concurrency.py tests/test_core/test_wave4_subwave4_concurrency.py tests/test_core/test_remote_concurrency_audit.py tests/test_core/test_wave6_subwave8_async.py -q
python -m ruff check src/gunz_utils/concurrency.py tests/test_core/test_async_cleanup_regressions.py
python -m mypy --follow-imports=silent src/gunz_utils/concurrency.py tests/test_core/test_async_cleanup_regressions.py
python scripts/ci.py test
python scripts/audit_ci.py --skip-packaging --summary-json tmp/utils-async-cleanup-ci-20261115.json
```

The Python 3.12 focused run omits the pytest-asyncio-dependent final file and
uses the standard-library async tests instead. Local run logs are under
`/tmp/gunz-utils-cleanup-*20261115.log`, `/tmp/gunz-utils-full-tests-20261115.log`,
and `/tmp/gunz-utils-before-six-failures-20261115.log`. The original source snapshot
and repair-only diff are also in `/tmp`; they are not committed artifacts.
