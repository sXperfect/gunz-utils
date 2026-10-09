# RS-03: Parser, binary and optional C safety/lifetime

**Date:** 2026-10-08
**Status:** Complete for stated Linux audit/repair scope; follow-ups recorded
**Parent:** [Resource/security audit](2026-10-08-resource-security-audit.md)
**Baseline:** `a3f224ba5b14fe98b4f41833c9a73f297754a3af` plus current verified
platform/async repairs and preserved user edits
**Branch:** `audit/native-platforms-20261008`

## Inventory and maintained evidence reviewed

Reviewed all of `serialization.py`, `binary.py`, `native/src/_accel.c`, and
`native/include/gunz_utils_native.h`; current registry ALG-012/076/077 and linked
AR-10/11 native recursion/subclass/activation proof obligations; existing binary,
serialization and native safety tests; optional native verifier/build support.
Prior AGENTS, SECURITY and canonical audit methodology remain applicable.
ALG-032 canonical conversion and ALG-077 streaming batching have overlapping
budget obligations; current depth/native proofs do not certify byte/item budgets.

Only tracked writes: this child record and new
`tests/test_core/test_parser_native_resource_audit.py`. Production source,
shared registry/index, CI, archived records and release/export edits remained
read-only. No external disclosure or production input was used.

## Contracts, allocation bounds and source ownership review

### Binary codec and reader — ALG-012/076

Canonical uint64 encoding accepts 0..2**64-1 and produces at most ten bytes.
Decoding inspects at most ten bytes, rejects truncated/noncanonical/overflow
encodings, and only commits offset after success. Fixed-width C shifts remain
0..63; the tenth byte is bounded before shifting. Python arithmetic cannot
wrap, and the C wrapper validates signed offset against buffer length before
pointer arithmetic. Successful offset+bytes_read cannot exceed Py_ssize_t buffer
length. Caller mutation of public reader offset beyond its typed domain is not
certified by these tests.

`binary.py:29-30,37-46`: ByteReader intentionally retains a byte-oriented
memoryview and read slices alias the original exporter. Small slices can keep
an entire caller buffer alive. This is observable zero-copy ownership, not a
leak; release/delete all views to permit resize/deallocation. No mandatory
close/context API is promised.

`_accel.c:207-236`: PyObject_GetBuffer failure has no acquired view to release;
all acquired-buffer validation/decode paths release before Python result
allocation. Noncontiguous views are rejected, not walked as contiguous memory.
`_accel.c:238-254`: temporary PyLong refs are decremented on offset/tuple
allocation failure and stolen into the result tuple on success. `_accel.c:173-181`
releases imported module/encoder refs in integer-subclass delegation. JSON list/
dict children use borrowed references while the GIL is retained, with balanced
recursion accounting and no heap traversal cache. Native stack depth remains
bounded independently at the existing 128 fast-path cutoff, then reference
fallback; default depth 100 and earlier 3.12 crash proofs remain covered.

No missing decref, unreleased acquired Py_buffer, invalid ordinary arithmetic,
or new default-depth crash was established in source review and executed finite
workloads. Result-allocation failure branches are source-inspected; no destructive
OOM/failing-allocator experiment was performed. Raw C header functions require
valid caller pointers/capacity; arbitrary native pointer misuse is not a Python
input trust boundary.

### Serialization — ALG-032/077

Default normalization depth 100 bounds recursive nesting, not total input bytes,
container width, or expanded graph nodes. Work/allocation depends on visited
edges and produced output. A compact caller-owned shared Python DAG can expand
when reference normalization duplicates containers; the finite proof below
uses only ten levels and 1,024 leaves, under a 2 MB traced peak ceiling.
A decoded JSON tree cannot encode these shared aliases compactly by itself.

`json_loads` delegates to standard json.loads; it has no byte/item/time budget
and preserves standard nonfinite decode behavior. `canonical_json` rejects the
nonfinite values on encoding. Neither helper declares an input-size sandbox;
applications handling untrusted transport documents must bound bytes/items at
their ingress. Width/shared-DAG amplification is a caller-budget limitation,
not evidence of unreachable retained resources or an existing size-limit bypass.
Native clean-input return aliasing is expressly documented and intentional;
mutation isolation requires caller copying. Custom Python objects/Mapping methods
execute caller code by design and are not equivalent to passive decoded JSON.

## Confirmed finding RS03-F1 — Python depth budget narrowed to C int (low)

**Locations:** `serialization.py:22-26,35-36`; `_accel.c:142-145`.

`to_jsonable` exposes a typed Python-int `_max_depth` with no documented signed
C-int bound, and the native/reference equivalence contract requires consistent
values/exceptions. Passing a one-leaf synthetic dict and the finite integer
2147483648 produces native OverflowError from PyArg_ParseTuple("i"), whereas the
reference returns the valid dict. With -2147483649, native raises OverflowError
while reference raises the documented depth ValueError. Both cases reproduce
on actual isolated native Python 3.11 and 3.12 builds.

This is a compatibility/parameter-domain defect on an explicitly supplied depth
budget, not a memory corruption/leak or default-depth exploit. The parameter is
an implementation-style underscore keyword, so severity remains low; the existing
helper tests already exercise that keyword and no C-int range is documented.
A merely large allowed budget must not change behavior solely with acceleration.

**Strict regressions:**
`test_depth_integer_budget_has_native_reference_exception_parity` has both finite
boundary cases. They remain failing on the unmodified native implementation;
no xfail, suppression, or assertion relaxation was added to conceal the defect.
Source fixes await coordinator assignment.

**Proposed focused repair:** retain reference depth semantics and the 128 native
optimization boundary by using Python fallback for native depth conversion
overflow, or normalize only the classifier's optimization budget while checking
negative depth semantics in Python first. Do not catch unrelated policy/depth/
bytes errors or introduce an arbitrary new public maximum. Own serialization
and dedicated regression cases in one follow-up; native C changes only if direct
classifier argument-domain policy is intentionally changed. Run all four backend/
interpreter legs and the canonical gate before claiming repaired parity.

## Finite lifetime and allocation evidence

Twenty dedicated cases, nine requiring explicit native availability:

- backend provenance checks when matrix requests native/fallback; native module
  source is asserted under isolated tmp and has_accel/hook presence is checked;
- failed decoder rollback, reader-held resize prohibition, buffer weakref release
  after deleting reader, and read-view retention until explicit release;
- direct C decode EOF/noncanonical/overflow/negative/end/huge-offset exception
  export release, proven by immediate bytearray resize after 32 calls per case;
- native success repeated 128 times and strided-view failure export cleanup;
- warmup plus 256-call clean JSON/cycle/subclass-exception workload: input
  reference counts restore exactly after GC; no retained caller reference found;
- ten-level shared DAG expands to exactly 1,024 leaves under 2 MB traced peak;
- warmup/GC plus 128 finite normalization calls on eight small records: live
  retained tracemalloc delta remains below 16 KiB, rather than using allocator
  RSS as leak evidence;
- standard decoder nonfinite handling and encoder rejection classification;
- two newly confirmed signed-C-int depth-budget parity failures.

Weakref/export tests show intended live ownership separately from release.
Allocation thresholds bound the experiment; they are not production quotas or
proof against all workloads. C allocator/refcount instrumentation, sanitizers,
free-threaded CPython, alternative exporters and arbitrary native pointer inputs
remain outside executed evidence. No large fuzz corpus or indefinite process
was created.

## Execution and provenance

Installed pinned environments: Python 3.11.14 and Python 3.12.13, pytest 9.0.3,
Ruff 0.14.10, mypy 1.19.1. Linux x86_64 only. `tmp/rs03/matrix.py` imports existing
`scripts/verify_native.py`, appends only the new resource audit test path to its
in-memory TESTS tuple, and invokes each mode with RS03_EXPECT_NATIVE=0/1 plus
PYTEST_DISABLE_PLUGIN_AUTOLOAD=1. Existing verifier creates isolated source copies,
asserts dispatch/import origin before each leg, compiles using the matching
interpreter headers/ABI suffix, and runs each child command with finite timeout.
The tracked verifier/build scripts are unchanged; no extension exists in src.

```bash
/tmp/gunz-utils-audit-20261008/bin/python tmp/rs03/matrix.py
/tmp/gunz-utils-audit-20261008-py312/bin/python tmp/rs03/matrix.py
/tmp/gunz-utils-audit-20261008/bin/ruff check \
  tests/test_core/test_parser_native_resource_audit.py
/tmp/gunz-utils-audit-20261008/bin/python -m mypy \
  tests/test_core/test_parser_native_resource_audit.py
```

| Final 77-case matrix | Fallback | Asserted compiled native |
|---|---|---|
| Python 3.11.14 | 46 passed, 31 explicit native-only skips, 2.74 s | 75 passed, **2 confirmed failures**, 1.39 s |
| Python 3.12.13 | 46 passed, 31 explicit native-only skips, 2.67 s | 75 passed, **2 confirmed failures**, 0.65 s |

All final failures are the same two RS03-F1 boundary cases. The initial 75-case
matrix before adding them passed every native case on both versions; this is
lifetime/refcount evidence, not repaired-depth parity. Nine resource-specific
native skips plus 22 existing native differential skips are expected in the
asserted fallback leg; zero skips occurred in native legs. Pinned Ruff passes;
mypy succeeds in one source file.

No complete full gate or A3/A4 promotion is claimed. Native present means actual
compiled C on Linux, not a Windows/macOS kernel proof. No package installs,
remote host operations, commit/publish or external report performed. Narrow
escalated local tools were required because sandbox bwrap loopback initialization
fails in this session.

## Acceptance and follow-up

- [x] Python/C contracts, source ownership and prior proofs reviewed.
- [x] Finite exception/export/refcount/weakref/allocation evidence on both versions.
- [x] Confirmed parity defect separated from caller budgets/intentional aliases.
- [x] Exact source locations, strict regression and narrow repair proposed.
- [x] Coordinator assigns RS03-F1 source repair and full integration checks.
- [x] Registry reconciliation reflects current passing/failing proof, not stale A4.

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
