# Cross-process storage proofs

**Date:** 2026-10-08
**Status:** Done — approved repair and scoped process proofs verified
**Owner:** Coordinator
**Base:** `3f474ad961239193bee8fc9f9695e0492bad74a7`
**Branch:** `audit/cross-process-storage-20261008`
**Predecessor:** [Completed audit repairs](2026-10-08-audit-follow-up.md)

## Goal and hierarchy

Replace the remaining simulated/thread-only storage evidence with bounded real
process schedules. Prove cooperating CAS publication, SecureStore coordination,
and recovery after actual abrupt process exit. Do not expand promises into
power-loss durability, hostile same-account authentication, or snapshot freshness.

| Task | Worker scope | Dependencies |
|---|---|---|
| [SP-01: CAS publication](2026-10-08-storage-cas-process-proofs.md) | Independent publisher/reader processes; normal and forced fallback | Audited CAS |
| [SP-02: SecureStore coordination](2026-10-08-storage-store-process-locks.md) | Independent stores, locks, rotation, stale generations | Audited SecureStore |
| [SP-03: Crash recovery](2026-10-08-storage-store-crash-recovery.md) | Actual process death before/after transaction and key publication | Coordinate any source repair with SP-02 |
| [SP-04: Mode-switch recovery repair](2026-10-08-storage-mode-switch-crash-repair.md) | Authenticated opposite-mode primary cleanup after partial publication | Confirmed SP-03 failure; exclusive source owner SP-02 |

## Ownership and execution

- Preserve existing user version, changelog, fragment deletions and enum/model
  export edits. No reset/stash, release, merge, push or external disclosure.
- First implement dedicated tests and proof records only. SP-01 owns
  `tests/test_core/test_cross_process_content_store.py`; SP-02 owns
  `tests/test_secure/test_cross_process_secure_store.py`; SP-03 owns
  `tests/test_secure/test_secure_store_process_crash.py`.
- Each worker owns its corresponding child task record and a unique internal
  fragment. Coordinator owns shared registry/index and integration evidence.
- Confirmed source defects must be reported with a reproduction before repair.
  Assign one owner per source; SP-02 coordinates all SecureStore source repairs
  and SP-01 coordinates CAS repairs. SP-03 does not edit SecureStore concurrently.
- Read AGENTS.md and canonical security/algorithm methodology. Use synthetic
  secrets and temp directories, explicit spawn where portable, top-level child
  entrypoints, readiness barriers/events, bounded waits, and unconditional child
  reap/cleanup. No timing-only stress claims or unbounded Queue joins.
- Each proof states its contract, admissible domains, independent byte/generation/
  transaction oracle, forced interleaving, failure conditions, platform limits,
  and executed command/result. Distinguish process crash from power failure.
- Use `/tmp/gunz-utils-audit-20261008/bin/python` (Python3.11) and
  `/tmp/gunz-utils-audit-20261008-py312/bin/python` (Python3.12), pinned pytest9.0.3.
  Pinned Ruff/mypy are in the first env. Set PYTEST_DISABLE_PLUGIN_AUTOLOAD=1.
- Temporary probes stay under ignored uniquely named `tmp/sp01`, `tmp/sp02`,
  `tmp/sp03`. Do not edit archived records or install into shared environments.
- Do not promote A3/A4 without required execution. Final coordinator checks the
  combined tests, static gates and canonical full gate where applicable.

## Acceptance

- [x] Normal/fallback same-digest CAS process schedules preserve correct content.
- [x] CAS publication failures never report unverified success; inode replacement
      is distinguished from corruption and crash-left staging is characterized.
- [x] Real SecureStore locks serialize cooperating mutations/unlock/rotation;
      stale owners fail closed and can explicitly refresh safely.
- [x] Abrupt process exit preserves recoverable old/new committed state, secret/
      audit atomicity and correct pending material without invented guarantees.
- [x] Every child is stopped/reaped, all waits bounded, temporary outputs isolated.
- [x] Both supported Python versions, pinned lint/type and applicable full gates
      pass; registry/index reflect actual evidence and remaining platform limits.

## Evidence

### Current focused results and blocker

SP-01: 12 actual-spawn CAS cases pass on Python 3.11 and 3.12. SP-02: 10 actual
OS-lock/SQLite coordination cases pass on both. SP-03: 24 of 26 actual crash cases
pass on both; two strict mode-switch post-rename recovery failures remain.
Combined Python 3.11 packet: 46 pass, two fail. All new proof files pass pinned
Ruff/mypy. The approved CAS get docstring clarifies transient identity rejection;
it adds no implicit retry guarantee.

The user replied **Continue** directly to the explicit request to apply the
concrete SP-04 recovery patch. That authorization supersedes the earlier
automatic-approval blocker. The coordinator applied the reviewed source patch:
obsolete opposite-mode primary cleanup runs only after the candidate key,
generation and record policy authenticate under the process lock. No production
store was touched. Strict previously failing tests remain unchanged and are
being rerun on both interpreters; aggregate verification is pending. The first
audit commit remains `3f474ad`; new proof/repair work is not yet committed.

The preceding repairs were committed as `3f474ad` with only audit-owned files
and the sdist include hunk. User release/export edits were excluded. Exact staged
source passed 1,244 main tests and 57 actual native tests per interpreter after
adding Git metadata to its disposable snapshot; no source test was weakened.

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
