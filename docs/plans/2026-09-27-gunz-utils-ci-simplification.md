# gunz-utils CI simplification and coverage program

## Goal

Make gunz-utils CI substantially easier to maintain and cheaper in runner work while preserving comprehensive, truthful correctness, dependency-isolation, packaging, and documentation checks. A DS4F worker implements bounded units; a separate DS4F auditor designs, critiques, and independently verifies each unit before the coordinator releases the next.

## Authority, repositories, and environments

- User authorized this long-horizon CI improvement program and delegation to `hp:gz_u-ds4f-worker` and `hp:gz_u-ds4f-auditor`, both DS4F medium.
- Sole writable implementation worktree: `/tmp/gunz-utils-ci-2026-09-27`, branch `ci/simplify-github-free-2026-09-27`.
- Coordination root: `/tmp/gunz-utils-ci-orchestration-2026-09-27`.
- Original checkout `/home/sxperfect/projects/hyperion/libs/gunz-utils` and all Hyperion/crawler worktrees are outside this pair's edit scope. Do not cherry-pick, merge, reset, push, commit, or alter them.
- Baseline HEAD is `5c55b9a`; 17 existing dirty paths were copied into the isolated worktree and preserved under `baseline/gunz-utils`. They include earlier test/regression repairs. They are not changes produced by this CI project.
- The crawler pair may later change its own gunz-utils checkout. Do not edit that checkout, reinstall its editable import, or claim this CI branch already contains future fixes. Report eventual reconciliation as a separate integration gate.
- Use `mamba run -n hyperion` for all local Python, lint, and tests, following the user's environment instruction. Explicitly set `PYTHONPATH=/tmp/gunz-utils-ci-2026-09-27/src` where needed and verify `gunz_utils.__file__` points into this worktree before testing. Do not repoint the shared environment's editable install.
- Python 3.11 is canonical; retain existing Python 3.12 compatibility coverage unless concrete evidence supports a reviewed alternative. Package metadata declares >=3.11, so document the actual tested range without pretending it proves all future versions.
- No new dependencies or package-manager migrations without user authorization. Existing declared extras/tooling may be used. Missing local tooling is an explicit validation limitation, never a passing gate. Do not install into shared environments during autonomous work.
- Follow applicable AGENTS and role task templates. Split work into small units, generally at most three implementation files plus focused tests/docs, and snapshot before editing. No file deletion, destructive cleanup, live deployment, paid runners, billing/account changes, or secret access is authorized.

## Verified starting evidence

Recheck current line numbers before implementation. These findings were established by a read-only audit of the copied baseline:

| Finding | Baseline evidence | Consequence |
| --- | --- | --- |
| Push-only validation | `.github/workflows/ci.yml:3`, `deploy_docs.yml:3` | No ordinary PR checks before merge |
| Repeated work | Seven two-version matrices plus Ruff, core-import, mypy; `.github/workflows/ci.yml:8,41,62,82,102,122,142,162,179,200` | 17 CI jobs plus one documentation job on matching pushes |
| Missing bounded execution controls | Both workflows | No explicit concurrency cancellation, timeout, dependency cache, or scoped docs execution |
| Misleading local parity | `scripts/ci.py:122,135` | Six unittest groups plus Ruff omit full pytest, typing, import, and docs checks |
| Pytest tests omitted by unittest | `scripts/ci.py:100`, `tests/test_core/test_dag.py:5,10` | Local success does not prove all test functions ran |
| Existing lint/type failures | CI-equivalent local commands | 46 Ruff findings; 28 mypy errors in 13 files at audit time |
| Optional plot omitted from all | `pyproject.toml:26-32`, `ci.yml:57` | An all-extras label does not prove real plotting works |
| Source can shadow installed distribution | `pyproject.toml:79` | Full pytest is not an installed-wheel smoke test |
| Documentation warnings pass | `scripts/build_docs.sh:24`, `docs/source/conf.py:8,28` | Missing static directory, duplicate autodoc warnings, stale docs version |
| Docs workflow is build-only | `deploy_docs.yml:30` | Do not invent an authorized Pages deployment |
| Uncontrolled tool resolution | `ci.yml:22,56,174,213` | Repeated latest-tool installation introduces drift |

Existing audit logs: `/tmp/gunz-ci-lint-audit.log`, `/tmp/gunz-ci-mypy-audit.log`. Treat these as initial evidence, not final results. Prior repaired baseline full suite: 712 passed and 45 subtests; verify current collection rather than forcing that historical count.

Public GitHub API evidence saved in this directory:
- `github-repository.json`: public `sXperfect/gunz-utils`, default branch main.
- `github-runs.json`: recent run sample; latest captured CI run 36331164502 failed, docs run 36331164524 succeeded.
- `github-latest-ci-jobs.json`: 17 CI jobs, with test, lint, typing and core-import failures/cancellations. The pushed revision does not include all local uncommitted repairs; do not attribute every remote failure to today's local tree.
- Branch protection query returned HTTP 401; GitHub CLI is unauthenticated. Required check names, repository settings and account usage cannot be assumed known.

## GitHub Free and resource constraints

Verified 2026-09-27 against official documentation:

- Standard GitHub-hosted runners are free for public repositories. GitHub Free's 2,000 monthly minutes concern private-repository allowances; do not apply that cap to this public repository or promise invented monetary savings.
- GitHub Free includes 500 MB artifact storage, shared with Packages; cache allowance is 10 GB per repository. Keep artifact retention short and cache keys bounded. Larger runners are charged and are outside this task.
- Favor standard Ubuntu runners. Do not add broad OS/Python matrices, scheduled runs, external SaaS, or self-hosted infrastructure without a demonstrated coverage need.
- Show measured runner work, queue time, job count, setup duplication and storage as separate metrics. Estimates must identify assumptions. Account-wide costs require account data, which is unavailable.

Sources:
- https://docs.github.com/en/billing/concepts/product-billing/github-actions
- https://docs.github.com/en/actions/concepts/workflows-and-actions/concurrency
- https://docs.github.com/en/actions/reference/workflows-and-actions/workflow-syntax

Required workflows skipped by whole-workflow path/branch filters can leave required checks pending. Prefer an always-reporting PR gate with appropriately conditional jobs/steps; preserve clear failure propagation. Verify actual trigger semantics against official documentation, including forks, draft/ready PRs, cancellation, and manual runs. Never use privileged pull_request_target to execute untrusted PR code.

## Target architecture to critique in C01

Aim for approximately three to five useful jobs on a typical code PR, instead of 18 jobs on each matching branch push. This is a design target, not permission to delete distinct coverage.

1. Canonical Python 3.11 validation: full pytest collection, Ruff, typing, and package-build checks with shared setup where maintainability improves.
2. Dependency-isolation and distribution checks: prove zero-dependency root/fallback behavior, each meaningful optional-extra boundary, and outside-source installed-artifact behavior in genuinely isolated contexts. Combining jobs must not let previously installed extras leak into later cases.
3. Python 3.12 compatibility: preserve the current distinct compatibility guarantee while eliminating repeated category execution that full pytest already covers.
4. Strict documentation validation: cover documentation and relevant API/configuration changes, without redundant unconditional builds or new publication.
5. Only add a stable aggregate result if required by conditional jobs/branch-protection migration; it must fail on failed/cancelled required work and not mistake skipped prerequisites for success.

Prefer native Actions features and a small transparent local command dispatcher. Do not replace two YAML files with a bespoke CI framework, large shell DSL, dynamic generated workflow graph, or dozens of maintenance fixtures. The auditor should justify every extra abstraction against fewer workflow concepts and clearer local reproduction.

## Milestones and review gates

### C01 — Evidence, coverage contract, and concrete design (first assignment; no implementation)

Inventory triggers, jobs, versions, install commands, dependency assumptions, test discovery, public API/import guarantees, docs behavior, artifact/cache behavior, and check names. Probe saved API schemas before processing. Build a coverage mapping showing which old checks each proposed check preserves. Record local baseline failures separately from already repaired remote failures. Draft the target job graph, supported versions, canonical commands, tool/dependency strategy, resource targets, fork permissions, and rollback/check-name migration procedure. Auditor independently checks the coverage matrix and accepts a concrete spec digest before C02.

### C02 — Truthful local command parity

Make local CI commands match the intended hosted gates. Full pytest must collect pytest functions and unittest tests; expose separate gates and useful exit statuses. Ordinary checking must not implicitly upgrade or reinstall the environment. Include benchmarks in the intended Ruff scope. Ensure package-import origin is deliberate. Keep this step separate from job consolidation; use narrow subprocess failure/argument tests where they prove behavior.

### C03a/C03b/C03c — Restore honest lint, typing, and docs gates

Split the actual failing gates into small fixes. Preserve prior repairs and public APIs. No blanket ignores, weakening assertions, disabling test collection, continue-on-error, hidden skip expansion, or narrowing lint/type scope merely to get green. If fixing existing typing findings requires broader domain changes, identify the specific block and propose a bounded corrective unit. Repair actionable documentation warnings and stale version configuration before enabling a strict build; account for warnings from optional imports and supported tools explicitly.

### C04 — Consolidate canonical CI execution

Implement the accepted simple job graph and consolidate repeated installation/setup/test execution. Preserve full collection on canonical Python and compatibility coverage. Use existing tooling, a reviewed reproducibility strategy, stable and understandable check names, and job-local minimal permissions. Every removed job needs a coverage-matrix replacement with evidence. A source-editable environment does not prove built distribution correctness.

### C05 — Dependency and packaging contracts

Prove root import without optional packages, stdlib fallbacks, declared single extras, secure/validation/project/observability behavior, and real headless plotting with the already-declared plot extra. Ensure absent dependencies produce intended errors rather than accidental imports. Validate wheel and sdist contents and outside-checkout installed imports, including a check that would catch accidental source shadowing. Use clean isolated contexts; a success after cumulatively installing all extras is not evidence of isolation. Preserve optionality instead of adding runtime dependencies to satisfy CI.

### C06 — PR triggers, cancellation, limits, caching and diagnostics

Add PR validation only for pull requests targeting `main` and post-merge validation only for pushes to `main`. Feature-branch pushes, `develop`, and manual dispatch stay disabled to avoid duplicate hosted work. Set explicit read-only permissions, per-workflow/ref concurrency groups, cancel superseded CI, bounded job timeouts, and dependency caches keyed by relevant metadata/interpreter. Keep needed diagnostics in logs/summaries; use small short-lived failure artifacts only when useful. Avoid caching secrets, virtual environments with unsafe restore semantics, or unbounded key churn. Verify always-reporting required gate semantics and fork safety.

### C07 — Documentation workflow and maintenance consolidation

Choose one clear place for docs validation and truthful local parity, without double-building docs. Include API/config changes in its change-detection contract. Document existing build-only behavior; do not deploy Pages. Explain every CI job, supported versions, local command, isolation guarantee, tool refresh process, artifact retention, and troubleshooting path. Identify obsolete files but do not delete without the required checkpoint/authorization process.

### C08 — Adversarial acceptance and rollout packet

Independently validate full tests, lint, typing, strict docs, packaged imports and isolation to the extent supported locally. Validate YAML syntax and Actions expressions with existing available tools, keeping missing tooling explicit. Check meaningful scenarios: code PR to `main`, docs-only PR to `main`, PR to another base (no CI), feature-branch push (no CI), main push, API change, CI metadata change, fork PR without secrets, repeated pushes/cancellation, failing test, failing lint, failed docs, cache miss/hit, and package import from outside checkout. Use a compact scenario table and focused tests rather than mirroring YAML in brittle assertions.

Provide before/after workflow/job/command counts, measured local timings and available hosted baseline durations, estimated setup savings, storage bounds, unresolved settings, and a reversible rollout procedure preserving required check coverage. Real post-change GitHub results require a separately authorized publish/run step; do not label unrun hosted checks successful. Finish with a precise reviewable patch and honest pending hosted validation, not a false production-complete claim.

## Each worker handoff

Worker reads its bounded assignment, captures/uses the coordinator checkpoint, implements only that unit, runs relevant checks with bounded subprocesses, and writes a report under this coordination root. Report READY_FOR_REVIEW or BLOCKED, exact changed paths, current file:line evidence, commands/exit codes/counts/log paths, baseline preservation, and remaining limitations. STOP after the report. Do not prompt the other session directly or edit coordinator/credential files.

Auditor inspects actual diffs and test behavior, independently reruns the necessary gates, records accepted/revise/blocked/complete plus evidence, and designs the next bounded assignment. At most two correction rounds per unit; unresolved repeated failure pauses for a concrete decision. No broad process kills: terminate only owned bounded children by exact identity.

## Definition of done

- Reviewed design and coverage-equivalence mapping explain a simpler workflow graph.
- PR validation is useful, truthful, bounded, and safe for forks.
- Full canonical test collection and supported compatibility, dependency-isolation, built-artifact and docs guarantees are preserved or improved with evidence.
- Existing lint/type/doc failures are fixed or concretely reported as blockers; no gate is silently weakened.
- Local and hosted commands agree; optional dependencies remain optional.
- Original checkout, crawler pair, and shared environment are unchanged by this CI pair.
- Resource claims distinguish public free minutes, storage, measured runtime, and unmeasured estimates.
- Final patch, review reports, before/after metrics, and required-check rollout steps are ready for review. Commits, pushes, repository settings, paid usage and hosted validation remain explicitly separate.
