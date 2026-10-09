# RP-01: SecureStore authentication and recovery repairs

**Status:** Complete for stated Linux audit/repair scope; follow-ups recorded
**Parent:** [Parallel repairs](2026-10-08-resource-security-repairs.md)
**Findings:** [RS-02](2026-10-08-secure-input-budgets.md)

Own `src/gunz_utils/ext/secure_store.py`,
`tests/test_secure/test_secure_input_budget_audit.py`, this record and a unique
fixed/security fragment. Other sources and shared registry/index are read-only.

Repair three reproduced findings: authenticate current key-check/policy under
the mutation lock before new encryption as well as generation comparison; allow
key/salt generation only for a genuinely fresh store; try independently valid
pending recovery past a format-invalid primary without swallowing unsafe-file
security errors. Preserve rejected-credential/policy bytes and authenticated
candidate ordering. Retain full authenticated snapshot replay as the documented
external-freshness exclusion. Avoid unrelated budget/crypto changes.

- [x] Four failing RS-02 regressions pass without weakening assertions.
- [x] SecureStore policy/rotation/recovery/crash/coordination suites pass on both Pythons.
- [x] Ruff/mypy, focused security review and unique fragment complete.
- [x] Root integration and independent source review complete.

## Concrete repair and ordering

User authorized the parallel repair parent; production ownership was explicitly
assigned to this agent. Only SecureStore source, the RS-02 dedicated tests, this
record and `changes/20261008-secure-store-auth-recovery.security.md` changed.

`_verify_key_generation` keeps the numeric mismatch RuntimeError first and then
authenticates the current key_check and matching record-format policy using the
active instance key. Existing guarded reads and mutations invoke it under their
locks; new-name set executes it inside the coordination lock and SQLite write
transaction before encryption. Resetting only an unsigned counter cannot make
the stale key authenticate the current signed policy. Full authenticated old
snapshot rollback still requires external freshness and remains excluded.

Before generating absent primary key/salt, unlock now requires all three
store_meta, secrets and audit tables to be empty. Any retained initialization,
record or audit history rejects without publishing unrelated replacement
material. A store with every table emptied is indistinguishable from a new
database; this is not an external rollback/freshness detector. Genuine fresh
store initialization remains covered by existing secure/process tests.

Only Fernet-constructor ValueError for already-read regular-file key candidates
is skipped. Private reads, ownership checks, symlink/nonregular errors and I/O
errors occur outside this catch and continue to propagate. Another candidate
must independently verify signed policy, format and generation before existing
pending promotion or authenticated opposite-mode cleanup can run. Rejected
credentials/policy leave candidate bytes unchanged. Salt length, read budgets,
key whitespace and crypto APIs are untouched; RS-02 resource-admission gaps are
separate follow-up work.

## Regression evidence

Retained all 23 original RS-02 cases, including four strict previously failing
cases and 19 positive independent crypto/component/lifetime proofs. Added four
meaningful cases: key/salt audit-only history cannot regenerate missing material;
malformed primary plus wrong pending rejects with DB/candidate bytes preserved;
unsafe symlink primary propagates despite a cryptographically valid pending key.

Coordinator review identified that the existing shared transaction helper checked
generation before BEGIN IMMEDIATE. The guard now executes inside its try block
after acquiring the SQLite write transaction, or within a joined transaction,
so rejected policy follows the helper's rollback path and authentication and
encryption share SQLite write exclusion. Two deterministic interleaving cases
attempt raw SQLite mutation with timeout zero immediately after real policy
verification, without using the cooperative file lock. Both owned and joined
transactions must reject that raw writer as locked and preserve policy/value.

Initial Python 3.11 secure suite after the production repair (before the four
additional evidence cases): **154 passed in 62.50s**. Final expanded secure suite
on both maintained interpreters includes policy/migration, rejected-auth ordering,
ordinary recovery, real-process crash, lock/contention/stale-refresh, rotation and
crypto suites. Before the final transaction-order correction, both versions
passed 158 cases (3.11: 59.99s; 3.12: 65.00s). Final counts for the correction
and two raw-writer cases are **160 passed on Python 3.11.14 in 60.09s** and
**160 passed on Python 3.12.13 in 60.68s**. Exact command for each maintained
environment: `timeout 180 <env>/bin/python -m pytest tests/test_secure -q
-p no:cacheprovider`, using `/tmp/gunz-utils-audit-20261008` and its `-py312`
counterpart. Both exited zero; no strict regression was weakened or skipped.

Pinned Ruff 0.14.10 check of both owned executable files: passed. Pinned mypy
1.19.1 `--follow-imports=silent --cache-dir tmp/rp01/mypy` of both files: passed,
no issues in two source files. No native activation claim is needed for these
pure-Python secure suites. No installs, real store/key operations, commits,
external reports or CI/remote jobs occurred. All destructive fixture steps are
bounded synthetic pytest tmp stores.

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
