# SP-02: SecureStore process coordination

**Date:** 2026-10-08
**Status:** Done — approved repair and scoped process proofs verified
**Parent:** [Cross-process proof program](2026-10-08-storage-process-proofs.md)
**Base:** `3f474ad961239193bee8fc9f9695e0492bad74a7` plus preserved user edits

## Scope and ownership

Independent SQLite connections and actual OS locks: simultaneous first unlock, overlapping mutation/rotation, two rotations, explicit stale-generation rejection and refresh. Ensure success audit and mutation agree after independent reopen. Cover file-key/passphrase modes with synthetic inputs and readiness-controlled contention, including original lock holder process exit. Reads may fail closed during generation transition; do not invent implicit auto-refresh.

Own only `tests/test_secure/test_cross_process_secure_store.py`, this child record, and `changes/20261008-store-process-lock-proofs.internal.md`. Follow parent
ownership/cleanup rules; propose source repairs to coordinator before editing.
SP-03 coordinates SecureStore fixes with SP-02 and cannot edit that source.

## Deliverables

- [x] Explicit contracts, independent oracle and acknowledged process schedules.
- [x] Portable start/cleanup boundaries; skips identify unsupported OS guarantees.
- [x] Focused proof tests execute with bounded waits and no orphan children.
- [x] Both Python versions and pinned Ruff/mypy results recorded.
- [x] Confirmed defects versus accepted limitations distinguished.
- [x] Coordinator receives summary; final integration evidence remains parent-owned.

## Results

## Contract, domains and oracle

New tests/test_secure/test_cross_process_secure_store.py has ten real-process
cases, parameterized over file-key mode and a synthetic passphrase. Each child
uses explicit multiprocessing spawn, constructs its own SecureStore and SQLite
connection, and receives bounded duplex-pipe commands. No inherited store/key
object or simulated SQLite/file lock is used.

The process-local lock observer first performs an actual nonblocking POSIX flock
attempt on the production descriptor, reports kernel-confirmed contention when
it fails, then calls the original blocking _lock_fd. It does not replace the
lock with an in-memory barrier. Parent sequencing requires both readiness and
actual contention acknowledgment; elapsed sleep is never the oracle.

Private APIs are paused only to force meaningful production boundaries. Mutation
pauses inside the actual set call after row insertion and before its success
audit; rotation pauses inside actual rotate_master_key after the committed new
generation and before pending-key publication. Both callbacks then invoke the
original method. Parent aborts fail the paused callback instead of silently
omitting the original operation.

Accepted domains are deliberately finite: two cooperating processes, bounded
named synthetic records and identical known synthetic credentials for
same-protection-mode rotations. Parent waits are at most 15 seconds each;
cleanup joins at most 1+3+3 seconds before graceful stop/terminate/kill and
asserted reap. Child command waits are bounded too. Production blocking flock
may wait indefinitely in isolation, but parent watchdog/termination bounds this
test's ownership lifetime. No Queue feeder/join or timing-only stress loop.

An independent, explicitly closed parent SQLite connection observes only
committed generation, secret names and ordered successful set audits. A fresh
independent SecureStore later verifies authenticated integrity and exact secret
values. Generation/key-mode primary existence and absence of stale-success audit
rows are checked separately from child event reports.

## Acknowledged schedules and results

| Schedule | Observable invariant |
|---|---|
| First unlock, 2 modes | Both stores exist without key/salt; one holds real flock, the other's first unlock reports contention; exactly generation 1 and one successful audit per committed value survive independent reopen |
| Mutation transaction, 2 modes | Contender set waits on actual kernel lock while holder's actual set is paused before success audit; neither uncommitted value nor success audit is externally visible; release commits value/audit together before contender's write |
| Rotation with stale set/rotation, 4 cases | Actual rotation is paused after DB generation 2 commits but before key publication; old owner reports contention then fails closed after release, creates no stale value/audit, rejects stale read, refreshes explicitly, writes and rotates to generation 3; first owner then also needs explicit refresh |
| Lock-holder process exit, 2 modes | Contender acknowledges real flock contention; parent terminates/reaps holder; kernel releases lock, surviving set succeeds with matching committed audit and independently verified bytes |

No new coordination source defect was confirmed by these ten cases. Observed
stale RuntimeError is the contract, not failed implicit refresh. Cooperative ACL
labels, whole authenticated snapshot freshness and same-account adversaries are
not expanded into new authentication promises.

## Executed verification

Base 3f474ad961239193bee8fc9f9695e0492bad74a7 on
audit/cross-process-storage-20261008 plus preserved user edits. Read repository
AGENTS.md and security/algorithm methodology; earlier reads remain applicable.
Final commands from libs/utils, with PYTEST_DISABLE_PLUGIN_AUTOLOAD=1:

```bash
timeout 90 /tmp/gunz-utils-audit-20261008/bin/python -m pytest tests/test_secure/test_cross_process_secure_store.py -q -p no:cacheprovider
# Python 3.11.14 / pytest 9.0.3: 10 passed in 9.99s
timeout 90 /tmp/gunz-utils-audit-20261008-py312/bin/python -m pytest tests/test_secure/test_cross_process_secure_store.py -q -p no:cacheprovider
# Python 3.12.13 / pytest 9.0.3: 10 passed in 9.87s
/tmp/gunz-utils-audit-20261008/bin/ruff check tests/test_secure/test_cross_process_secure_store.py
# Ruff 0.14.10: All checks passed
timeout 45 /tmp/gunz-utils-audit-20261008/bin/python -m mypy --follow-imports=silent --cache-dir tmp/sp02/mypy-cache tests/test_secure/test_cross_process_secure_store.py
# mypy 1.19.1: Success: no issues found in 1 source file
```

All ten cases executed on Linux/POSIX, no skips. The module explicitly skips
non-POSIX hosts because the acknowledged nonblocking flock proof is specific
to POSIX; it does not certify Windows lock semantics. Startup and cleanup are
spawn-based and all started children are stopped/reaped on failure as well as
success. Final correction after execution only split a long call across lines;
no behavior changed. Earlier ten-case runs also passed before strengthening
pauses to lie inside actual API calls, but final evidence above uses those
stronger boundaries.

Initial owned writes were the dedicated proof file, this record and
changes/20261008-store-process-lock-proofs.internal.md. Source diff for
secure_store.py remained empty at the initial proof capture, before the user
approved the separate SP-04 proposal. Shared registry/index, release metadata
and pre-existing enum/model/export edits were preserved. No installs, commits,
publishing or archived-record changes by this worker.

## Confirmed SP-03 repair dependency and approval boundary

SP-03 independently confirmed a real post-rename mode-switch crash defect:
normal-candidate authenticated recovery leaves the opposite-mode primary file,
which blocks later file-mode rotation and retains obsolete file-key material
after the reverse transition. Its strict crash test remains unchanged by this
worker. Coordinator assigned the source correction to SP-02 in SP-04.

Automatic approval review rejected both proposed source-edit attempts, stating
that the broad audit authorization did not authorize irreversible runtime
removal of alternate key material. The original promotion routine already
performs those removals; the intended repair completes that existing
postcondition only after key/policy/generation verification. Nevertheless, no
retry or alternate execution was performed after the second rejection.

A concrete proposal and rationale were prepared as plain text under ignored
tmp/sp04/recovery-proposal.patch and recovery-proposal-rationale.txt. Coordinator
presented an explicit approval question naming obsolete opposite-mode primary
removal after authentication; the user's direct "Continue" authorized that exact
patch. Coordinator then applied it. No production store was touched. Approval
is resolved; the original rejected attempts themselves did not execute.

## Approved SP-04 review and final secure verification

The exact source correction adds a private cleanup helper and invokes it on the
successful normal-candidate unlock path. Key-check authentication, record policy
validation and generation verification all precede this branch under the
inter-process lock. Only the obsolete opposite-mode primary is removed; current
key/salt is retained. Removal completes the same postcondition already provided
by normal pending-material promotion. Missing obsolete material is harmless;
directory fsync follows successful removal. Wrong credentials or damaged
policy/generation exit before cleanup. Trust/legacy opt-in and full-snapshot
freshness exclusions remain unchanged. This worker independently reviewed the
coordinator's 12-line source delta and made no further source change.

Added tests/test_secure/test_mode_switch_recovery.py (ten synthetic ordinary
cases): both mode directions reject wrong credentials, damaged policy and
damaged generation without changing primary/pending bytes; cleanup permission
failure retains current material and permits a later retry; post-removal fsync
failure may report an error after cleanup visibility, while current committed
key and ciphertext remain recoverable and future same-mode rotation succeeds.
These complement SP-03's unchanged real-death assertions rather than weaken
them. Unique fixed fragment:
changes/20261008-mode-switch-crash-recovery.fixed.md.

Final full secure commands with PYTEST_DISABLE_PLUGIN_AUTOLOAD=1:

```bash
timeout 90 /tmp/gunz-utils-audit-20261008/bin/python -m pytest tests/test_secure -q -p no:cacheprovider
# Python 3.11.14 / pytest 9.0.3: 131 passed in 55.20s
timeout 120 /tmp/gunz-utils-audit-20261008-py312/bin/python -m pytest tests/test_secure -q -p no:cacheprovider
# Python 3.12.13 / pytest 9.0.3: 131 passed in 55.46s
timeout 60 /tmp/gunz-utils-audit-20261008/bin/python -m mypy --follow-imports=silent --cache-dir tmp/sp02/mypy-recovery src/gunz_utils/ext/secure_store.py tests/test_secure/test_cross_process_secure_store.py tests/test_secure/test_mode_switch_recovery.py
# mypy 1.19.1: Success: no issues found in 3 source files
/tmp/gunz-utils-audit-20261008/bin/ruff check src/gunz_utils/ext/secure_store.py tests/test_secure/test_cross_process_secure_store.py tests/test_secure/test_mode_switch_recovery.py
# Ruff 0.14.10: All checks passed
```

Both secure-suite runs include SP-02's ten real coordination proofs, SP-03's
26 strict crash cases, ten new ordinary recovery cases and the prior secure
tests. No skips or failures. All fixture credentials/data are synthetic; no
current or historical production key material was removed by this worker.
Coordinator owns canonical combined gate, registry/index and integration.
No new A4 claim is made by this proof packet alone.

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
