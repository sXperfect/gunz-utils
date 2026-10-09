# NP-01: Windows native contracts and build readiness

**Date:** 2026-10-08
**Status:** Preparation complete — actual Windows host execution pending
**Parent:** [Native platform verification](2026-10-08-platform-verification.md)
**Base:** `a3f224ba5b14fe98b4f41833c9a73f297754a3af` plus preserved user edits

## Scope

Inspect Python/CRT file locking, file-key/salt cleanup, os.rename no-overwrite behavior, reparse/ACL limits, Windows pipe timeout/cancellation and child ownership, C extension compile+link include/library/output paths. Identify meaningful Windows-native test selection and portable counterparts; propose source repairs outside owned build script before editing. Simulated command/dispatch checks must be labeled preparation, not Windows verification. Use primary CPython/MSVC docs for uncertain facts.

## Exclusive ownership

scripts/build_native.py only for reviewed Windows configuration fixes; tests/test_core/test_platform_windows_contracts.py; this record; unique fragment.

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

## Inventory and confirmed build configuration findings

Reviewed scripts/build_native.py, SecureStore's Windows CRT lock/private-file/
publication cleanup branches, fs._rename_directory_noreplace,
security.open_path_under_base fallback, subprocess pipe/termination branches,
and relevant secure/crash/atomic-permission/security/subprocess/native tests.
Read current AGENTS.md and canonical security/algorithm methodology. No
implementation other than the exclusively assigned build script was edited.

The former Windows command provided includes and /LD but no explicit CPython
import-library location, no dynamic CRT choice, and no isolated object/import
library output. These are inspection-confirmed configuration omissions, not an
observed Windows compilation failure: no Windows machine/compiler was present.
An externally configured LIB environment could previously supply the missing
Python search directory; the standalone script did not establish it itself.

Python 3.11 documents Windows extension linkage with pythonXY.lib. Its actual
PC/pyconfig.h also selects python311.lib/python311_d.lib via MSVC pragma, so
absence of an explicit library argument alone does not prove missing linkage;
the search directory and debug/release agreement still matter.
[CPython Windows extension guide](https://docs.python.org/3.11/extending/windows.html),
[CPython 3.11 header](https://github.com/python/cpython/blob/3.11/PC/pyconfig.h).

MSVC /LD defaults to /MT unless /MD is selected; /LIBPATH supplies a linker
search directory, /Fo controls object output, and /IMPLIB controls import-library
output. These explain the concrete preparation changes below.
[MSVC runtime choices](https://learn.microsoft.com/en-us/cpp/build/reference/md-mt-ld-use-run-time-library),
[/LIBPATH](https://learn.microsoft.com/en-us/cpp/build/reference/libpath-additional-libpath),
[/Fo](https://learn.microsoft.com/en-us/cpp/build/reference/fo-object-file-name),
[/IMPLIB](https://learn.microsoft.com/en-us/cpp/build/reference/implib-name-import-library).

## Scoped build preparation repair

Windows command now uses the running interpreter's major/minor import library
under sys.base_prefix/libs, rather than the venv's prefix. A debug interpreter
chooses its _d library and /MDd; release chooses the ordinary library and /MD.
Py_DEBUG configuration or the debug interpreter's gettotalrefcount attribute
drives the choice, consistent with _DEBUG header selection. Missing import
library is a clear nonzero configuration failure before cl launches. This
supports standard installed CPython layouts; embedded/custom source-tree
layouts without import libraries remain explicit prerequisites, not guessed.

MSVC executes in a unique managed temporary directory beneath the requested
output directory. /Fo and /IMPLIB target that directory; cwd also contains
default auxiliary artifacts. Final .pyd output remains outside scratch using
an absolute destination, preserving relative --output-dir behavior when cwd
changes. Scratch cleanup covers both compiler success and nonzero failure.
The Windows fallback extension suffix is .pyd. POSIX gcc/clang arguments and
Darwin dynamic_lookup flags remain unchanged. The factored executor retains
existing compiler-error handling. No new CI job/workflow or runtime dependency.

New tests/test_core/test_platform_windows_contracts.py has seven preparation
cases: release/debug ABI matching and intermediate cleanup on success/failure,
missing-base-library refusal before compiler execution, and unchanged Linux/
Darwin command contracts. Preparation substitutes only compiler execution,
uses synthetic library/artifact bytes, and never calls the fake .pyd executable.
Passing these cases is not an MSVC, Windows ABI or kernel proof.

Unique fragment: changes/20261008-windows-native-build-preparation.fixed.md.
User release/version/export/changelog edits, shared indexes/registry and other
source files remain preserved. No commits, shared-environment installs,
production store access, remote execution or external messages.

## Real Windows counterparts prepared for NP-03

The following exact node IDs execute only when actual sys.platform is win32;
Linux preparation never spoofs their host guard:

- tests/test_core/test_platform_windows_contracts.py::test_windows_byte_lock_serializes_and_releases_on_holder_exit
  (two cases: graceful release and process termination). Spawned child uses
  actual SecureStore CRT lock, acknowledges ownership, parent verifies an
  independent descriptor cannot take byte zero, then verifies release after
  holder exit. The CRT can lock beyond EOF, so empty .lock files are admissible.
  [Python CRT locking contract](https://docs.python.org/3.11/library/msvcrt.html#msvcrt.locking).
- tests/test_core/test_platform_windows_contracts.py::test_windows_directory_rename_preserves_existing_target
  directly exercises the actual Windows no-replace rename branch with a
  competing destination; both source bytes and target remain intact.
- tests/test_core/test_platform_windows_contracts.py::test_windows_store_roundtrip_and_mode_cleanup
  (two credential modes). Actual local file/salt publication, opposite-mode
  cleanup, independent reopen, integrity and cooperative ACL label behavior.
  It deliberately does not treat POSIX 0600 bits as a Windows ACL oracle.

The lock test has 15-second readiness/release watchdogs, five-second join,
bounded terminate/kill fallback, explicit descriptor/pipe closure and reap.
Only synthetic stores/children are involved. No process-crash result is
interpreted as power-loss durability. These five cases are pending on Windows.

## Platform boundaries and still-uncovered obligations

- Windows SecureStore mode enforcement is not a DACL implementation: owner/mode
  checks and fchmod are POSIX-only. Windows chmod only controls the read-only
  flag, not POSIX permission bits. A Windows deployment must provide a suitable
  trusted parent DACL; actual inherited ACL/owner evidence is still needed.
  [Python chmod platform contract](https://docs.python.org/3.11/library/os.html#os.chmod).
- Static symlink checks do not establish general NTFS reparse-point/junction
  protection. Descriptor-relative O_NOFOLLOW opening is a POSIX branch;
  Windows security opener resolves/validates then path-opens. Reparse races
  and ACL guarantees require a real host/security contract, not Linux shims.
- Existing tests/test_secure/test_secure_store.py::TestSecureStore::test_master_key_file_mode_0600
  assumes POSIX mode bits without a Windows guard. POSIX fchmod and no-follow
  tests, plus the POSIX-flock SP-02 module, correctly skip relevant unavailable
  facilities. Native selection must name gaps/counterparts rather than blanket
  suppressing unrelated tests. Linux /proc benchmark tests are inherently
  platform-specific.
- Windows synchronous capture has blocking daemon pipe readers; escaped
  descendants can retain readers after the API deadline. Windows termination
  paths target the direct child and do not establish Job Object ownership of
  descendants. Async subprocess support needs the Proactor loop on Windows;
  selector-loop support cannot be assumed. These are read-only review limits,
  not repaired or newly executed Windows outcomes.
  [CPython asyncio Windows support](https://docs.python.org/3.11/library/asyncio-platforms.html#subprocess-support-on-windows),
  [Windows process termination boundary](https://learn.microsoft.com/en-us/windows/win32/procthread/terminating-a-process).
- Real cl/link execution, architecture compatibility, debug binary loading,
  actual .pyd dispatch, NTFS ACL/reparse behavior and native bounded pipe/process
  schedules remain unperformed. No Windows host or credentials were supplied.

## Executed preparation evidence

Linux host, base a3f224ba5b14fe98b4f41833c9a73f297754a3af on
audit/native-platforms-20261008 with user edits preserved. Plugin autoload
disabled for focused pytest. Actual commands:

```bash
PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 timeout 45 /tmp/gunz-utils-audit-20261008/bin/python -m pytest tests/test_core/test_platform_windows_contracts.py -q -p no:cacheprovider
# Python 3.11.14 / pytest 9.0.3: 7 passed, 5 actual-Windows skips, 0.05s
PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 timeout 45 /tmp/gunz-utils-audit-20261008-py312/bin/python -m pytest tests/test_core/test_platform_windows_contracts.py -q -p no:cacheprovider
# Python 3.12.13 / pytest 9.0.3: 7 passed, 5 actual-Windows skips, 0.06s
/tmp/gunz-utils-audit-20261008/bin/ruff check scripts/build_native.py tests/test_core/test_platform_windows_contracts.py
# Ruff 0.14.10: All checks passed
timeout 45 /tmp/gunz-utils-audit-20261008/bin/python -m mypy --follow-imports=silent --cache-dir tmp/np01/mypy scripts/build_native.py tests/test_core/test_platform_windows_contracts.py
# mypy 1.19.1: Success: no issues found in 2 source files
PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 timeout 90 /tmp/gunz-utils-audit-20261008/bin/python scripts/verify_native.py --mode native
# Real Linux GCC build in temporary package: 57 passed, zero skips, 0.26s
```

The last command proves POSIX build regression only, not Windows native
activation. Initial mock-setup failure and Linux typeshed CRT-symbol errors
were corrected; final pinned checks passed. Equivalent runtime CRT import
avoids treating Windows-only typeshed names as available on Linux.

Coordinator reports combined preparation/static/docs gates pass and is
collecting guarded source-fingerprinted evidence via NP-03. That reported
integration result is distinct from this worker's commands. Actual Windows
Python3.11/3.12 acceptance remains unchecked; no Windows A3/A4/native-certification
claim is made. Ready prerequisite: matching-architecture MSVC developer prompt,
standard installed CPython headers/import libs, pinned tools/extras, and a
confirmed actual Windows host; run NP-03 with requested platform Windows and
both interpreter paths. The verifier must refuse a Linux host for that request
and report all five native skips as uncovered coverage, not success.

## Independent readiness follow-up

Re-reviewed the current builder, all preparation/native probe bodies and the
verifier's exact WINDOWS_NODES selection. No additional production builder
defect was confirmed. Release/debug CRT and pythonNN[_d].lib agree; includes
come from the running interpreter's sysconfig. Architecture consistency still
depends on the correct MSVC developer prompt and actual import/load evidence:
command capture cannot validate a PE binary or a custom header installation.

Two preparation-fixture mistakes were confirmed and corrected:

1. Simulated release cases set Py_DEBUG=0 but inherited the real interpreter's
   gettotalrefcount marker. A bounded synthetic probe injecting that marker
   reproduced a failure seeking the absent debug import library. The corrected
   fixture models its own sys object, keeping simulated release/debug identity
   independent of the actual test host. The originally failing probe then passed.
2. Debug cases previously supplied a release-style extension suffix. CPython
   Windows loaders use a _d prefix for both tagged and untagged debug .pyd
   names. Fixtures and filename assertions now match that ABI naming rule.
   [CPython 3.11 loader](https://github.com/python/cpython/blob/3.11/Python/dynload_win.c),
   [CPython 3.12 loader](https://github.com/python/cpython/blob/3.12/Python/dynload_win.c).

One distinct regression now covers missing Py_DEBUG metadata with an available
debug-interpreter marker: command must select /MDd, the _d import library and
the supplied debug suffix. Existing debug cases, rather than duplicate cases,
now use relative output paths containing spaces. Captured final artifact paths
remain absolute and outside the cleaned intermediate directory. This is still
synthetic command/cleanup preparation, not MSVC or Windows-kernel execution.

The five actual-Windows counterpart cases and their exact verifier node IDs are
unchanged. The byte-lock schedule acknowledges production lock ownership,
uses an independently opened descriptor at the same byte position, and proves
that the same descriptor can lock after graceful or terminated holder exit.
Thus the first lock error is checked against a subsequent successful operation,
rather than accepted alone as evidence of support. Mode-cleanup probes validate
both credential directions and authenticated independent reopen without using
POSIX permission bits as an ACL oracle. Neither probe certifies NTFS reparse
containment, Windows DACL privacy or descendant process ownership.

Read-only verifier coverage review found a readiness limitation: its Windows
ordinary secure-store suite also selects the POSIX-only SP-02 module, which
necessarily contributes ten native coverage skips on Windows. Current strict
completeness will therefore remain false even if the five Windows counterparts
pass. Basic byte-lock probes are not a replacement for the full cross-process
stale-generation/rotation proof. Preserve this visible gap until a meaningful
Windows counterpart is added; do not blanket suppress skips to manufacture
completion. Verifier/subprocess/source registry and shared indexes were not edited.

Final focused commands used the same pinned paths/options recorded above:

- Python 3.11.14: **8 passed, 5 actual-Windows skips in 0.07s**.
- Python 3.12.13: **8 passed, 5 actual-Windows skips in 0.06s**.
- Ruff 0.14.10: owned builder and test file passed.
- mypy 1.19.1, --follow-imports=silent, cache tmp/np01-review/mypy:
  no issues in those two files.

Synthetic before/after fixture probe used tmp/np01-review; no native compiler,
remote host, production store, install or commit was invoked during follow-up.
Added changes/20261008-windows-readiness-review.internal.md. The production
builder, actual Windows probe bodies and native node IDs remained unchanged.
Actual release/debug binary linkage/loading, header/architecture agreement,
ACL/reparse/process-tree and complete Windows process schedules still require
real host evidence; no Windows verification level is promoted by this review.
