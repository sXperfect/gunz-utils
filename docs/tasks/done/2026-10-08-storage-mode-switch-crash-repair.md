# SP-04: Complete authenticated mode-switch publication recovery

**Date:** 2026-10-08
**Status:** Done — approved repair and scoped process proofs verified
**Parent:** [Cross-process proof program](2026-10-08-storage-process-proofs.md)
**Evidence:** [SP-03 abrupt-exit packet](2026-10-08-storage-store-crash-recovery.md)

## Confirmed trigger and contract

An independent spawned process is killed after real pending-key rename during
passphrase-to-file rotation and before old salt unlink. SQLite has committed the
new generation and authenticated envelopes. Fresh file-key unlock/read/write
succeed, but old master.salt remains and a subsequent file-key rotation raises
a protection-mode downgrade error. SP-03 executed 23 passing cases and this
strict failing case; this is a process crash, not a simulated COMMIT failure.

Recovery should finish publication cleanup after the candidate key, current
generation and record policy authenticate. The analogous file-to-passphrase
boundary must remove obsolete master.key. Wrong credentials/corrupt policy must
never trigger destruction of current or recoverable key material.

## Ownership and repair

SP-02 worker exclusively owns `ext/secure_store.py`, dedicated ordinary recovery
regressions if necessary, this record and a uniquely named fixed fragment.
SP-03 exclusively owns the actual crash tests; it must retain strict assertions
for secret/ACL/audit/generation state, opposite-mode cleanup and future rotations.
Coordinate before source/test changes; no archived record edits or other helpers.

## Acceptance

- [x] Actual post-rename crash reproduces before source correction.
- [x] Authenticated unlock completes cleanup for both mode transitions.
- [x] Wrong credentials/policy reject without deleting recovery material.
- [x] All real-process matrix cases and existing secure suites pass on 3.11/3.12.
- [x] Pinned Ruff/mypy, canonical combined gate and updated registry evidence pass.

## Results

SP-03 executed 26 strict real-process cases per interpreter: 24 pass and two
post-rename mode-transition cases fail. Both cases leave obsolete opposite-mode
primary material after authenticated reopen. Wrong-credential and damaged-policy
byte-preservation checks pass. The failing regressions are retained unchanged.

Automatic approval review initially rejected both source-edit attempts, stating
that deletion of alternate key material required explicit user authorization.
Neither rejected attempt executed. Coordinator presented the concrete proposal
at tmp/sp04/recovery-proposal.patch and asked explicit authorization to remove
obsolete opposite-mode primary material after authenticated recovery. The user
answered "Continue" to that question; coordinator applied that exact proposal.
Approval is resolved. No live production store was touched.

The source delta is 12 added lines: a private helper removes only the obsolete
opposite-mode primary, and the successful normal-candidate unlock branch invokes
it after key-check, record-policy and generation verification under the process
lock. It completes the same deletion already performed by the existing pending
promotion routine. Missing obsolete files are harmless; successful removal is
followed by directory fsync. Invalid credentials/policy/generation never reach
cleanup. The explicit trusted legacy and snapshot freshness contracts were not
changed. SP-02 independently reviewed the applied delta; no additional source
correction was needed.

Dedicated ordinary tests/test_secure/test_mode_switch_recovery.py adds ten
synthetic cases spanning both mode directions: credential/policy/generation
rejection preserves every primary/pending byte, permission failure retains
current material and supports retry, and post-removal fsync failure preserves
the committed current key for independently reopened access and future rotation.
SP-03's strict real-process tests remained unchanged by this worker.

Full secure suites, including both process modules and these ordinary cases,
passed with plugin autoload disabled:

- Python 3.11.14 / pinned pytest 9.0.3: **131 passed in 55.20s**, no skips.
- Python 3.12.13 / pinned pytest 9.0.3: **131 passed in 55.46s**, no skips.
- Pinned Ruff 0.14.10: source and both SP-02-owned test files passed.
- Pinned mypy 1.19.1, --follow-imports=silent: no issues in those three files.

Commands and detailed evidence are linked in the SP-02 packet. Unique fixed
fragment changes/20261008-mode-switch-crash-recovery.fixed.md was added.
Source/tests were exercised only against synthetic temporary stores; no shared
environment install, commit, publication or archived-record edit was performed.
Coordinator retains canonical combined-gate, registry/index and integration
ownership; this focused result does not claim A4 by itself.

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
