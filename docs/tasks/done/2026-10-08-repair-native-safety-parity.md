# AR-10: Native recursion safety and integer-subclass parity

**Date:** 2026-10-08
**Status:** Done — scoped repair and final integration verified
**Priority:** P1/P2
**Parent:** [Audit follow-up](2026-10-08-audit-follow-up.md)
**Evidence:** [AU-04 findings F1/F2](2026-10-08-audit-native-acceleration.md)

## Ownership and approach

Own `native/src/_accel.c`, binary/serialization dispatch only when necessary,
and dedicated native safety/parity regressions. Coordinate Python depth-domain
behavior with AU-05. Use Python C-API recursion protection or a bounded iterative
implementation; validate expanded depth so cyclic input raises safely rather
than exhausting native stack. Preserve the pure-Python reference's integer
subclass semantics, or use fallback for non-exact builtin integers.

## Regression checks

- Expanded-depth cyclic and deeply nested objects must raise a controlled
  exception in isolated native-present and fallback child processes.
- Default-depth valid objects and boundary behavior remain equivalent.
- Int subclasses with overridden arithmetic/comparison and ordinary uint64
  boundary values have matching results or documented exception behavior.
- Run compiled-present tests with asserted native activation and zero unexpected
  skips, plus native-absent fallback tests. Preserve decoder differential proofs.

The confirmed crash uses an expanded `_max_depth=100000` and constrained child
stack. No default-depth exploit was demonstrated. Preserve this condition in
severity and regression documentation. Temporary compiled artifacts belong in
ignored task directories; do not overwrite source-tree artifacts during review.

## Acceptance

- [x] Exclusive source/test ownership assigned before editing.
- [x] Safe exception behavior and parity regressions pass.
- [x] Applicable lint/type/docs checks and repaired-tree full gate pass.
- [x] Changelog fragment and actual revision-specific evidence recorded.

Implemented in `native/src/_accel.c`; Python dispatch and serialization source
were unchanged. Native validator wraps each recursive visit with balanced
`Py_EnterRecursiveCall` / `Py_LeaveRecursiveCall`, including all error paths.
Expanded/cyclic traversal now raises RecursionError using the interpreter's
recursion limit. The existing default maximum depth still raises ValueError.
Native varint encoder delegates non-exact int subclasses to the existing
`binary._py_encode_uvarint`, retaining overridden arithmetic/comparison behavior;
exact builtin integers and bool retain the direct C path. Temporary import and
call references are released on success/failure. Unique fixed fragment added.

Dedicated tests: `tests/test_core/test_audit_native_safety_regressions.py` covers
custom comparison/arithmetic integer subclasses, default-depth cycles/valid
objects, and native/fallback active-backend child processes for cyclic and
3,000-deep objects with `_max_depth=100000`. Child core dumps disabled, stack
limited to 1 MiB, 10-second subprocess timeout, and continued use after caught
RecursionError checked. No native test in this dedicated module skips; it tests
the actual active backend and the AR-11 matrix forces both modes.

Verification environment: `/tmp/gunz-utils-audit-20261008/bin/python`, Python
3.11.14, pytest 9.0.3, Ruff 0.14.10. GCC 13.3.0 compiled into ignored tmp/au04
using `-O2 -g -shared -fPIC -Wall -Wextra`; only existing unused self/partial
module initializer warnings. No source-tree extension installed.

Commands/results:

- Forced absent focused dedicated/binary/serialization pytest: **34 passed,
  22 expected native differential skips, 6 subtests passed**, 0.45 seconds.
- `.../bin/python tmp/au04/native_tests.py` asserts binary/serialization native
  hooks after loading tmp extension and module reload: **56 passed, zero skips,
  6 subtests passed**, 0.26 seconds across the same three modules.
- `.../bin/python tmp/au04/probes.py`: prior 70,793-case decoder differential
  oracle and isolated crash reproduction rerun; details recorded below.
- Pinned Ruff on dedicated native safety regressions passes. C reviewed manually
  for balanced recursion accounting and reference ownership. No Python source
  typing changed; broader mypy/gates belong to integration.

The crash was conditional on expanded depth; no default-depth exploit was
claimed. Extremely raised interpreter recursion limits or unusually tiny stacks
remain interpreter/application configuration limits, as with pure Python.
No sanitizer, Windows/macOS, Python 3.12, or full canonical gate claim is made.
CI enforcement and distribution verification belong to AR-11; that owner was
notified when C and dedicated tests stabilized. No commits or external disclosure.


Final probe results: 70,793 decoder cases retain zero native/reference mismatches.
The original expanded-cycle reproducer now exits 0 and prints RecursionError in
both native and fallback modes; integer-subclass range rejection now matches.
Ordinary JSON subtype/error probes retain parity. With the coordinator's backend
installed and AR-11 packaging edits visible, tmp probe builds additionally showed
sdist contains the native C/header and build script; wheel contains no _accel
artifact. Those shared packaging edits are owned and fully verified by AR-11,
not claimed as this task's independent packaging gate.

### Python 3.12 integration correction

Full compatibility verification revealed that C-API recursion accounting alone
was insufficient on CPython 3.12.13: under the original 1 MiB expanded-depth child
probe, the cyclic object still segfaulted (-11), while the 3,000-deep acyclic
object completed rather than reaching Python reference recursion behavior.
The crash assertion was retained; this was a source safety failure, not merely
an incorrect exception expectation.

Native traversal now has an independent depth-128 fast-path budget, checked
before another recursive descent. Crossing it returns false to the existing
Python normalization reference; this is an optimization boundary, not a public
maximum-depth rejection. Default maximum depth 100 retains native validation.
Py_EnterRecursiveCall/Py_LeaveRecursiveCall remain balanced. A new 200-deep valid
input oracle verifies that deeper permitted inputs still normalize successfully
through reference fallback.

Executed `scripts/verify_native.py --mode all` using pinned pytest 9.0.3:

| Interpreter | Asserted fallback | Asserted compiled native |
|---|---|---|
| Python 3.11.14 | 35 passed, 22 expected native skips, 0.26 s | 57 passed, zero skips, 0.27 s |
| Python 3.12.13 | 35 passed, 22 expected native skips, 0.32 s | 57 passed, zero skips, 0.31 s |

Both native-version cycle and deep child processes now catch RecursionError,
exit 0, and continue serializing a valid object. Dedicated regression Ruff check
passes. Compilation remained isolated under ignored temporary source copies.
The earlier 56-test evidence predates the added valid-input fallback oracle.

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
