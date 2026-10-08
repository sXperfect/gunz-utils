# SP-01: CAS process publication

**Date:** 2026-10-08
**Status:** Done — approved repair and scoped process proofs verified
**Parent:** [Cross-process proof program](2026-10-08-storage-process-proofs.md)
**Base:** `3f474ad961239193bee8fc9f9695e0492bad74a7` plus preserved user edits
**Branch:** `audit/cross-process-storage-20261008`

## Ownership and contract

Initial tracked proof writes: `tests/test_core/test_cross_process_content_store.py`, this
record, and `changes/20261008-cas-process-proofs.internal.md`. Existing other tests, archived records, release metadata and export edits were
untouched. Coordinator subsequently authorized only a narrow get() docstring
clarification and a unique docs fragment; no source behavior was changed.
Repository AGENTS and the previously read security/algorithm methodology apply.

Cooperating same-digest writers must preserve complete correct bytes; readers
that return successfully must observe exact bytes with the expected SHA-256.
Normal hard-link publication retains a winner inode. Forced hard-link-unavailable
fallback may replace that inode; its promise is content correctness. Existing
corrupt entries must be rejected, not reported as verified hits. An acknowledged
crash before/after the actual publication syscall characterizes observable
process-death state, not storage-controller or power-loss durability. No promise
of automatic crash staging cleanup or reader success under arbitrary concurrent
inode replacement is assumed.

Domains: finite synthetic 524,288-byte binary payload; SHA-256; fanout 0 and 2
for competing publisher/reader proofs, historical fanout 1 for other cases.
Normal-mode cases first independently probe real hard-link support and skip
with a specific capability reason if absent; forced fallback cases still run.
Inode comparisons are asserted on POSIX; platform-independent byte/error oracles
apply in both modes. Execution below was Linux x86_64 with real hard links.

## Independent oracle and acknowledged schedules

All children use explicit multiprocessing `spawn` with independent stores.
Top-level entrypoints receive dedicated duplex pipes; no Queue feeder thread,
unbounded Queue join, background stress daemon, or timing-only schedule exists.
SHA-256 and exact byte comparisons use standard hashlib/read_bytes independently
of the production helpers. Child OS hooks pause at the actual link/replace
boundary, then invoke the real kernel operation; fallback changes only link
availability to EOPNOTSUPP. OS hooks are local to a publisher process.

- **Two publishers plus one reader, normal/fallback and fanout 0/2 (4 cases):**
  both publishers hash/fsync staging and acknowledge before final link/replace.
  A reader confirms the digest is absent. First publisher is released and
  acknowledged successful; reader verifies bytes. Second publisher is released
  only after that; 16-read bursts overlap each released publication phase and
  final successful read is required. Every successful snapshot matches exact
  bytes, size, and independent digest; only absent/explicit identity-change
  rejections are admissible in overlapping reads. Normal winner inode remains;
  fallback winner inode changes in this forced competing schedule. Successful
  workers leave no incoming staging.
- **Independent existing corrupt competitor (2 cases):** a separate process
  writes and acknowledges corrupt bytes at the expected digest before publisher
  execution. Both publication modes return ValueError, leave competitor bytes
  unchanged, and remove their staging.
- **Actual abrupt publisher death (4 cases):** publisher acknowledges immediately
  before or immediately after real link/replace, then blocks on the pipe. Parent
  kills and joins it; no finally block or success acknowledgment runs. Before
  publication: canonical object missing; fsynced staging retains exact bytes.
  After normal link: canonical object complete; crash-left staging hardlinks to
  the object. After fallback replace: canonical object complete; staging name
  absent. An independent retry publisher succeeds in all four states.
- **Failed fallback publication (1 case):** acknowledged real publisher path,
  then synthetic ENOSPC before replace. OSError is reported, no success, no
  canonical object, and no staging remains after normal exception cleanup.
- **Deterministic reader identity race (1 case):** reader hashes first winner's
  opened inode and acknowledges its independently checked digest; second fallback
  publisher replaces that inode and acknowledges correct content. Resumed
  reader rejects exactly `ValueError("artifact changed during operation")`.
  Explicit retry by the same independent reader succeeds with the byte oracle.
  Other ValueError messages and all other unexpected errors fail the proof.

## Results: confirmed behavior versus defects

No incorrect bytes, unverified success, unreaped child, or new source defect
was established. The initial reader-burst tests expected every read to succeed;
both fallback variants failed with ValueError. Source contract inspection and a
new acknowledged deterministic schedule established fail-closed inode identity
rejection, rather than corruption. Tests now explicitly account for this exact
rejection; errors are not broadly swallowed and successful reads retain the
strict independent byte/hash checks.

**Accepted limits:** competing fallback writers replace inode identity; a reader
may need an explicit retry when pathname identity changes; crash-left incoming
files persist before publication and after normal hard-link publication. No
power-failure/fsync-directory guarantee, hostile directory/source mutation proof,
Windows filesystem proof, stable snapshot promise, or automatic garbage collector
is inferred from these tests.

**Approved narrow documentation clarification:** coordinator authorized the
`ContentAddressedStore.get` docstring to state that concurrent pathname replacement
can raise ValueError even for a same-digest cooperating publisher, and callers may
retry after publication settles. Implemented this wording and unique docs fragment;
no automatic retry or source behavior change was made.

**GAP-006 scoped proof:** cooperating cross-process writer byte correctness is
proved for acknowledged normal/fallback schedules with independent reader oracles.
Fallback inode replacement is an accepted contract behavior, not corruption.
Hostile-root/final-path identity boundaries and power-loss durability remain
outside this proof and retain their existing limitations.

## Boundedness and cleanup

Parent/child pipe waits: 15 seconds. Normal completion joins: 15 seconds.
Unconditional finally cleanup closes every pipe, allows 0.25 seconds for natural
exit, kills any remaining child, joins within 15 seconds, verifies it is reaped,
and closes process handles. Crash cases use real kill plus bounded join before
reading state. Each test has at most three live children, finite 16-read bursts,
a finite payload, and pytest-isolated temporary output directories. A timeout,
unexpected phase, child protocol error, or unkillable child fails visibly.

## Execution evidence

`PYTEST_DISABLE_PLUGIN_AUTOLOAD=1` for both interpreter runs; pinned pytest 9.0.3.

```bash
PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 /tmp/gunz-utils-audit-20261008/bin/python \
  -m pytest -q tests/test_core/test_cross_process_content_store.py
PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 /tmp/gunz-utils-audit-20261008-py312/bin/python \
  -m pytest -q tests/test_core/test_cross_process_content_store.py
/tmp/gunz-utils-audit-20261008/bin/ruff check \
  tests/test_core/test_cross_process_content_store.py
/tmp/gunz-utils-audit-20261008/bin/python -m mypy \
  tests/test_core/test_cross_process_content_store.py
```

Final results after hard-link capability handling: Python 3.11.14 **12 passed
in 4.55 seconds**; Python 3.12.13 **12 passed in 4.56 seconds**, zero skips. Earlier
completed version after typed observer subclass: Python 3.11.14 **12 passed in
5.02 seconds**; Python 3.12.13 **12 passed in 4.83 seconds**. Ruff 0.14.10 and
mypy 1.19.1 pass. Initial mypy messages about assigning an instance method and
returning Any were corrected with an observed-store subclass and typed message
cast; no type suppression was added.

No package installation, network operation, branch mutation, source behavior
repair, commit, publication, shared-index edit, or archived-record write performed.
Narrow escalated local commands were needed because the sandbox's bwrap loopback
initialization fails in this session. Full integration/gate and registry evidence
belong to the parent; this packet does not promote historical audit levels.

## Deliverables

- [x] Contracts, independent oracle, acknowledged process schedules recorded.
- [x] Portable start/capability and unconditional bounded cleanup implemented.
- [x] Both Python versions execute real process proofs.
- [x] Pinned Ruff/mypy results recorded.
- [x] Confirmed behavior separated from source defects/accepted limits.
- [x] Coordinator receives packet and proposed documentation wording.
- [x] Combined integration/canonical gate evidence, owned by coordinator.

## Final approved-repair integration — 2026-10-08

The user replied **Continue** directly to the explicit request to apply the
reviewable authenticated cleanup patch. The coordinator applied that exact
12-line source change; no existing production store was accessed. Previous
approval-blocked and failing statements above are chronological pre-repair
evidence and are superseded by this final integration.

- SP-01 CAS: 12 real spawned-process cases pass per interpreter.
- SP-02 SecureStore locks: 10 real-process cases pass per interpreter.
- SP-03 abrupt-exit recovery: unchanged 26 strict cases pass per interpreter,
  including both mode-switch post-rename failures, future writes/rotation and
  credential/policy rejection preserving current/pending key bytes.
- SP-04 ordinary rejection/cleanup/fsync recovery: 10 additional cases pass.
  Full secure isolation suite: **131 passed**. Counts overlap.
- Canonical aggregate gate: all six gates return zero. Python 3.11.14 and
  Python 3.12.13 each pass **1,302 main tests**, with 22 intentional native-absent
  skips, plus **57 compiled-native tests with zero skips** and 35 forced-fallback
  passes. Ruff 0.14.10, mypy 1.19.1 (97 source files), strict Sphinx and all
  dependency/distribution isolation checks pass.
- Local logs: `tmp/storage-final-verification.log`; summary:
  `tmp/storage-final-summary.json`. Source/test/config/build/doc-source input
  fingerprint: `0ca79e0c9f628a3cc6d8856346d624f2b627d9c40d2612d45c9c060ee9ed1861` (242 files; manifest
  `tmp/storage-final-tree.json`, excluding evolving task/audit records).

The scoped storage work is complete. Broader Windows/macOS/NFS behavior,
power-loss durability, hostile-root/final-path races, full snapshot freshness,
deep graphs, AES interoperability/resource bounds and independent state-machine
proofs remain separate obligations in the repository-wide algorithm program.
CAS fallback guarantees correct cooperating-writer bytes, permits inode
replacement and may reject a raced reader identity; callers explicitly retry
after publication settles. Abrupt death may leave private staging.
