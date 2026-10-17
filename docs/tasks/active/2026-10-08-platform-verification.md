# Native Windows and macOS verification

**Date:** 2026-10-08
**Status:** Preparation implemented and locally checked; real native hosts pending
**Base:** `a3f224ba5b14fe98b4f41833c9a73f297754a3af`
**Branch:** `audit/native-platforms-20261008`
**Predecessor:** [Storage proofs](../done/2026-10-08-storage-process-proofs.md)

## Goal and task hierarchy

Verify actual filesystem publication, SecureStore locking/key cleanup, bounded
subprocess timeout/cancellation, and optional C acceleration on real Windows and
macOS for Python 3.11/3.12. Prepare concrete runnable checks before asking for
runner access; Linux shims and inspection are useful preparation but never native
kernel evidence.

| Task | Owner scope | Native execution |
|---|---|---|
| [NP-01 Windows](2026-10-08-platform-windows.md) | Windows contracts, native compiler/link configuration, targeted tests | Pending real Windows host |
| [NP-02 macOS](2026-10-08-platform-macos.md) | Darwin exclusive rename, filesystem/process/lock contracts, targeted tests | Pending real macOS host |
| [NP-03 portable verifier](2026-10-08-platform-verifier.md) | Host identity guard, selected test collection, bounded runs and structured evidence | Linux validation now; native run later |
| [NP-04 async pipe deadline](2026-10-08-platform-async-drain.md) | Separate bounded reproduction of the inspected async drain concern | Queued; no reproduced native defect |

## Current environment and runner discovery

Current host reports Linux. No gh executable or native execution connector is
available. SSH exists; existing SSH alias labels yielded no obvious Windows/macOS
candidate. No arbitrary machine was contacted. Current hosted CI declares one
Ubuntu job. The coordinator asked for existing native host aliases/runner names;
credentials must not be pasted into chat. No native host has been confirmed.

## Execution and ownership contract

- Preserve user changelog/version/consumed-fragment and enum/model export edits.
  No reset/stash, release, merge/push, messages to third parties, or production data.
- Preserve current single-job, main/PR-to-main hosted CI routing and minimal
  permissions. This phase builds local-first checks; no new workflow or paid
  hosted jobs are launched. Real runner access/routing is a separate concrete step.
- Read AGENTS.md and canonical security/algorithm/runner policy. Native-platform
  source claims require upstream primary documentation where uncertain.
- Each worker owns its child record, dedicated new tests, uniquely named fragment
  and explicitly assigned executable source. Coordinator owns shared indexes and
  registry. No overlapping source edits without coordination.
- Temporary native builds and artifacts stay under ignored tmp; no compiler is
  made a runtime dependency. Synthetic stores/files/children only; all waits
  bounded and resources cleaned/reaped. Never target real key directories.
- Verifier must refuse a requested platform that differs from actual host and
  report version/kernel/architecture/source origin, source revision or fingerprint,
  tool versions, command return codes and exact pass/skip/failure evidence.
  Missing tools/OS capability are visible; no skipped coverage silently certifies
  a guarantee. No A3/A4 native claim until checks execute successfully there.
- Windows ACL/reparse-point/private-key and descendant-process boundaries must
  be stated explicitly; POSIX modes/process groups cannot be assumed.
- Existing tests with POSIX-only assumptions need targeted portable counterparts
  or precisely justified native skips, rather than blanket test suppression.
- Use pinned local Python envs under /tmp/gunz-utils-audit-20261008 and -py312.
  Pinned Ruff/mypy live in the first environment. Do not mutate shared envs.

## Acceptance

- [x] Runnable portable verifier validates actual host, source and interpreters.
- [x] Targeted ordinary/native/fallback suites and platform capability expectations
      defined for filesystem, key cleanup/locks, subprocess and native build.
- [x] Preparation tests and applicable Linux/static gates pass.
- [ ] Actual Windows Python3.11/3.12 evidence captured and reviewed.
- [x] Actual macOS Python3.11/3.12 evidence captured and reviewed.
- [ ] Confirmed defects repaired with meaningful regressions and applicable gates.
- [x] Registry/index distinguish executed Linux/shim evidence from pending native
      proofs and accepted platform limitations.

## Evidence and pending decisions

Actual macOS verification executed successfully on Darwin 25.6.0 arm64 across Python 3.11.16 and 3.12.15:
`scripts/verify_platform.py --platform macos --python /Users/sxperfect/miniforge3/envs/gunz-bench/bin/python --python /Users/sxperfect/miniforge3/envs/gunz-style/bin/python --output tmp/macos-platform-evidence.json`
produced `status=passed`, `complete=true`, `native_platform_complete=true`, `python_matrix_complete=true`, and `source_unchanged=true`.
Each interpreter executed:
- filesystem: 18 passed, 0 failures, 0 skips
- secure-store: 79 passed, 0 failures, 0 skips
- subprocess: 34 passed, 0 failures, 0 skips
- native-platform: 3 passed, 0 failures, 0 skips
- fallback: 103 passed, 0 failures, 31 expected exclusions
- compiled-native: 134 passed, 0 failures, 0 skips
All JUnit skip/failure and activation logs are recorded in `tmp/macos-platform-evidence.json`. Windows native host execution remains pending.

Three parallel workers produced Windows compiler preparation/regressions, Darwin
adapter/capability probes, and `scripts/verify_platform.py`. The Windows builder
now selects the base CPython import library and matching dynamic CRT and isolates
compiler intermediates. Native compilation on Windows still requires a real host.

Combined new tests pass on both Python 3.11.14 and 3.12.13: **30 passed, 7 actual
Windows/Darwin skips** per interpreter. The canonical aggregate run passed release,
Python tests, strict docs, packaging isolation and compatibility. Main Python 3.11
collection preceded the final two new test files: **1,311 passed, 24 skipped**;
the final Python 3.12 collection passed **1,332, with 29 skips**. Compiled native
proofs passed **57 tests** on each Linux interpreter; forced fallback passed 35
with 22 explicitly native-only skips. The initial aggregate lint ran against an
unfinished harness and failed; final `scripts/ci.py lint` passed Ruff and mypy
(97 package source files). Final release/docs reruns also passed. Initial JSON
`tmp/platform-ci-summary.json` retains the original lint failure; it is not
rewritten to claim an all-green initial aggregate run.

Native hosts remain required for actual Windows/macOS acceptance. Run on each
real OS with both interpreter paths supplied:

```text
python scripts/verify_platform.py --platform windows --python <python311> --python <python312> --output tmp/windows-platform-evidence.json
python scripts/verify_platform.py --platform macos --python <python311> --python <python312> --output tmp/macos-platform-evidence.json
```

Each command refuses a mismatched actual OS, requires both versions for native
completion, records source fingerprints and import origins, and preserves JUnit
skip/failure evidence. Platform-specific skipped contracts remain visible coverage
gaps. CLI success on `--platform linux-preparation` is preparation only and never
native-platform completion. See NP-03 for the executed end-to-end preparation
report and NP-01/02 for native prerequisites and narrower platform limitations.

The stable-source end-to-end run produced `tmp/np03/linux-platform-evidence.json`:
`status=prepared`, `complete=true`, `source_unchanged=true`, both Python versions
present, and `native_platform_complete=false`. Each interpreter passed 18
filesystem, 46 SecureStore, 20 subprocess, 35 fallback and 57 compiled-native
cases. The 22 fallback-only native skips per interpreter are explicitly recorded
expected exclusions; there were no unexplained skips. An earlier run correctly
rejected source mutation while a worker finalized a test and is retained as
`tmp/np03/linux-platform-evidence-initial-incomplete.json`.

NP-04 records the newly inspected async drain concern for separate reproduction;
that initial inspection status is superseded by the integrated repair below.
Existing user edits are preserved; no release, commit, push, merge, hosted job,
remote host contact, or production-store operation was performed.

## Integrated parallel follow-up

The second parallel review reproduced and repaired the async exit/drain deadline
and cleanup issue (NP-04), corrected Windows debug-interpreter preparation fixtures
(NP-01), and repaired verifier evidence acceptance (NP-03). The verifier now
rejects malformed JUnit/identity data, hidden xfails and zero-pass proof packets,
uses exact activation receipts and removes inherited pytest plugin hooks. Its
subprocess phase includes the new async regressions.

All six canonical gates passed on the final integrated executable source;
`tmp/platform-integrated-ci-summary.json` records `passed=true` and six zero
return codes. Both Python 3.11.14 and 3.12.13 full suites passed **1,370 tests,
29 skips**, with **57 compiled-native passes** each. Strict docs and isolated
wheel/sdist/optional-dependency packaging passed. This final all-green run
supersedes the earlier draft lint failure without rewriting its historical JSON.

Fresh stable-source report `tmp/np03/integrated-linux-platform-evidence.json`
records `prepared`, complete/unchanged-source true, both versions present and
native-platform completion false. Each runtime passed 18 filesystem, 46 store,
34 subprocess, 35 fallback and 57 native cases; 22 exact native-only fallback
exclusions are recorded, with no other gaps. See NP-03 for fingerprint/provenance.
Actual Windows/macOS execution still requires native hosts; Linux preparation
does not satisfy those acceptance boxes.
