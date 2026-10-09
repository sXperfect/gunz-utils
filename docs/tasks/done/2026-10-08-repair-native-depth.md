# RP-03: Native/reference depth-budget parity

**Date:** 2026-10-08
**Status:** Complete for stated Linux audit/repair scope; follow-ups recorded
**Parent:** [Parallel repairs](2026-10-08-resource-security-repairs.md)
**Findings:** [RS-03](2026-10-08-parser-native-safety.md)
**Branch:** `audit/native-platforms-20261008`

## Ownership and contract

Changed only `src/gunz_utils/serialization.py`, existing
`tests/test_core/test_parser_native_resource_audit.py`, this record and unique
`changes/20261008-native-depth-budget-parity.fixed.md`. Native C/header/build and
maintained verifier sources remained read-only; coordinator owns verifier/index/
registry/full gates. All prior/user edits retained; no commit or public report.

The public normalization helper's Python-int depth budget must yield the same
values/errors with optional acceleration. Original RS-03 failures were finite
positive 2**31 (native OverflowError versus valid reference result) and negative
-2**31-1 (native OverflowError versus reference depth ValueError). Reproduced
strict tests were preserved and extended, never suppressed or weakened.

## Focused implementation

- Existing depth-exceeded check now runs with Python integer semantics before
  classifier dispatch, preserving negative-budget ValueError even below C-int
  minimum. Default recursive depth validation remains in every call.
- Only the native classifier's integer optimization budget is at most 129. Its
  existing traversal cutoff is 128; larger/deeper values cause its normal false
  return and Python normalization fallback. This ceiling is not a new public
  maximum: recursive calls retain the original `_max_depth`, including 2**100.
- Default budget 100 and existing classifier behavior for depth 128 remain
  unchanged. Non-integer argument-domain policy is not expanded; no blanket
  exception catch, dependency, retry or C implementation change was introduced.
- A native classifier's direct C-int argument domain remains its own internal
  wrapper contract. This repair targets the Python normalization dispatch.

The approach was sent to coordinator before editing and independently accepted.
The fixed optimization ceiling depends on the documented C fast-path cutoff;
new deep-value regressions will expose a future uncoordinated cutoff change.

## Regression and resource checks

RS-03 now has 34 dedicated cases. Strict parity tests span negative/zero/ordinary
budgets, 128/129 cutoff boundaries, C-int maximum and both overflow sides, plus
positive/negative 2**100. Two independent reference comparisons of 160-deep valid
inputs with huge budgets prove that native argument normalization imposes no new
public depth limit. Dispatch spies check default 100, 128 and huge-budget 129
optimization routing; a negative-budget spy forbids classifier invocation.

Existing immediate buffer-resize, weakref ownership/release, repeated native
input-reference count restoration, bounded tracemalloc retention, malformed
varint rollback, shared DAG allocation and native recursion/subclass proofs remain
strict and pass. No observed memory leak or reference/buffer regression arose.

## Actual backend/interpreter evidence

Pinned pytest 9.0.3, Ruff 0.14.10, mypy 1.19.1. Linux only; no native Windows/macOS
claim. Temporary `tmp/rs03/matrix.py` uses existing native verifier helpers,
deduplicates its in-memory test tuple against coordinator's maintained update,
and runs asserted fallback/native modes with RS03_EXPECT_NATIVE=0/1 and
PYTEST_DISABLE_PLUGIN_AUTOLOAD=1. Each mode verifies source origin and dispatch;
matching C artifacts build only into isolated tmp source copies with the actual
interpreter headers/ABI. Source package receives no extension artifact.

```bash
/tmp/gunz-utils-audit-20261008/bin/python tmp/rs03/matrix.py
/tmp/gunz-utils-audit-20261008-py312/bin/python tmp/rs03/matrix.py
/tmp/gunz-utils-audit-20261008/bin/ruff check \
  src/gunz_utils/serialization.py tests/test_core/test_parser_native_resource_audit.py
/tmp/gunz-utils-audit-20261008/bin/python -m mypy \
  src/gunz_utils/serialization.py tests/test_core/test_parser_native_resource_audit.py
```

| Interpreter | Asserted fallback | Actual asserted compiled native |
|---|---|---|
| Python 3.11.14 | 60 passed, 31 expected native-only skips, 1.65 s | 91 passed, zero skips, 0.79 s |
| Python 3.12.13 | 60 passed, 31 expected native-only skips, 1.00 s | 91 passed, zero skips, 0.59 s |

All two original boundary failures pass in both native legs. Fallback skips are
22 existing differential cases plus nine direct C resource cases; they do not
certify C execution. Compiled native legs execute all cases with zero skips.
Pinned Ruff passes; mypy succeeds in two source files. An initial E501 on the new
conditional line was fixed before final lint; no unrelated source formatting.

## Limits and re-audit

Reviewed Python/C dispatch ordering and preservation of the original recursive
budget. Negative-depth rejection occurs before any classifier conversion;
positive integer ceiling changes only bounded native optimization, not caller
value/resource budgets. All C buffer/refcount/recursion code is unchanged and its
existing evidence remains applicable with the stated Linux-only provenance.

Caller byte/width/DAG budgets, intentional returned aliases, direct classifier
C-int limits, arbitrary custom object behavior, sanitizer/allocator-failure
coverage and real OS portability remain as recorded in RS-03. The earlier
historical A4 ledger does not replace current integration evidence. Root owns
canonical full gate and maintained registry reconciliation.

## Acceptance

- [x] Strict positive/negative native parity failures repaired and retained.
- [x] Four actual compiled/fallback interpreter legs pass with activation checked.
- [x] Passing buffer/refcount/lifetime/allocation proof preserved.
- [x] Pinned Ruff/mypy and unique fixed fragment complete.
- [x] Root canonical integration gate and shared evidence reconciliation.

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
