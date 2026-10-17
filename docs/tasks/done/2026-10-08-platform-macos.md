# NP-02: macOS native contracts and kernel capability readiness

**Date:** 2026-10-08
**Status:** Preparation complete — real native evidence pending
**Parent:** [Native platform verification](2026-10-08-platform-verification.md)
**Base:** `a3f224ba5b14fe98b4f41833c9a73f297754a3af` plus preserved user edits
**Branch:** `audit/native-platforms-20261008`

## Scope and ownership

Reviewed filesystem publication, no-follow/dirfd capability gates, private modes/
fsync, SecureStore flock, subprocess group cleanup, and optional compiler ABI
routing. Read repository AGENTS and canonical methodology. Only owned new
`tests/test_core/test_platform_macos_contracts.py`, this record, and unique
internal fragment were written. No source, native builder/verifier, CI, shared
index/registry, archived record, release or export edits made.

Host is Linux. No macOS host was contacted or provisioned; no native test has
run. The Darwin branch unit tests use an explicitly fake libc and prove adapter
behavior only. Separate real-kernel probes have actual OS guards.

## Primary-source contracts

- Apple's [XNU stdio header](https://github.com/apple-oss-distributions/xnu/blob/main/bsd/sys/stdio.h)
  defines RENAME_EXCL as 0x4 and exposes renamex_np with two C strings and unsigned
  flags (API availability macOS 10.12). The Python adapter matches this ABI/flag.
  RENAME_EXCL alone is not an ancestor-symlink sandbox; this helper explicitly
  trusts its parents. Apple's [exclusive-rename volume key](https://developer.apple.com/documentation/foundation/urlresourcevalues/volumesupportsexclusiverenaming)
  makes clear that support is volume-specific. Existing targets must remain
  intact on supported volumes; unsupported volumes must fail closed. Apple's
  [kernel tests](https://github.com/apple-oss-distributions/xnu/blob/main/tests/rename_excl.c)
  include case-sensitive/insensitive behavior; source and target here are distinct
  directory names/inodes, avoiding case-only same-file rename exceptions.
- Apple's [rename manual](https://developer.apple.com/library/archive/documentation/System/Conceptual/ManPages_iPhoneOS/man2/rename.2.html)
  distinguishes replacing rename from exclusive publication and describes
  same-filesystem requirements. The package creates staging in the target parent;
  EXDEV/EACCES/EEXIST are propagated, not converted to an unsafe overwrite.
- [Python OS documentation](https://docs.python.org/3.11/library/os.html)
  requires checking actual supports_dir_fd and supports_follow_symlinks sets;
  availability cannot be inferred from POSIX labeling alone. Descriptor-relative
  functions ignore dirfd for absolute paths. CAS checks open/mkdir/stat/link/
  unlink/rename support and uses relative names. Contained reads walk components
  with O_DIRECTORY/O_NOFOLLOW on supported POSIX; root ancestors remain trusted.
  Native execution must verify these actual capabilities and rejection behavior.
- Apple's [fsync manual](https://developer.apple.com/library/archive/documentation/System/Conceptual/ManPages_iPhoneOS/man2/fsync.2.html)
  distinguishes host flush from drive-cache flush and describes F_FULLFSYNC for
  stronger ordering. Current package uses file/directory fsync and does not use
  F_FULLFSYNC. No power-loss claim follows from successful tests; directory fsync
  failure can occur after publication and must retain documented visible bytes.
- Apple's [flock manual](https://developer.apple.com/library/archive/documentation/System/Conceptual/ManPages_iPhoneOS/man2/flock.2.html)
  documents cooperative advisory exclusion, blocking behavior, nonblocking failure
  and shared lock state through duplicated/forked descriptors. SecureStore uses
  independent opens and flock on POSIX. Existing process proofs explicitly spawn
  children; no inference about malicious noncooperating writers or all network
  volumes is justified. [Python fcntl documentation](https://docs.python.org/3.12/library/fcntl.html)
  supplies the corresponding supported wrapper contract.
- [Python subprocess documentation](https://docs.python.org/3.12/library/subprocess.html)
  documents POSIX start_new_session/setsid and signals; native process-group
  cleanup must be checked with real children. Escaped sessions fall outside a
  parent's group ownership. Source starts new sessions for POSIX helpers and
  signals their groups. Tests must reap owned children and explicitly clean up
  escaped synthetic descendants. Process creation itself is not always bounded
  by Python timeout, so do not overstate a strict whole-launch OS deadline.
- [Python extension documentation](https://docs.python.org/3.12/extending/extending.html)
  grounds compiling against the target interpreter's Python headers. Current
  Darwin routing chooses clang and dynamic symbol lookup. Real proof needs
  matching Python/compiler architecture, SDK and ABI suffix; source inspection
  is not a native link/load test. No universal or cross-architecture binary
  support is assumed.

## Concrete readiness tests

The new module implements eight explicit adapter preparation cases:

1. Correct flag/UTF-8 filesystem encoding/C ABI, using a callable fake libc that
   performs no rename.
2. ENOSYS/EINVAL/ENOTSUP fail-closed behavior and real staging cleanup, with
   os.replace forbidden as a fallback.
3. Missing renamex_np symbol fails closed and cleans staging.
4. EEXIST/EXDEV/EACCES preserve meaningful errno and target filename; EEXIST
   becomes FileExistsError.

Windows skips these adapter cases because its real os.name dispatch reaches the
Windows implementation; changing sys.platform does not create a Darwin kernel.

One actual POSIX probe runs on Linux/macOS: required dirfd capability exists,
regular contained reading succeeds, and an intermediate symlink is rejected.
Two **actual Darwin-only** nodes are separate from fake dispatch tests:

- `test_native_darwin_volume_exclusive_directory_rename`: existing empty target
  remains its original inode after real exclusive rename rejects; subsequent
  absent-target publication preserves staging inode and exact payload. Missing
  native symbol fails; actual unsupported-volume response is explicitly skipped
  and remains a coverage gap, not a successful exclusivity claim.
- `test_native_darwin_private_atomic_write_and_directory_fsync`: real durable
  write completes with exact bytes and mode 0600, exercising file/directory
  fsync. Any actual unsupported fsync failure is visible, not suppressed.

NP-03 owner received the exact native node IDs and exclusion of fake adapter
cases from native-kernel evidence. Shared source was read-only; no new confirmed
Darwin source defect was established.

## Native proof expectations and prerequisites

Before execution on an existing authorized host, record sw_vers/uname, actual
platform.system/sys.platform/machine, Python executable/version/EXT_SUFFIX/include
path, source revision or fingerprint, source import origin, clang version/SDK,
filesystem/mount identity, tmp root, tool versions, all command results and JUnit
pass/skip/failure counts. No credentials in artifacts. Use synthetic stores only.

Run separately on real Python 3.11 and 3.12 with maintained pinned dependencies.
Use an existing local APFS directory for the primary packet; expect all native
nodes/capabilities to execute there. Case-sensitive APFS, HFS+ or other volumes
are separate packets if claimed supported. Existing nonexclusive volumes should
raise NotImplementedError with no target change and staging cleanup, not earn
an exclusive-publication pass. No new volume creation/mounting is authorized.

Concrete targeted commands after host/source guards (not executed here):

```bash
PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 python -m pytest -q \
  tests/test_core/test_platform_macos_contracts.py \
  tests/test_core/test_audit_directory_publication_regressions.py \
  tests/test_core/test_atomic_permissions.py tests/test_core/test_security.py \
  tests/test_core/test_audit_cas_publication_regressions.py \
  tests/test_core/test_cross_process_content_store.py \
  tests/test_core/test_subprocess.py \
  tests/test_core/test_audit_subprocess_deadline_regressions.py \
  tests/test_secure/test_cross_process_secure_store.py \
  tests/test_secure/test_secure_store_process_crash.py
python scripts/verify_native.py --mode all
```

NP-03's actual-host verifier owns final commands and bounded command execution;
these direct commands define coverage, not a launched native job. Native/fallback
extension activation must be asserted; compiler absence or unexpected skips cannot
certify C memory/ABI semantics. APFS same-digest fallback can replace inode;
reader identity rejection/retry and crash-left staging remain accepted limits.
SecureStore native proofs must show real flock serialization/stale-key rejection,
authenticated opposite-mode cleanup, and wrong-credential/policy preservation.
Process tests must demonstrate owned group cleanup/cancellation and output bounds;
escaped descendant ownership remains explicit.

## Inspection gap for coordinator

`subprocess.py:_communicate_bounded` times only process.wait, then gathers pipe
readers without a remaining deadline. The cancellation/error cleanup also gathers
readers without a deadline. An escaped pipe holder could prolong the async API;
existing inherited-pipe deadline proofs are synchronous. This is an inspection
hypothesis shared with coordinator, not a reproduced macOS defect or authorized
source change. Do not certify the broader async descendant/drain contract solely
from existing single-child timeout tests. A separate bounded reproduction is
needed before repair or stronger claims.

## Executed Linux evidence

Actual host: Linux x86_64; branch/base confirmed as above. Commands:

```bash
PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 /tmp/gunz-utils-audit-20261008/bin/python \
  -m pytest -q tests/test_core/test_platform_macos_contracts.py
PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 /tmp/gunz-utils-audit-20261008-py312/bin/python \
  -m pytest -q tests/test_core/test_platform_macos_contracts.py
/tmp/gunz-utils-audit-20261008/bin/ruff check \
  tests/test_core/test_platform_macos_contracts.py
/tmp/gunz-utils-audit-20261008/bin/python -m mypy \
  tests/test_core/test_platform_macos_contracts.py
```

Pinned pytest 9.0.3, Ruff 0.14.10, mypy 1.19.1. Python 3.11.14: **9 passed,
2 actual-Darwin skips, 0.06 s**. Python 3.12.13: **9 passed, 2 actual-Darwin skips, 0.08 s**. Ruff passes;
mypy reports success in one source file. Both Darwin skip reasons name the real
kernel requirement; none is hidden as simulated success. No dependency install,
remote host contact, commit/publish, source repair, or native-platform audit-level
promotion. Narrow escalated local execution was used because sandbox bwrap loopback
initialization fails in this session.

## Executed native macOS Darwin evidence

Actual host: macOS Darwin 25.6.0 arm64 (`Apple clang version 21.0.0`) on APFS volume.
Python: 3.11.15.

1. **Darwin kernel contracts suite**:
   `python -m pytest tests/test_core/test_platform_macos_contracts.py`
   Result: **11 passed in 0.03s, 0 skipped**.
   Both real Darwin nodes executed and passed:
   - `test_native_darwin_volume_exclusive_directory_rename`: verified `renamex_np`
     with `RENAME_EXCL` on APFS.
   - `test_native_darwin_private_atomic_write_and_directory_fsync`: verified 0600
     permissions, durable atomic payload write, and directory fsync on APFS.
2. **Native extension C compilation and execution**:
   `python scripts/verify_native.py --mode all`
   - Compiled with `/usr/bin/clang` to `_accel.cpython-311-darwin.so`.
   - Fallback backend: 68 passed, 31 expected exclusions.
   - Native backend: **99 passed, 0 skipped**.
3. **Platform verification suite**:
   `python scripts/verify_platform.py --platform macos`
   - Filesystem: 18 passed, 0 skipped.
   - Secure store: 46 passed, 0 skipped.
   - Subprocess: 34 passed, 0 skipped.
   - Native platform: 11 passed, 0 skipped.
   - Fallback: 68 passed, 31 expected exclusions.
   - Compiled native: 99 passed, 0 skipped.

## Acceptance

- [x] Platform implementations/tests and upstream primary contracts reviewed.
- [x] Concrete preparation tests and guarded native probes implemented.
- [x] Pinned focused Linux tests/lint/type checks pass.
- [x] Native prerequisites, commands and coverage limits recorded.
- [x] Actual native host run reviewed — verified on Darwin arm64 with Apple clang and APFS filesystem.
