# NP-03: Portable platform evidence harness

**Date:** 2026-10-08
**Status:** Adversarial repairs and stable Linux preparation verified; native hosts unavailable
**Parent:** [Native platform verification](2026-10-08-platform-verification.md)
**Base:** `a3f224ba5b14fe98b4f41833c9a73f297754a3af` plus preserved user edits

## Scope

Implement a local-first command that validates requested OS against actual host, requires Python>=3.11, verifies source origin and native/fallback activation using existing verify_native helper, runs targeted filesystem/storage/process contracts with bounded commands and synthetic fixtures, and emits structured JSON including actual host/revision/tool/result/skip evidence. Permit explicit Linux preparation run, reject mismatched target, and never claim macOS/Windows evidence from mocks or Linux. Avoid external dependency installs, remote job launch and CI edits; expose missing compiler/extras clearly.

## Exclusive ownership

scripts/verify_platform.py; tests/test_core/test_platform_verifier.py; this record; unique internal fragment.

Read the parent execution contract and preserve all user edits. Initial work
needs no real host; native acceptance cannot complete without one. Report source
locations, contract, actual executed commands and expected native capability/skip
rules. Finish bounded preparation independently; tell coordinator when ready.

## Acceptance and evidence

- [x] Implementation/test inventory and platform contracts reviewed.
- [x] Preparation or verifier implementation is concrete and reviewable.
- [x] Pinned focused tests/lint/type checks execute successfully.
- [x] Native prerequisites, command, evidence format and coverage gaps recorded.
- [ ] Actual native host run reviewed (pending access).

## Implementation and coverage contract

Implemented scripts/verify_platform.py and dedicated test_platform_verifier.py.
Standalone Python CLI validates actual OS against --platform before launching any
command; Linux is accepted only as explicit linux-preparation. Wrong OS refuses
with structured JSON, not a mocked/native success. Launcher and each requested
interpreter require Python>=3.11. A fresh process records OS/kernel/architecture,
Python executable/compiler/implementation, relevant dependency versions, include/
library/extension configuration and actual gunz_utils import origin. Source must
come from the current checkout's src/gunz_utils/__init__.py.

A SHA256 manifest fingerprints source/native/script/test inputs and pyproject,
including dirty source and local acceleration binaries; Git HEAD is recorded
when available. Fingerprints before/after must agree. Docs/tmp/cache artifacts
are excluded, so independent evidence updates do not invalidate source identity.
Compiler selection/path/version is recorded; missing tools remain visible.

Selected real suites cover filesystem atomic publication/setup and CAS process
schedules, SecureStore crash/lock/mode recovery, and subprocess deadlines/cleanup.
Actual Darwin nodes are exclusive-volume rename, private write/directory fsync,
and descriptor/symlink handling. Windows nodes are byte-lock holder exit,
no-replace directory rename and credential-mode store roundtrip/cleanup. Mock
compiler/ABI preparation cases are excluded from the native-platform phase.

Existing verify_native.py runs separately in fallback and native modes under
bounded outer commands; its isolated-source activation checks remain unchanged.
Each phase records exact argv, return code, duration, full file-backed log paths
and bounded 16KiB tails. JUnit records actual testcase counts plus every skipped/
failed/error case. Missing/empty/malformed JUnit cannot pass. Only the two exact
native-only binary differential/compiled-extension skip reasons in forced-fallback
mode are expected exclusions; they remain listed. Any other required OS/native
skip marks coverage incomplete. Both real Python3.11 and3.12 identities are
required for native completion; missing versions are explicit. Single-interpreter
Linux preparation is allowed, with native matrix omissions visible.

Windows common POSIX flock/process-group/permission probes can skip there; these
remain gaps and block native completion. Host-only counterparts establish narrower
native contracts, not an automatic waiver. Any future accepted exclusion needs
an explicit contract decision. Windows ACL/reparse and complete descendant/job
ownership, unsupported Darwin volumes, and real native host execution remain
outside the Linux preparation result.

Each command has a finite timeout, direct process reap and POSIX owned-group or
Windows taskkill-tree cleanup evidence. Logs go directly to files to avoid
inherited-pipe capture hangs; no shell/Bash gate or network service is used.
Trusted repository checks may produce full disk logs; this is not a general
untrusted-output disk-quota sandbox. Process-tree escape/OS termination limits
remain explicit rather than claiming arbitrary hostile child termination.

## Focused preparation checks

Pinned Ruff0.14.10/mypy1.19.1/pytest9.0.3; explicit launcher guard retains a scoped
UP036 explanation because standalone refusal is required by this task.

```bash
ruff check scripts/verify_platform.py tests/test_core/test_platform_verifier.py
# All checks passed
mypy --cache-dir tmp/np03-mypy scripts/verify_platform.py tests/test_core/test_platform_verifier.py
# Success: no issues found in2 source files
PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 /tmp/gunz-utils-audit-20261008/bin/python -m pytest -q tests/test_core/test_platform_verifier.py
# 14 passed in0.15s
PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 /tmp/gunz-utils-audit-20261008-py312/bin/python -m pytest -q tests/test_core/test_platform_verifier.py
# 14 passed in0.20s
```

Tests independently check wrong-host no-execution refusal, installed-source/old-
Python/wrong-kernel identity rejection, changed runtime/proof input fingerprints,
required dual-version matrix, exact expected fallback skips, unexplained native
skips/failures, absent/empty JUnit, actual process timeout/reap, missing executable,
and invalid timeout before artifact/process actions. Fake metadata in unit tests
is preparation for guards, never native host evidence.

## Concrete local commands and pending native prerequisites

From repository root, Linux preparation executed on both pinned interpreters:

```bash
/tmp/gunz-utils-audit-20261008/bin/python scripts/verify_platform.py --platform linux-preparation --python /tmp/gunz-utils-audit-20261008/bin/python --python /tmp/gunz-utils-audit-20261008-py312/bin/python --output tmp/np03/linux-platform-evidence.json --timeout 180
```

Native macOS, with installed project extras/pytest and actual clang headers:

```text
python3.11 scripts/verify_platform.py --platform macos --python /path/to/python3.11 --python /path/to/python3.12 --output tmp/macos-platform-evidence.json --timeout 240
```

Native Windows, from a matching MSVC developer environment with Python libraries
and installed project extras/pytest (replace each path with the real executable):

```text
C:\Python311\python.exe scripts\verify_platform.py --platform windows --python C:\Python311\python.exe --python C:\Python312\python.exe --output tmp\windows-platform-evidence.json --timeout 240
```

Commands invoke Python only; no dependency install, CI/job launch, remote host
contact, workflow change or platform spoofing is performed. JSON/log/JUnit
artifacts are local reviewable evidence. Actual Windows/macOS hosts have not
been accessed; native acceptance remains pending. Fragment:
changes/20261008-platform-verifier.internal.md. Coordinator owns aggregate gate,
registry/index reconciliation and real-run routing.

## Prior actual Linux preparation evidence (before acceptance repairs)

First real run: all10 phases returned0 with no unexplained skips, but the
source fingerprint changed from2838bb5020d00f7d0b7c3b19bc48d5f85f063a5daeff82004dd1b2f937609583
tofefd44657ffcc63e83b0c239de9f771ddafcc47b4068487483b8684369b52b74
(232 inputs both times). Windows owner finalized its CRT runtime-import source
while this run executed. The guard correctly returned exit1/status incomplete;
no stable-source or native claim was made. Preserved JSON:
tmp/np03/linux-platform-evidence-initial-incomplete.json, with full logs/JUnit.

Each actual interpreter (3.11.14 and3.12.13) recorded18 filesystem,46 store,
20 subprocess,35 fallback and57 native passes. Forced fallback additionally
records22 exact native-only expected skips; native phase has none. These are
JUnit testcase counts, not a promise that all executed subtests are independent
coverage. Compiler/native activation and source-origin guards passed.

Final stable rerun returned exit0/status **prepared**, complete=True,
source_unchanged=True, native_platform_complete=False, missing_python_versions=[].
The232-input SHA256 fingerprint agreed before/after:
fefd44657ffcc63e83b0c239de9f771ddafcc47b4068487483b8684369b52b74.
Actual local compiler executable /usr/bin/gcc was recorded and both native
activation checks passed; fallback was independently required to load no hooks.

For each real Python3.11.14/3.12.13 interpreter, all5 phases returned0:
18 filesystem,46 SecureStore,20 subprocess,35 fallback and57 native JUnit passes.
Fallback's22 exact native-only skips remain visible expected exclusions; no
unexplained skips, test failures, timeouts or launch failures occurred. Source
origin matched this checkout for both interpreters. Full report/JUnit/logs:
tmp/np03/linux-platform-evidence.json and its reported artifact directory.
The earlier changed-source rejection is preserved independently.

No script/test mutation occurred during this final run. Pinned scoped Ruff/mypy
and both14-case verifier test runs pass. This is actual **Linux preparation**,
not Windows/macOS proof or a full native-platform audit claim. Native Windows/
macOS host access and actual OS-required contracts remain pending. Coordinator
owns full repository gate and shared registry evidence.



## Adversarial acceptance/provenance follow-up

Confirmed and repaired within assigned verifier ownership:

1. A fallback report containing only an allowlisted-reason pytest.xfail was
   accepted with zero executed passes. Skip disposition type was discarded and
   class matching used a substring. Expected exclusions now require exact
   tests.test_core.test_binary_accel classname, pytest.skip type and approved
   reason; pytest.xfail/unknown types/unrelated modules are coverage gaps. At
   least one actually passed testcase must exist even in forced fallback.
2. An unrelated XML root with a blank testcase could certify native coverage.
   The parser now validates known root/suite/testcase structure, nonempty test
   names, known outcome children and nonnegative bounded decimal counters.
   Huge malformed counters return structured invalid evidence instead of Python
   integer-conversion errors. Header-reported failures/errors block completion;
   per-case pass counting avoids negative totals for multiple failure outcomes.
   Summary counts are retained independently because actual pytest subtests can
   make suite totals exceed testcase rows (63 summary vs57 rows in real fallback).
3. Truncated/non-integer/bool/negative Python version identity was accepted or
   could raise type errors. Require exactly three nonnegative integer components
   and a nonempty string source origin before path comparison. Actual native
   dual-version requirements remain unchanged; duplicate3.11 aliases cannot
   supply3.12 evidence.
4. An inherited PYTEST_PLUGINS selection hook bypassed disabled plugin autoload:
   a real synthetic plugin removed a failing test and pytest reported1pass/exit0.
   Controlled verification environment now removes PYTEST_PLUGINS as well as
   PYTEST_ADDOPTS, preserving compiler/developer environment. A real pytest
   regression proves the formerly suppressed assertion now executes and fails.
5. Native activation receipt checking accepted negated/prefixed strings by
   substring. Receipt must now be an exact standalone helper stdout line.

These are local verifier acceptance defects, not a claim of native kernel failure
or protection against compromised Python/pytest/compiler/repository software.
Source fingerprinting records trusted workspace snapshots before/after a run;
it detects persistent concurrent edits but is not continuous hostile same-account
attestation. Interpreter identity and duplicated/missing version guards remain
explicit. External native hosts are still absent; subprocess and Windows build
source are owned by the other parallel workers and were not edited here.

Focused verification (no full harness run while other owners mutate inputs):

```bash
/tmp/gunz-utils-audit-20261008/bin/ruff check scripts/verify_platform.py tests/test_core/test_platform_verifier.py
# All checks passed
/tmp/gunz-utils-audit-20261008/bin/mypy --cache-dir tmp/np03-mypy scripts/verify_platform.py tests/test_core/test_platform_verifier.py
# Success: no issues found in2 source files
PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 /tmp/gunz-utils-audit-20261008/bin/python -m pytest -q tests/test_core/test_platform_verifier.py
# 37 passed in0.50s
PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 /tmp/gunz-utils-audit-20261008-py312/bin/python -m pytest -q tests/test_core/test_platform_verifier.py
# 37 passed in0.50s
git diff --check
# Passed
```

Added23 meaningful regressions to previous14 (37 total), including real pytest
xfail and external selection-plugin executions, malformed JUnit/identity domains,
all-skipped fallback, aggregate/multiple outcomes and exact activation receipts.
Previously captured10 real phase XML artifacts were replayed through the tightened
parser successfully; this is schema compatibility evidence only, not a fresh
platform run. Earlier prepared Linux report belongs to its original fingerprint.
At worker handoff, the stable-source rerun remained coordinator-owned pending
completion of parallel executable owners. No hosted/remote job, dependency installation,
commit, source edit outside ownership or unsupported A3/A4 native claim.

## Coordinator stable-source rerun

After all executable owners finished, the coordinator added NP-04's 14 async
regressions to the subprocess phase and executed:

```text
/tmp/gunz-utils-audit-20261008/bin/python scripts/verify_platform.py --platform linux-preparation --python /tmp/gunz-utils-audit-20261008/bin/python --python /tmp/gunz-utils-audit-20261008-py312/bin/python --output tmp/np03/integrated-linux-platform-evidence.json
```

Exit 0; `status=prepared`, `complete=true`, `source_unchanged=true`, both supported
Python versions present, `native_platform_complete=false`. Each interpreter
passed 18 filesystem, 46 SecureStore, 34 subprocess, 35 fallback and 57 compiled
native cases. Each fallback phase records 22 exact expected native-only skips;
all ten phases have zero coverage gaps. The 233-file SHA-256 fingerprint is
`d05c1944ba457f32d0b58f98aaeae52ac7846586779880e42d58977c93da02e6`.
Logs/JUnit remain beside the JSON under ignored tmp. No actual Windows/macOS
execution or new platform audit-level promotion is claimed.

The coordinator's final canonical aggregate gate also passed all six gates;
`tmp/platform-integrated-ci-summary.json` records every return code as zero.
Both full Python suites passed 1,370 tests with 29 documented skips and each
compiled-native proof suite passed 57 tests. Initial and earlier-phase evidence
is retained with its original fingerprint rather than substituted for this run.
