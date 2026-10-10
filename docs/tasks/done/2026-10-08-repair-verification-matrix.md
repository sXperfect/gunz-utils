# AR-11: Enforce native and source-distribution verification

**Date:** 2026-10-08
**Status:** Done — scoped repair and final integration verified
**Priority:** P2
**Parent:** [Audit follow-up](2026-10-08-audit-follow-up.md)
**Evidence:** [AU-04](2026-10-08-audit-native-acceleration.md) and
[AU-06](2026-10-08-audit-packaging-evidence.md)

## Ownership and scope

Own existing canonical `scripts/ci.py`/`scripts/audit_ci.py`/workflow gates,
native test activation assertions, packaging metadata and isolation contract
tests. Preserve the single hosted job and main/PR-to-main triggers. Coordinate
with AR-10; do not add duplicate workflows or a mandatory compiler dependency.

## Approach and verification

1. Explicitly exercise native-present and native-absent modes where the build
   platform supports compilation. Assert actual extension activation before
   differential tests so fallback cannot compare against itself unnoticed.
2. Build an sdist, unpack/build/install it in isolation, and verify advertised
   distribution contents, zero-dependency imports, and `py.typed`. Decide whether
   optional C sources/build support must ship; inspect built artifacts before
   changing metadata. The current exclusion is inspection evidence, not an
   executed sdist-build failure.
3. Validate Python 3.11/3.12 with maintained tool/dependency versions. Record
   unsupported platform proofs and missing tools rather than silently skipping.
4. Reconcile registry claims and task states after coordinated repairs using
   actual revision-specific evidence. Do not blanket-promote historical A4.

## Acceptance

- [x] Native mode tests cannot silently exercise fallback twice.
- [x] Sdist install/build roundtrip and optional compilation behavior verified.
- [x] Missing compiler preserves pure-Python installation.
- [x] Canonical full gate and available compatibility checks pass.
- [x] Source artifact and API ownership claims match actual package behavior.

## Implementation

The existing test gate runs the full suite and then scripts/verify_native.py.
The new runner copies the package into a unique ignored temporary source tree,
excluding compiled libraries/caches. Its first interpreter verifies all dispatch
hooks are absent, then runs the binary/serialization/native safety suites. The
second compiles C into that temporary package and requires all three native
hooks to be active before running the same suites. Import origin is checked;
compiler/activation/test failures are explicit nonzero outcomes, not skips.
The script cleans its temporary tree and never creates src/gunz_utils/_accel.
Standalone --mode fallback/native supports focused investigations.

scripts/build_native.py adds a backward-compatible --output-dir option.
Python 3.12 compatibility invokes the same test gate, so its native build uses
that interpreter's ABI. Hosted triggers, permissions, one verify job and timeout
remain unchanged. Packaging-trigger detection now includes native sources and
native build/verification scripts.

The wheel/sdist case inventories pure wheel/typing contents and native source/
header/build support in the sdist. It separately installs wheel and sdist with
no runtime dependencies, validates installed origin outside the checkout,
py.typed, no optional imports, and fallback activation. It extracts only safe
regular-file/directory archive members, rebuilds a wheel from the extracted
sdist outside the checkout, inventories/installs/verifies that wheel, and finally
compiles/activates optional C support only in the extracted scratch package.

The metadata edit is limited to sdist includes: src/, native/, and
scripts/build_native.py. User's pre-existing version 1.14.1 and other metadata
are preserved. Wheels remain py3-none-any with no compiled binaries. Native
compilation is an explicit verification toolchain requirement, not a runtime or
installation dependency. Both wheel and sdist installation succeeded before optional compilation.
A further independent sdist installation also passed with PATH restricted to
its venv/bin and CC deliberately invalid: gcc/clang discovery both returned
None; installed origin, py.typed and all fallback hooks were verified from /tmp.
This confirms source installation does not require the optional compiler.

Approved handoff doc ../gunz-bench references now point to the actual ../bench
sibling. Compatibility benchmark removal/API migration remains outside this fix.
No registry/index/version source was edited, and no changes were committed or
published. Unique internal fragment:
changes/20261008-verification-native-sdist.internal.md.

## Executed evidence

Interpreter /tmp/gunz-utils-audit-20261008/bin/python, Python 3.11.14,
pytest9.0.3, Ruff0.14.10, mypy1.19.1; Linux/GCC. Coordinate AR-10 C source and
its dedicated test_audit_native_safety_regressions.py; that file is explicitly
included in both matrix legs.

```bash
PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 timeout 120 /tmp/gunz-utils-audit-20261008/bin/python scripts/verify_native.py
# fallback: 34 passed, 22 intentional native differential skips, 0.30s
# native: 56 passed, zero skips, 0.29s
PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 timeout 60 /tmp/gunz-utils-audit-20261008/bin/python -m pytest tests/test_core/test_audit_verification_matrix.py tests/test_core/test_audit_ci.py tests/test_core/test_ci_policy.py scripts/tests/test_ci_cli.py -q -p no:cacheprovider
# 30 passed in 1.74s
/tmp/gunz-utils-audit-20261008/bin/ruff check scripts/ci.py scripts/audit_ci.py scripts/build_native.py scripts/verify_native.py tests/test_core/test_audit_verification_matrix.py
# All checks passed
```

Real `_case_wheel_sdist()` invoked with a bounded 180-second wrapper, using
fresh throwaway tmp/c05-venvs environments and tmp/c05-dist artifacts; exit 0.
Executed twice because coordinated C changed during the first run. Final
stable-C run succeeded: wheel/sdist installed independently, extracted-sdist
wheel rebuilt/installed, and extracted-source C compiled with active hooks.
Log: ignored tmp/ar11/packaging-roundtrip.txt.

Archive inventory confirmed gunz_utils-1.14.1-py3-none-any.whl has py.typed and
no binary, and sdist has native/src/_accel.c,
native/include/gunz_utils_native.h, scripts/build_native.py. Checkout _accel
artifact list remained empty. Package installs occurred only in isolated scratch
venvs as authorized; the shared existing environment was not modified.

Regression tests enforce activation failure when fallback is falsely claimed
native, required native sdist support, rejection of accidental binaries in pure
wheels, safe archive extraction, and preserved dispatcher/hosted gate contracts.
Platform-specific native proof is Linux only. Windows/macOS, the full canonical
gate and Python3.12 actual execution remain coordinator verification. No A4 or complete compatibility claim.


Independent compiler-hidden install used a copied sdist and unique
 tmp/ar11/no-compiler-env, avoiding canonical c05 scratch collisions. Fresh
 venv source installation with --no-deps passed despite unavailable gcc/clang
 discovery and deliberately invalid CC; outside-checkout installed fallback and
 typing marker verification also passed. Its package installation affected only
 that disposable venv.

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
