# AU-04: Native acceleration semantics and memory safety

**Date:** 2026-10-08
**Role:** Audit researcher
**Status:** Done — initial review; scoped repair results recorded below
**Priority:** P2
**Parent:** [Audit follow-up](2026-10-08-audit-follow-up.md)
**Baseline:** `80bde76a641ce4577574fde60ec957251aee2ba0` plus existing dirty tree

## Scope and contracts

Reviewed all of `native/src/_accel.c`, `native/include/gunz_utils_native.h`,
`scripts/build_native.py`, `binary.py`, `serialization.py`, `buffers.py`, relevant
streaming buffer operations, acceleration specs/design, focused tests, and
canonical CI/native build routing. Parent shared execution contract and the
repository methodology apply; source/tests remained read-only.

- Varint encoder: integer range 0..2**64-1, canonical 1..10 byte encoding.
  Bool and ordinary IntEnum currently work in both modes. Negative/overflow
  integer errors are ValueError. Decoder consumes at most 10 bytes and commits
  reader offset only after success; short inputs raise EOFError and invalid
  canonicality/overflow raises ValueError. Codec work/space is O(1).
- ByteReader casts buffers to byte-oriented contiguous memoryviews. Native
  wrapper acquires Py_buffer, bounds offset before pointer arithmetic, and
  releases views before returning or raising. Successful bytes_read is bounded
  by available length, making final offset addition safe. Default operation
  retains the GIL; simultaneous buffer resizing is not permitted while a view
  is exported. This review does not certify third-party malicious exporters.
- JSON accelerator recognizes exact builtin primitives/containers; subclasses
  and custom objects return false for Python normalization. Default traversal
  depth is 100; cycles reach the same ValueError depth guard as fallback.
  Nonfinite numbers and bytes are rejected. Clean input identity sharing is
  explicitly documented and tested, so native-return aliasing is an accepted
  limitation, not a new parity defect. Work is proportional to visited edges;
  repeated/shared subgraphs are not deduplicated.
- Depth is a Python-callable parameter (`is_json_clean(obj, max_depth)` and
  `to_jsonable(..., _max_depth=...)`); no input domain or safe upper bound is
  validated beyond C int conversion. Large-depth behavior matters separately
  from safe default use.

## Confirmed findings

### AU04-F1 — Expanded depth permits native stack exhaustion (medium, conditional)

**Location:** `native/src/_accel.c:68-121, 123-138`;
`serialization.py:22-44`.
Recursive C traversal has no `Py_EnterRecursiveCall`/leave guard or iterative
stack. With a cyclic builtin list and `_max_depth=100000`, the native mode
terminates a child interpreter with signal 11, whereas fallback returns a
catchable RecursionError. Reproduction sets the child stack limit to 1 MiB,
disables core dumps, and has a 5-second timeout. Same subprocess setting and
input are used for both modes. This is a confirmed availability and semantic
parity defect when callers expand the configured depth. Default depth 100 is
bounded and existing cycle/depth tests pass; no default-depth crash was shown.
Use guarded or iterative traversal; define finite nonboolean integer bounds
for depth and keep native/fallback error semantics consistent. Do not describe
this result as exploitable by ordinary fixed-depth JSON input alone.

### AU04-F2 — Integer-subclass encoding semantics differ (low)

**Location:** `native/src/_accel.c:142-170`; `binary.py:74-90`.
An int subclass with overridden `__lt__` can raise fallback range rejection
while native PyLong conversion encodes its numeric value. Concrete synthetic
`IntSub(3)` with `__lt__` always true returns b'\x03' in native mode and raises
ValueError in fallback. The API annotation accepts int; subclass handling is
not explicitly narrowed. Invalid ordinary input types raise TypeError in both
modes but messages differ. Negative and overflow builtin int messages match.
Define/coerce the common integer domain before dispatch or explicitly reject
custom subclasses in both modes; add domain/parity tests. No memory violation
or incorrect ordinary uint64 encoding was demonstrated.

## Confirmed verification gap and packaging inspection

- **Canonical native execution gap:** `.github/workflows/ci.yml`,
  `scripts/ci.py`, and `scripts/audit_ci.py` never build the extension.
  `test_native_extension_is_compiled_and_active` skips when absent; the 21
  native varint differential cases also skip. Serialization tests named native
  differential do not require native presence and can compare fallback against
  fallback. A clean canonical checkout therefore does not enforce compiled
  coverage. Executed absent-mode focused suite reproduced all 22 native skips.
- **Distribution build-support gap (inspection only):** pyproject sdist include
  is restricted to `src/`; native C/header and scripts/build_native.py are
  outside it. No hatch native build hook exists; wheel configuration is plain
  src package inclusion. This matches compiler-optional import/install but
  means distributed sdist lacks the repo's optional native rebuild support.
  Decide whether that support is an intended distributable contract. Artifact
  contents were not built/inspected: hatchling is absent in this environment.
- `scripts/build_native.py` always writes into src and offers no output-directory
  option; audit compiled with an equivalent explicit GCC invocation into tmp.
  Windows command lacks explicit Python import-library linkage and macOS/Windows
  paths were not executed; portability is a pending proof, not a confirmed bug.
- No ASan/UBSan, Python 3.12 native build, wheel tag inspection, multi-platform
  build, or complete aggregate gate executed. No audit-level promotion applies.

## Executed evidence

Environment: Python 3.11.14, pytest 9.0.2; GCC
`(Ubuntu 13.3.0-6ubuntu2~24.04.1) 13.3.0`, Linux x86_64 CPython.
The environment's pytest is below maintained CI pin 9.0.3; cryptography 49.0.0
is below maintained >=50.0.1, although these selected codec/serialization tests
exercise no crypto. Environment is focused local evidence, not canonical-gate
certification. No dependency installation or network activity occurred.

```bash
/home/adhisant/tmp/miniforge3/envs/gunz-utils/bin/python tmp/au04/build_and_test.py
/home/adhisant/tmp/miniforge3/envs/gunz-utils/bin/python -m pytest -q \
  tests/test_core/test_binary_accel.py tests/test_core/test_serialization.py \
  tests/test_core/test_native_benchmark_mechanisms.py
/home/adhisant/tmp/miniforge3/envs/gunz-utils/bin/python tmp/au04/native_tests.py
/home/adhisant/tmp/miniforge3/envs/gunz-utils/bin/python tmp/au04/probes.py
```

- Compile: GCC `-O2 -g -shared -fPIC -Wall -Wextra`, installed Python include,
  C source path, output solely `tmp/au04/_accel.cpython-311-x86_64-linux-gnu.so`.
  Successful; warnings are unused wrapper self parameters and partial module
  struct initializer, not diagnosed unsafe arithmetic.
- Native absent: **35 passed, 22 skipped, 25 subtests passed**, 2.99 s.
- Native present: **57 passed, zero skipped, 25 subtests passed**, 0.96 s.
  Both suites show one expected benchmark deprecation warning. Temporary native
  runner adds tmp extension location to package path and reloads dispatch modules,
  then asserts both binary and serialization acceleration are active before tests.
  An initial runner failed the active assertion because root eager imports had
  already cached fallback; it was corrected by reload, not counted as native proof.
- Decoder differential: exhaustive all bytes strings of length 0, 1, and 2,
  plus 5,000 seeded random strings of length 1..12: **70,793 cases, zero
  differences** in value/error type/message and post-call reader offset.
- Ordinary/nonfinite and subtype JSON cases: float subclass, IntEnum, StrEnum,
  list subclass, dict subclass retain equal results or exception behavior.
- Direct native strided view raises BufferError rather than reading unchecked
  noncontiguous bytes. Public ByteReader cast rejects noncontiguous buffers in
  both modes. Native offset -1/1/2 for one-byte input raises EOFError, 0 succeeds,
  2**100 raises OverflowError from ssize_t conversion. Externally mutated reader
  offset domain/parity is not fully proved.
- Corrected depth subprocess: native returncode **-11**; fallback returncode
  **0**, prints RecursionError. Earlier probe before reload exercised fallback
  twice; only the corrected native-active run supports the finding.
- Build backend check: `ImportError` for hatchling; no artifacts built or
  packaging completion claimed.

Temporary runners/probes reside only under ignored `tmp/au04`. Narrow escalated
local execution was used because sandbox bwrap loopback initialization failed
in this session. No source, tests, release metadata, registry, or shared index
was edited by this worker.

## Proposed repair ownership and regressions

1. **AU04-R1, P2, native/serialization owner:** own `_accel.c` recursion guards
   and shared serialization depth validation. Coordinate with AU-05's graph/
   input bounds owner before touching serialization. Add child-process native
   crash regression, cyclic and deep acyclic inputs, valid depth boundary,
   boolean/noninteger/negative/large depth domains, native/fallback parity.
2. **AU04-R2, P3, codec owner:** `binary.py` and `_accel.c` integer domain
   agreement. Same native owner or sequence after R1; custom int subclass,
   bool/IntEnum, uint64 boundaries, invalid types, exact errors as specified.
3. **AU04-R3, P2, CI/build owner:** add an output-dir option to build_native.py;
   run an asserted native-present focused/full pass and an explicitly absent
   fallback pass through the existing canonical dispatcher, without creating
   duplicate hosted workflows. Cover Python 3.11/3.12 ABI separation and zero
   native-test skips in the required native leg. Coordinate packaging changes
   with AU-06; keep source/wheel contamination controlled.
4. **AU04-R4, pending contract decision:** package optional native source/build
   support if intended; inspect actual wheel/sdist contents/tags and verify
   compiler-free installation/fallback. Platform link commands and sanitizers
   require additional environment-backed execution, not source-only claims.

## Acceptance

- [x] Scoped source/test inventory, contracts, and domains reviewed.
- [x] Confirmed findings separated from evidence gaps and limitations.
- [x] Native-present and native-absent execution, skips, and triggers recorded.
- [x] Owned repairs and coordination dependencies proposed.
- [x] Findings sent to coordinator.
- [ ] Implementation repair, sanitizer/platform proofs, canonical verification.

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
