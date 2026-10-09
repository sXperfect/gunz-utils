# Resource lifetime and security audit from the maintained registry

**Date:** 2026-10-08
**Status:** Complete for stated Linux audit/repair scope; follow-ups recorded
**Starting point:** Current working tree, including verified platform/async repairs
**Sources:** [Registry](../../audits/algorithm-registry.md),
[methodology](../../design/audit/security-audit-methodology.md), AGENTS.md, SECURITY.md

## Goal and hierarchy

Investigate memory/resource leaks and security issues using documented proof gaps
as leads. Historical audit levels are evidence for their original revisions, not
proof of the current tree. Findings must distinguish confirmed defects, inspected
concerns, intentional caller-owned budgets and unavailable platform evidence.

| Task | Scope | Owner |
|---|---|---|
| [RS-01 lifetime](2026-10-08-resource-lifetime.md) | Tasks, readers, descriptors, callbacks, caches and retained payloads | Concurrency agent |
| [RS-02 secure storage](2026-10-08-secure-input-budgets.md) | GAP-008, key/salt reads, decode budgets, tampering and diagnostics | Secure-store agent |
| [RS-03 parsing/native](2026-10-08-parser-native-safety.md) | Serialization/binary input bounds and C allocation/refcount lifetimes | Filesystem agent |

## Execution contract

- Read maintained audit policy and existing proof packets before alleging missing
  coverage. Include source lines, contract, realistic input/trust assumptions,
  severity rationale, reproducible evidence and proposed focused remediation.
- Initially source is read-only. Each agent owns its child task record and uniquely
  named new audit regression file. Report confirmed defects before source changes;
  coordinator assigns implementation ownership and handles registry/index/gates.
- Use only synthetic tmp fixtures and finite resource budgets. Avoid unbounded
  allocation, indefinite children/waits, real secrets, real stores or host changes.
  No public issue/report, external message, commit/push, CI or remote job.
- Preserve existing user release/version/export edits and all earlier audit work.
  Existing archived task records stay intact. No speculative API redesign.
- Leak evidence should use weak references, GC/task/thread/fd ownership checks,
  bounded repeated workloads or tracemalloc with warmup; allocator RSS alone is
  not proof. Distinguish intended caches from unreachable-but-retained resources.
- Use pinned /tmp/gunz-utils-audit-20261008 and -py312 interpreters. Run meaningful
  focused cases on both versions; record native activation explicitly if relevant.
- Source-based fixes require regressions, a suitable fragment and canonical
  integration verification. Security findings remain local per SECURITY.md.
- This phase is targeted follow-up, not a claim of complete package-wide security
  certification, real Windows/macOS verification or completed advisory review.

## Acceptance

- [x] Three concrete source/evidence review packets completed.
- [x] Confirmed defects reproduced with bounded independent evidence.
- [x] Follow-up repairs assigned and verified where needed.
- [x] Registry gaps reconciled without unsupported level promotion.

## Audit handoff

RS-01 reproduced six cleanup regressions across three finding families; RS-02
reproduced four regressions across three authentication/recovery findings; RS-03
reproduced two compiled-backend depth-budget parity cases. Positive resource and
crypto proofs are recorded in the child packets; no universal leak-free or
package-wide security claim follows. The user authorized the
[parallel repair hierarchy](2026-10-08-resource-security-repairs.md), which owns
remediation and coordinator integration. Fixed-format read admission and actual
Windows/macOS execution remain distinct follow-ups.

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
