# RP-02: Coroutine ownership and cancellation cleanup

**Status:** Complete for stated Linux audit/repair scope; follow-ups recorded
**Parent:** [Parallel repairs](2026-10-08-resource-security-repairs.md)
**Findings:** [RS-01](2026-10-08-resource-lifetime.md)

Own `src/gunz_utils/concurrency.py`, `src/gunz_utils/cache.py`,
`tests/test_core/test_resource_lifetime_audit.py`, this record and a unique fixed
fragment. Preserve prior subprocess/pipeline/DAG changes; those sources are read-only.

Close consumed/generated coroutines when task submission fails in gather/map and
cache-owned producers. Drain owned children through repeated cancellation so
cooperative asynchronous finalizers can release descriptors. Reuse compatible
existing ownership/draining patterns; preserve original errors, cancellation,
bounded concurrency, ordering and SingleFlight/TTL sharing semantics.

- [x] Six strict failing regressions and seven positive lifetime proofs pass.
- [x] Focused cache/concurrency/cancellation suites pass on both Pythons.
- [x] Ruff/mypy, fragment and retained-resource limitations recorded.
- [x] Root integration gate complete.


## Implementation and preserved ownership contracts

Explicit user authorization for parallel repairs applied. Source changes are
limited to concurrency.py/cache.py; pipeline/DAG/subprocess and other owners'
production files are untouched. Work remains on the existing audit branch with
all user/prior changes preserved; no commit, install or external action occurred.

Every consumed/generated scheduler coroutine and internal cache producer/worker
is retained until create_task accepts it. Submission failure closes the rejected
coroutine before task entry publication and preserves the initiating error. Cache
keys, TTL/size policy, per-key sharing and shielding of producers from waiter
cancellation remain unchanged.

One private concurrency _cancel_and_drain helper cancels each live owned child
once, shields one gather until cooperative finalization completes and returns any
additional caller cancellation. Both public schedulers preserve the initiating
worker error/original cancellation. For explicit async-generator close,
GeneratorExit is an internal close request; a new cancellation received while
closing is propagated after child cleanup instead of silently swallowed.
No public export, dependency, broad refactor or timeout API was added.

Retained limits: cleanup waits for cooperative callbacks; Python cannot force
arbitrary cancellation-resistant coroutine finalizers to finish. Ordered gather
retains O(n) results by contract. Cache maxsize bounds stored results, not distinct
in-flight producers, and cache_clear does not fence running publication. Caller-
held tasks/results/tracebacks can intentionally retain payloads.

## Strict and positive regression evidence

All original13 lifetime cases pass (previously6 failed/7 passed). Added3 bounded
cases test worker-failure identity through cleanup cancellation for each helper,
and explicit iterator-close cancellation after fd release. Original repeated-
cancellation regressions also now require the initiating cancellation message.
The old rejection/descriptor failures were not skipped, xfailed or weakened.

Focused suites also retain ordinary/failure concurrency bounds, result ordering,
return_exceptions cancellation semantics, iterator-close cleanup, TTL method
binding/eviction, SingleFlight sharing and prior algorithm/lifecycle proofs.
Weakref/GC/task/fd positive evidence stays finite and synthetic; no RSS-only claim.

Pinned Python3.11.14/Python3.12.13, pytest9.0.3, Ruff0.14.10/mypy1.19.1:

```bash
PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 /tmp/gunz-utils-audit-20261008/bin/python -m pytest -q tests/test_core/test_resource_lifetime_audit.py tests/test_core/test_cache.py tests/test_core/test_concurrency.py tests/test_core/test_audit_pipeline_lifecycle_regressions.py tests/test_core/test_a1_algorithm_audit.py tests/test_core/test_a1_algorithm_proofs.py
# 101 passed,7 subtests passed in0.90s; no skips/warnings
PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 /tmp/gunz-utils-audit-20261008-py312/bin/python -m pytest -q tests/test_core/test_resource_lifetime_audit.py tests/test_core/test_cache.py tests/test_core/test_concurrency.py tests/test_core/test_audit_pipeline_lifecycle_regressions.py tests/test_core/test_a1_algorithm_audit.py tests/test_core/test_a1_algorithm_proofs.py
# 101 passed,7 subtests passed in1.49s; no skips/warnings
ruff check src/gunz_utils/concurrency.py src/gunz_utils/cache.py tests/test_core/test_resource_lifetime_audit.py
# All checks passed
mypy --cache-dir tmp/rp02-mypy src/gunz_utils/concurrency.py src/gunz_utils/cache.py tests/test_core/test_resource_lifetime_audit.py
# Success: no issues found in3 source files
git diff --check
# Passed
```

Initial type inference in the added two-API precedence case required an explicit
Future[Any] annotation; corrected without ignores or behavior changes. Final
executable source/tests are frozen for root integration. Unique fixed fragment:
changes/20261008-coroutine-resource-cleanup.fixed.md. Root owns registry/standalone
SingleFlight family reconciliation and full canonical/native/fallback harness
execution; no unsupported A4/full-platform claim is made here.

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
