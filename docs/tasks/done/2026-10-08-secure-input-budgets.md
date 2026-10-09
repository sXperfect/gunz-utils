# RS-02: SecureStore/crypto input budgets and security gaps

**Status:** Complete for stated Linux audit/repair scope; follow-ups recorded
**Parent:** [Resource/security audit](2026-10-08-resource-security-audit.md)

Review ext/secure_store.py and ext/secure_crypto.py against GAP-008/ALG-050 and
completed SP/AR evidence. Examine key/salt/record reads before allocation, decoding,
KDF parameter/input budgets, authenticated tampering/downgrade behavior, rejected
unlock mutation, diagnostics and key-material lifetime. Distinguish independent
known-answer/component tests from existing malformed-format coverage. Do not
reopen accepted trusted-root, snapshot rollback or OS ACL limits as new bugs.

Own this record and `tests/test_secure/test_secure_input_budget_audit.py` only;
production source and shared registry stay read-only until coordinator assigns a
confirmed repair. Follow parent policy; bounded synthetic stores and fixture bytes
only. Record exact trust/domain/size contract and bytes consumed before rejection.

- [x] GAP-008 reconciled against actual current coverage.
- [x] Bounded independent authentication/input-budget cases run on both Pythons.
- [x] Confirmed defects distinguished from caller budgets and platform limits.

## Reviewed inventory and contracts

Reviewed current SecureStore initialization/private reads, candidate unlock,
authenticated record policy, generation checks, mutation transactions, envelope
decoding, rotation/recovery, audit messages and lock/close lifetime; reviewed
secure_crypto AES wire parsing and PBKDF2. Prior AR-04 policy/rotation, SP-02
independent process and SP-03 crash/authentication-preservation regressions remain
relevant. Existing secure_crypto malformed salt/hex tests already exist: GAP-008
is an independent-oracle/resource-admission gap, not absent malformed coverage.
No registry promotion or package-wide/security/advisory certification is claimed.

Persistent generated Fernet keys are 44 encoded bytes and store salts 16 raw
bytes. Private reads reject symlinks/nonregular files and verify POSIX ownership;
the trusted store root and platform ACL/reparse assumptions remain prerequisites.
Variable plaintext/ciphertext, JSON/base64 envelopes, SQLite result sets and
rotation lists have no published universal payload-size admission limit. Their
linear allocation and caller request/passphrase/rate budgets are distinguished
from fixed-format persisted material. PBKDF2 iteration count is fixed at 600,000;
caller rate limiting is explicitly required by secure_crypto. No huge workload,
unbounded read or production store was exercised in this audit.

## Confirmed defects and proposed focused repairs

1. **Rejected unlock publishes unrelated missing material.** At
   `src/gunz_utils/ext/secure_store.py:742` and `:768`, an existing database with
   its primary key/salt missing and no pending candidate receives a newly
   generated key/salt before current policy authentication. Unlock then rejects
   but leaves an unrelated 44-byte key/16-byte salt. Synthetic snapshots prove
   DB metadata and ciphertext unchanged; original material was already missing,
   so this is recovery-state mutation rather than deletion of an available key.
   Requires local corruption/deletion/restored incomplete material within the
   trusted-root domain. Proposal: allow material generation only for a genuinely
   fresh empty database; existing authenticated metadata or records fail closed
   without publishing a replacement. Two strict regressions currently fail.
2. **Malformed primary prevents independently valid pending recovery.** At
   `secure_store.py:750`, eager Fernet construction aborts on a 13-byte malformed
   primary before the valid pending key is tried. Synthetic committed rotation
   paused before promotion leaves pending key that independently decrypts the
   current strict policy; current unlock raises ValueError. The valid pending
   material survives, so this is recovery availability rather than total loss.
   Proposal: skip bounded format-invalid regular-file candidates, verify another
   candidate cryptographically before promotion, and retain ownership/symlink/
   unsafe-read failures. One strict regression currently fails.
3. **Unsigned generation reset permits obsolete-key new writes.** At
   `secure_store.py:696`, mutation freshness compares only the unsigned database
   counter; `set`'s new-name branch (`:915`) never authenticates current policy.
   After passphrase rotation from generation 1 to 2, changing only the counter
   to 1 lets a still-unlocked old instance successfully set a new secret and
   commit a success audit. The current signed key_check stays byte-identical;
   independently retained obsolete Fernet decrypts the future value. Requires
   DB write access plus an available stale writer/obsolete key; confidentiality
   of future writes and claimed rotation isolation are affected. This does not
   replay or forge an authenticated whole snapshot. Proposal: authenticate the
   current key_check/policy with the active key under the mutation lock before
   encryption, in addition to checking generation. Fully authenticated old
   snapshot replay remains the documented external-freshness exclusion. One
   strict regression currently fails.

All production source remains unchanged in this phase. Strict tests deliberately
remain failing; do not suppress them or reinterpret them as repaired evidence.

## Bounded resource observations

- `_read_private` (`secure_store.py:446–469`) uses `read()` without a byte limit.
  Descriptor instrumentation with a 4,096-byte synthetic malformed key observed
  one request `read(-1)` returning all 4,096 bytes before rejection. Synthetic
  salt files of 1 and 4,096 bytes each read in full and invoke one real 600,000-
  iteration PBKDF2 before InvalidToken; `_derive_key` (`:807`) does not enforce
  persisted salt length. Proposed follow-up: bounded key reads with an explicitly
  documented whitespace policy and exact 16-byte salt admission before KDF.
  These are fixed-shape admission gaps, not demonstrated memory exhaustion.
- `secure_crypto.py:102–113` splits and unhexes every field before fixed salt/IV/
  tag validation. A 2,119-byte wire with one-byte salt decodes field pairs
  (encoded, decoded) `(2,1), (24,12), (32,16), (2048,1024)` before rejecting.
  KDF does not run. Early fixed-field shape rejection can avoid needless payload
  decode; arbitrary valid ciphertext size remains a caller budget unless an
  explicit API cap is adopted. No universal-size violation is alleged.
- Record decoding and rotation retain payloads proportional to input/record
  totals. No independent recursion/leak defect was demonstrated here; bounded
  caller admission, trusted authenticated envelope and total database size are
  separate limits from persisted key/salt format.

## Independent crypto, lifetime and diagnostic evidence

The new module uses two independent
[upstream OpenSSL AES-256-GCM vectors](https://github.com/openssl/openssl/blob/master/test/recipes/30-test_evp_data/evpciph_aes_common.txt)
for empty/16-zero-byte plaintext with zero key and IV. Only entropy and KDF are
stubbed in these wire/AES cases; a separate real 600,000-iteration PBKDF2 test
compares cryptography output to `hashlib.pbkdf2_hmac`, including UTF-8 passphrase.
Actual encrypted wire salt, IV, tag and ciphertext tampering each rejects with
InvalidTag. Six fixed component boundaries and three additional malformed hex
components reject before KDF. These augment existing malformed tests rather
than duplicating a claim that they were missing.

Weakref/GC cases show lock, close and rotation release unreferenced old Fernet
objects. The exposed Fernet property can intentionally remain caller-owned;
Python immutable key bytes are not securely zeroized and externally retained
exceptions/tracebacks may retain locals. No process cache or retained-unreachable
Fernet leak was found. RSS changes alone were not used as proof.

Crypto rejection diagnostics exclude the synthetic passphrase/plaintext.
Inspected SecureStore audit fields contain caller/action/name/status, not secret
value or passphrase; caller-controlled identifiers can themselves contain
sensitive labels. ACL caller labels remain application authorization inputs,
not independently authenticated operating-system identities. Explicit trusted
legacy migration and modern policy rejection contracts remain unchanged.

## Commands and actual results

Synthetic ignored probes: `tmp/rs02/probe.py`, `generation_probe.py`,
`budget_probe.py`, `decode_probe.py`. Maximum malformed fixture read was 4,096
bytes; AES decode fixture decoded 1,024 ciphertext bytes. No real secrets or
stores, installs, commits, CI/remote operations or external report occurred.

- Python 3.11.14 maintained environment:
  `timeout 90 /tmp/gunz-utils-audit-20261008/bin/python -m pytest
  tests/test_secure/test_secure_input_budget_audit.py -q -p no:cacheprovider`:
  **19 passed, 4 failed in 14.49s** (the four strict cases above).
- Python 3.12.13 maintained environment, same module/options:
  **19 passed, 4 failed in 8.08s**. A subsequent helper-only typing correction
  changed snapshot metadata from list-of-pairs to equivalent dict; final 3.11
  rerun above confirms the same four failures. No source change occurred.
- Pinned Ruff 0.14.10 check of the new module: passed.
- Pinned mypy 1.19.1 `--follow-imports=silent --cache-dir tmp/rs02/mypy`
  on the new module: passed, no issues in one source file.
- cryptography 50.0.2 and pytest 9.0.3 are from the isolated maintained envs.

Next: coordinator assigns narrow repairs and defines fixed key-format admission;
rerun strict evidence plus existing secure/process/crash suites on both versions.

## Coordinator completion and retained limits

The three focused repair packets passed. Independent SecureStore review moved
policy/generation verification inside SQLite write exclusion; deterministic raw
writer probes cover owned and joined transactions. Original failing regressions
remain strict and pass. Prior failed audit evidence above is historical prepatch
evidence and must not be presented as a current source failure.

All six canonical gates passed: release, Ruff/mypy, full Python tests, strict
Sphinx, packaging isolation and Python 3.12 compatibility. JSON summary:
`tmp/resource-security-integrated-ci-summary.json`. Python 3.11 collected before
four final verifier exclusion regressions were added: 1,440 passed, 38 documented
skips. Python 3.12 collected the final tests: 1,444 passed, 38 skips. The final
41-case verifier suite also passed separately on BOTH versions, and final
Ruff/mypy/release reruns passed. No earlier result was rewritten to change counts.
Compiled-native proof suites pass 91 per version; fallback passes 60 with 31
explicit native-only exclusions. The maintained native gate now retains RS-03.

Stable-source harness JSON:
`tmp/np03/resource-security-linux-platform-evidence.json`. Both interpreters
pass 18 filesystem, 75 secure-store, 34 subprocess, 60 fallback and 91 native
cases. Only the fallback phases have 31 exactly matched expected exclusions;
zero unexplained gaps. Report status prepared, complete/source_unchanged true,
native_platform_complete false. Fingerprint (236 files, SHA-256):
`503ec4a63120b5817a37604248162a5de9ab71de87b18b150ba61ba08bd5d521`.
The first evidence runner was interrupted to integrate exact new native-only
fallback exclusions; the final run is the completed stable-source evidence.

Registry families ALG-025/050/056/077 and new scoped ALG-079 ownership evidence
are reconciled; historical levels are not blanket-promoted. Fixed key/salt input
admission is tracked separately in
[the pending task](../pending/2026-10-08-fixed-key-input-admission.md).
Real Windows/macOS execution, hostile roots, authenticated whole-snapshot
freshness, arbitrary caller payload budgets and sanitizer/allocator-failure
proofs remain outside this completed Linux repair scope. No leak-free or
security-certification claim follows from finite probes. Existing user edits
are preserved; no commit, push, release, remote execution or public report.
