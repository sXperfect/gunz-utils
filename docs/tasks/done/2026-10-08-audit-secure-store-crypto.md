# AU-02: SecureStore recovery and cryptographic boundaries

**Date:** 2026-10-08
**Role:** Audit researcher
**Status:** Done — initial review; scoped repair results recorded below
**Priority:** P1
**Parent:** [Audit follow-up](2026-10-08-audit-follow-up.md)
**Baseline:** `80bde76a641ce4577574fde60ec957251aee2ba0` plus existing dirty tree

## Question and scope

Do the current implementations uphold their documented security, correctness,
boundedness, and failure contracts? Scope: ext/secure_store.py, ext/secure_crypto.py; tests/test_secure/.

## Review obligations

Recent unlock/rotation recovery, cross-instance/process locks, stale lock identity, SQLite commit/rollback failure, audit/mutation atomicity, ACL envelope authentication, strict migration and downgrade rejection. Check malformed crypto lengths/hex, authenticated tampering, and expensive parsing/KDF ordering; do not assume historical GAP-008 still describes current coverage.

## Method and verification

Review existing secure-store audit/regression suites and crypto malformed-format tests. Use temporary stores and synthetic keys. Exercise transaction failure, concurrent rotation/read/write/unlock, tampered metadata/ciphertext, and recovery after interruption. Do not copy secrets into findings.

Read and obey the parent's shared execution contract. During the initial review,
this file is the worker's only permitted tracked write. Implementation repairs
are proposed for a separately coordinated follow-up.

Existing audit environment candidate:
`/home/adhisant/tmp/miniforge3/envs/gunz-utils/bin/python`.
The coordinator confirmed Python 3.11, pytest, mypy, and cryptography are
available; Ruff is absent. Record actual tool versions and results yourself.

## Deliverables and acceptance

- [x] Source and relevant test inventory reviewed.
- [x] Contract/trust model and parameter domains recorded.
- [x] Findings separated into confirmed defects, proof gaps, stale records,
      and accepted limitations, with source locations and severity rationale.
- [x] Executed commands, results, skips, and reproducible trigger recorded.
- [x] Follow-up repairs specify file ownership, dependencies, and regression checks.
- [x] Coordinator receives a concise findings summary.

## Review inventory and contract

Reviewed `src/gunz_utils/ext/secure_store.py` and `secure_crypto.py`, plus
`tests/test_secure/test_secure_store.py`, `test_secure_crypto.py`,
`test_secure_store_a1_audit.py`, and `test_a1_secure_store.py` (implementation and
focused regression inventory; selected regression bodies inspected in detail).
Read repository AGENTS.md, SECURITY.md, security audit methodology, and
algorithm correctness guide.

SecureStore uses SQLite transactions, per-instance RLocks, and a reentrant
OS file lock for coordinated mutations/unlock/rotation. Fernet envelopes bind
record name and ACL to encrypted payload; legacy acceptance is controlled by
`store_meta.record_format`. Rotation commits rewritten records and key metadata
before promoting a durable pending key/salt. Failed publication should recover
on a later unlock, and stale instance keys should fail closed.

Inputs: names are nonblank strings of at most 512 characters without NUL/control
characters; identities are nonblank strings of at most 256 characters without
comma/NUL; ACLs are deduplicated lists of identities. Values are str/bytes.
Passphrases are nonempty strings; mode switches require an explicit bool opt-in.
Audit limit is an integer (excluding bool) in [1, 10000]. AES helpers require
explicit passphrases, 16-byte salts, 12-byte IVs, and 16-byte tags; plaintext and
legacy wire formats fail closed except explicit plaintext migration.

Threat model: application callers supply identity strings; this is a cooperative
ACL facility, not independent user authentication. File-key mode protects against
other OS users, not a party that can read the master key. Database tamper review
is especially relevant to passphrase mode or modified offline database copies
without key access. The downgrade finding requires a saved same-generation
legacy ciphertext, not the ability to create arbitrary authenticated ciphertext.

## Findings

### Confirmed AU-02-F1: strict migration policy can be downgraded by metadata deletion

**Priority P1; local risk high within the database-tampering threat model.**
Source: `secure_store.py:645-650`, consumed at `get_bytes:907`,
`set:823`, `delete:945`, `rotate_master_key:1117`, and `verify_integrity:1251`.
`migrate_records:1183-1186` promises permanent metadata binding after migration.

Trigger: save a legitimate legacy ciphertext from before migration; migrate;
replace that row's ciphertext with the saved token and loosen the row ACL; delete
`store_meta.record_format`. Observed: the replay is rejected while the strict
marker exists, but after deletion an unauthorized caller reads the synthetic
value and `verify_integrity()` returns True. No new ciphertext/key forgery is
needed. An unexpected marker value also falls back to legacy acceptance by
inspection. This is narrower than whole-database rollback: migration/name/ACL
binding is disabled by removing one unauthenticated policy marker.

Coverage: `test_legacy_record_migration_and_strict_envelope_enforcement` tests
strict rejection while the marker remains and deliberately deletes the marker
when constructing a legacy fixture. It does not test marker deletion/corruption
following migration with replayed pre-migration ciphertext.

Proposed repair: make legacy acceptance explicit and fail closed for damaged
modern metadata; authenticate the format policy with the key-check metadata.
Missing authenticated policy must not silently enable legacy acceptance.
Preserve genuine legacy migration via an explicit trusted upgrade path. Document
that complete authenticated snapshot rollback still needs external freshness
state; this finding does not promise to solve general rollback attacks.

### Confirmed AU-02-F2: rotation rollback failure poisons the live store

**Priority P1; local risk medium (failure recovery/availability).**
Source: `secure_store.py:1168-1173`; compare hardened ordinary mutation cleanup at
`_transaction_locked:767-795`.

Trigger: inject SQLite OperationalError for both rotation COMMIT and its cleanup
ROLLBACK. Observed: the ROLLBACK exception masks the COMMIT exception; the
connection remains in a transaction, the pending key remains, and a later set
fails with a stale-key RuntimeError because the connection sees uncommitted new
generation metadata while the instance retains its old key generation.
This is deterministic fault injection, not proof that every real SQLite COMMIT
failure leaves this transaction state. Closing/reopening can recover; the live
instance does not restore its usable invariant.

Coverage: existing ordinary-set COMMIT failure regression exercises real SQLite
reader contention and verifies future writes work. Rotation tests cover database
failure/publication failure, but not a failing rollback during rotation cleanup.

Proposed repair: reconcile transaction outcome, reconnect when rollback cannot
restore state, preserve original failure, and safely retain or remove pending
material based on the actual persisted generation. Do not simply delete pending
material whenever COMMIT raises: a failure after durable commit needs that key.

### Proof gaps requiring follow-up

- Inter-process locking is implemented, but the focused test inventory has no
  process-based rotation/unlock/write adversarial schedule. The test named
  `test_concurrent_unlock_does_not_destroy_in_flight_rotation_pending_key` checks
  lock depth and then unlocks the second instance after rotation; it does not
  actually overlap an unlock operation. Add event-controlled process tests.
- Lock-file identity is not revalidated after acquiring a lock on an opened inode
  (`_ReentrantFileLock:145-166`). Replacement by a same-owner actor can split lock
  ownership; this initial review did not reproduce a race or establish that such
  an actor is inside the supported trust model. Record the trust assumption and
  test identity replacement if it must be supported.
- Reads of key files, envelope JSON/base64, and AES hex payloads are unbounded.
  AES decoding allocates before validating component lengths (`secure_crypto.py:
  104-113`); `_derive_key:742-748` lacks the AES helper's exact salt-length check.
  No documented universal payload-size bound was established. Treat these as
  resource/validation obligations, not confirmed cryptographic breaks. Review
  size budgets and persisted salt validation, coordinating AU-05.
- AES suite lacks independent known-answer interoperability and component-tamper
  coverage for salt, IV, tag, and ciphertext. Fernet ACL/substitution regressions
  do exist. KDF rate limiting remains a caller responsibility documented in
  `secure_crypto.py:44-46`.

### Stale evidence and accepted limitations

Malformed AES salt-length/hex regressions already exist and pass; historical
GAP-008 must not be treated as wholly missing coverage. The malformed-length test
currently covers one short salt, rather than exhaustive IV/tag boundaries.
Caller identity authentication, arbitrary same-UID malicious processes, and
complete rollback freshness are application/OS concerns unless the public
contract is deliberately expanded. Native process/platform lock behavior,
dependency advisories, fuzzing, and full canonical verification were not covered
in this bounded first-wave review.

## Verification evidence

Baseline: HEAD `80bde76a641ce4577574fde60ec957251aee2ba0`. SecureStore, crypto,
and their tests were clean in the inspected status. Existing dirty files included
CHANGELOG.md, deleted release fragments, pyproject.toml, enums.py, models.py,
and coordinator task/index files. None was altered by this worker, other than
this assigned child task file. No source/tests were edited.

Interpreter: `/home/adhisant/tmp/miniforge3/envs/gunz-utils/bin/python`;
Python 3.11.14, pytest 9.0.2, cryptography 49.0.0.

```bash
/home/adhisant/tmp/miniforge3/envs/gunz-utils/bin/python -m pytest tests/test_secure -q -p no:cacheprovider
# 64 passed in 10.45s; no skips
/home/adhisant/tmp/miniforge3/envs/gunz-utils/bin/python tmp/au02/probe.py
# Exit 0. Strict replay rejected before marker deletion.
# After deletion: unauthorized legacy replay accepted True; verify_integrity True.
# Rotation error: injected ROLLBACK failure; in_transaction True;
# pending key remains True; subsequent set fails stale-key RuntimeError.
```

The ignored temporary reproduction script uses synthetic data in temporary
stores under `tmp/au02/`. Initial sandbox exec failed during bwrap loopback
initialization; narrowly described escalated read/local-probe calls succeeded.
No packages were installed and no external reporting/publishing occurred.
Focused existing tests and temporary probes do not constitute A3/A4 promotion
or a complete deep audit.

## Proposed follow-up tasks

1. **AU-02-R1, P1:** authenticate strict-format policy and explicit legacy
   migration routing. Own `secure_store.py`, the secure-store migration tests,
   relevant public docs, registry evidence and a coordinated security fragment.
   Regression: pre-migration token replay + marker deletion/replacement must
   fail for read/overwrite/delete/integrity; trusted legacy import still works;
   reopen and rotation preserve strict policy.
2. **AU-02-R2, P1:** repair rotation transaction cleanup. Same source ownership
   as R1; schedule sequentially or assign one owner. Regression: body/COMMIT/
   ROLLBACK failures, failures before versus after durable commit, pending key
   recovery, and subsequent live-instance operations against independent
   reopened-store state.
3. **AU-02-R3, P2:** process-controlled locking and crash-recovery proof tests,
   plus lock identity threat-model decision. Own secure-store tests; coordinate
   source changes with R1/R2 and filesystem audit AU-01. Test actual overlapping
   unlock/rotate/write schedules, stale generations, and abrupt process exits.
4. **AU-02-R4, P2:** AES known-answer/tamper/boundary proof packet and resource
   contract. Own `secure_crypto.py` and its tests; coordinate input-size/salt
   obligations with AU-05. Test salt/IV/tag boundaries before KDF and component
   tampering through the authenticated primitive. No custom cryptography.

Run applicable focused checks during repairs and the canonical repository gate
before integration; coordinator AU-06 owns shared registry/index reconciliation.

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
