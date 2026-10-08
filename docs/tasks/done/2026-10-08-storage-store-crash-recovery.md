# SP-03: SecureStore abrupt process recovery

**Date:** 2026-10-08
**Status:** Done — approved repair and scoped process proofs verified
**Parent:** [Cross-process proof program](2026-10-08-storage-process-proofs.md)
**Base:** `3f474ad961239193bee8fc9f9695e0492bad74a7` plus preserved user edits

## Scope and ownership

Terminate actual worker processes at acknowledged boundaries: after pending key/salt staging before SQL commit, during transaction, after durable commit before publication, and after publication. Reopen independently and verify old/new committed generation, all secret envelopes/ACLs and audit rows, recovery/cleanup of pending material, and future writes/rotation. Cover file-key and passphrase transitions where meaningful. Use SIGKILL/process.kill or os._exit deliberately; monkeypatch only to place a barrier around real operations, not to fake durable commit outcomes.

Own only `tests/test_secure/test_secure_store_process_crash.py`, this child record, and `changes/20261008-store-process-crash-proofs.internal.md`. Follow parent
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

## Contract and proof matrix

Implemented tests/test_secure/test_secure_store_process_crash.py with 26 strict
cases, using multiprocessing.get_context("spawn") and top-level child entrypoints:

- Twenty rotation cases: file→file, passphrase→passphrase, file→passphrase,
  passphrase→file across acknowledged pending staging, fully rewritten open
  transaction before COMMIT, real returned COMMIT before publication, real pending
  os.replace before opposite-mode primary unlink, and completed publication.
- Four mutation cases: file/passphrase stores killed immediately before/after
  real COMMIT, covering the secret value and its successful set audit row together.
- Two rejection cases: interrupted mode switches with a deliberately damaged
  authenticated format marker; rejection must preserve primary and pending bytes.

Each crash child blocks after reporting exact boundary, PID and actual SQL
in_transaction state. The parent calls Process.kill, joins and verifies nonzero
exit, then opens SQLite independently. Hooks surround actual operations only;
no fake COMMIT outcome, mocked SQL persistence or normal exception rollback
stands in for process death. A second independent spawned process performs
credential verification, recovery, ACL checks and subsequent write/rotation.

Oracle: direct SQLite snapshots of metadata/generation, every secret row and
ordered audit rows before recovery. Precommit crashes must preserve all durable
SQL bytes/rows; postcommit rotation must increment generation and preserve the
same plaintext/ACLs/audits under actual new key material. Fernet decryption and
independent JSON/base64 envelope parsing check name, ACL and synthetic bytes;
passphrase mode derives from the real salt via PBKDF2HMAC's documented 600000
SHA256 iteration contract, not SecureStore._derive_key or _decode_record.
Mutation commit publishes exactly one new successful set audit row with the new
value; uncommitted death publishes neither. Wrong credentials are tried before
valid recovery and must leave every primary/pending material byte unchanged.

Correct recovery must remove pending and opposite-mode primary material only
after authenticating policy/key/generation. Its next same-mode rotation must
work without a mode-switch opt-in. All inputs are synthetic, two finite secrets
with explicit writer/reader ACLs; callbacks and barrier fields are bounded.

Resource contract: readiness/reopen polls ≤20s; joins ≤5s with unconditional
kill/reap in finally and a second bounded join if needed; Pipe endpoints and
Process objects close; independent SQLite oracle connections explicitly close.
The child checkpoint's recv is deliberately held only until parent kill under
that bounded parent schedule. No unbounded Queue drain, sleeps for race placement,
external service, credentials, live database or power-failure simulation.

## Confirmed SP-03-F1: incomplete mode-switch publication recovery

Source: ext/secure_store.py:_promote_pending_key_material (lines565-574),
unlock normal verified candidate branch (lines782-787), and
rotate_master_key mode detection (lines1126-1130). Local risk medium:
crash recovery leaves an inconsistent protection-mode filesystem state.

Actual death after real pending material rename and before opposite-mode unlink:

- file→passphrase: committed new generation/envelopes decrypt with the new
  passphrase, but authenticated reopen leaves obsolete master.key.
- passphrase→file: committed new generation/envelopes decrypt with new file key,
  but authenticated reopen leaves obsolete master.salt. Initial proof additionally
  established reads, ACL denial and future set work, then same-mode rotate(None)
  wrongly rejects as an unrequested downgrade because it infers mode from stale
  salt presence.

The strengthened oracle checks obsolete primary absence immediately after reopen
for both transitions; these were strict failing regressions before the approved
source repair and now pass unchanged.
There is no claim that the old key decrypts current new-generation records.
Initial 24-case matrices before stronger mode checks each reproduced the future
rotation failure on Python3.11/3.12 (23 passed, 1 failed). Wrong-credential and
policy-rejection material preservation pass after correcting the rejection test's
exception expectation from RuntimeError to the API's actual InvalidToken.

Proposed source repair: complete opposite-mode primary cleanup after successful
candidate key/policy/generation verification even when candidate is already
published, then fsync directory; never delete material on failed credential or
policy verification. SP-02 owns source changes; this worker remains tests-only.
The two modes and failure-preservation cases are included in this packet rather
than replacing the failing proof with xfail/skip/weaker acceptance.

## Executed evidence and limits

Base HEAD3f474ad961239193bee8fc9f9695e0492bad74a7,
branch audit/cross-process-storage-20261008 with preserved user edits.
Pinned Python3.11 and3.12 interpreters and pytest9.0.3; Ruff0.14.10/mypy1.19.1.
Commands (PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 for all pytest runs):

```bash
/tmp/gunz-utils-audit-20261008/bin/python -m pytest -q --tb=short tests/test_secure/test_secure_store_process_crash.py
/tmp/gunz-utils-audit-20261008-py312/bin/python -m pytest -q --tb=short tests/test_secure/test_secure_store_process_crash.py
# Each:24 passed,2 confirmed recovery failures in31.14s; no skips
/tmp/gunz-utils-audit-20261008/bin/ruff check tests/test_secure/test_secure_store_process_crash.py
# All checks passed
/tmp/gunz-utils-audit-20261008/bin/mypy --cache-dir tmp/sp03-mypy tests/test_secure/test_secure_store_process_crash.py
# Success: no issues found in1 source file
git diff --check
# Passed
```

Proofs execute on Linux with local files/SQLite, not native Windows/macOS nor
network filesystems; spawn entrypoints/Process.kill cleanup are portable, but no
unexecuted OS guarantee is claimed. OS process death leaves SQLite/OS recovery
facilities alive, unlike power loss; disk/controller/filesystem persistence under
power failure is outside this result. Full canonical gate and registry/index
integration remain coordinator responsibilities. No A3/A4 promotion is claimed from focused proof execution; final canonical
verification remains coordinator-owned. Fragment:
changes/20261008-store-process-crash-proofs.internal.md.

Automatic approval review initially rejected SP-02's runtime opposite-mode
primary-material cleanup proposals, requiring explicit authorization. The user
then answered Continue to the coordinator's concrete cleanup-patch approval
question. Coordinator applied the reviewed 12-line source patch; this worker
kept source read-only and reran the unchanged strict crash module. The new helper
cleans opposite primary material only after successful candidate/policy/generation
verification and fsyncs the directory. No approval workaround was attempted.

## Pre-repair matrix results

Pre-repair stable-file results: **Python3.11:24 passed,2 failed in31.14s**;
**Python3.12:24 passed,2 failed in31.14s**. Both failures are the post-rename
file→passphrase/passphrase→file obsolete primary material cases. No skips or
warnings. Independent SQL generation/secret/ACL/audit oracles pass before these
failures; all mutation atomicity and rejection-preservation cases pass. Every
child was unconditionally killed/reaped or exited and reaped. Final module Ruff,
mypy and whitespace checks pass; these runs preceded explicit cleanup approval.



## Approved repair verification

After the explicit user authorization and coordinator's stable source patch,
the **unchanged 26-case module** was rerun with plugin autoload disabled:

```bash
PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 /tmp/gunz-utils-audit-20261008/bin/python -m pytest -q --tb=short tests/test_secure/test_secure_store_process_crash.py
# 26 passed in 35.05s; no skips/warnings
PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 /tmp/gunz-utils-audit-20261008-py312/bin/python -m pytest -q --tb=short tests/test_secure/test_secure_store_process_crash.py
# 26 passed in 34.23s; no skips/warnings
```

Both opposite-mode PRIMARY checks now pass after authenticated independent
reopen, and next same-mode rotation/future mutation succeeds. Wrong-credential
and damaged-policy rejection preserve all primary/pending bytes and leave the
store locked. The preceding 24-pass/2-failure results remain historical evidence
of the reproduced defect. No regression assertion was weakened or skipped;
Ruff/mypy proof-module checks previously passed and the module remained unchanged.
Coordinator owns shared record reconciliation, source static checks and the full
aggregate gate. Every crash/verifier child was stopped and reaped.

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
