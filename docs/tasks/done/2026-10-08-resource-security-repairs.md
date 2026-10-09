# Parallel resource/security repairs

**Date:** 2026-10-08
**Status:** Complete for stated Linux audit/repair scope; follow-ups recorded
**Parent:** [Audit findings](2026-10-08-resource-security-audit.md)
**Branch:** audit/native-platforms-20261008 (preserve current verified work)

## Repair hierarchy and exclusive ownership

| Task | Owner | Source scope |
|---|---|---|
| [RP-01 SecureStore](2026-10-08-repair-secure-store.md) | Secure-store agent | ext/secure_store.py, RS-02 dedicated tests |
| [RP-02 cleanup](2026-10-08-repair-resource-cleanup.md) | Concurrency agent | concurrency.py, cache.py, RS-01 dedicated tests |
| [RP-03 parity](2026-10-08-repair-native-depth.md) | Filesystem agent | serialization.py, RS-03 dedicated tests |

## Shared contract

- Read AGENTS.md, SECURITY.md, maintained audit methodology, audit findings and
  existing regressions. Fix reproduced defects with narrowly scoped typed changes.
- Keep all existing failing regressions strict and retain passing resource proofs.
  No test suppression, unrelated refactor, API expansion or dependency changes.
- Fixed key/salt read budgets are a separate compatibility follow-up. Do not add
  arbitrary caps or change the key whitespace contract in this repair phase.
- Use finite synthetic tmp stores/children/resources, pinned Python 3.11/3.12,
  actual native/fallback activation where relevant. No real secrets/store actions,
  public vulnerability reports, external messages, CI/remote jobs or commits.
- Preserve user release/version/export edits and all prior platform work. No
  archived-task edits or overlapping production source changes.
- Each worker owns its repair record, assigned dedicated tests, source files and
  uniquely named fragment. Shared indexes/registry and integration gates belong
  to the coordinator. Send diagnosis before substantial edits and final evidence.
- Coordinator independently reviews authentication/recovery ordering, runs the
  full canonical aggregate gate and native/fallback checks, and reconciles audit
  evidence without unsupported platform or audit-level claims.

## Acceptance

- [x] All three focused repair packets pass supported-interpreter checks.
- [x] SecureStore repair independently reviewed, including rejected-auth mutation.
- [x] Full canonical integration and actual native/fallback verification pass.
- [x] Registry and task evidence reconciled on the final executable tree.

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
