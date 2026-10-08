# AU-06: Packaging, subsystem ownership, and audit evidence

**Date:** 2026-10-08
**Role:** Audit researcher
**Status:** Done — initial review; scoped repair results recorded below
**Priority:** P2
**Parent:** [Audit follow-up](2026-10-08-audit-follow-up.md)
**Baseline:** `80bde76a641ce4577574fde60ec957251aee2ba0` plus existing dirty tree

## Question and scope

Do the current implementations uphold their documented security, correctness,
boundedness, and failure contracts? Scope: pyproject.toml, scripts/ci.py, scripts/audit_ci.py, scripts/verify.sh, .github/workflows/ci.yml, docs/audits/algorithm-registry.md, docs/TASKS.md, migration handoff docs and task records.

## Review obligations

Zero-dependency core imports, optional integration isolation, py.typed and native artifact contents, Python/platform compatibility, current-revision A2/A4 evidence, stale crypto/SecureStore gaps, and benchmark ownership after the gunz-bench handoff. This task consumes AU-01 through AU-05; do not blanket-promote old evidence or treat migration prose as proof code moved.

## Method and verification

Use canonical release/lint/test/docs/packaging gates where installed tooling permits. Report unavailable interpreters/dependencies and native skips. Any live dependency advisory review must use current authoritative upstream sources; otherwise mark it unperformed. Preserve historical records and reconcile active/pending status explicitly.

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

## Contract and inventory

Reviewed pyproject.toml, .github/workflows/ci.yml, scripts/ci.py,
scripts/audit_ci.py, scripts/verify.sh, scripts/build_native.py,
scripts/build_docs.sh, .gitignore, the package API policy, algorithm registry,
current task index, benchmark migration handoff, root lazy exports, selected
repository policy/native tests, and first-wave AU-01/02/03 reports. Inspected
`../bench/pyproject.toml` and confirmed downstream native/design paths locally.
AU-04/05 summaries supplied by coordinator are recorded below; their final task
packets were not yet written at final capture, so final evidence cross-check
remains a coordinator dependency.

Contracts: Python >=3.11, empty mandatory runtime dependencies, optional extras,
hatchling builds, installed py.typed, source-origin checking, reference Python
fallbacks, and Python 3.11/3.12 verification. Namespace-first public API policy
allows historical optional lazy root exports. Packaging isolation must exercise
installed artifacts outside the checkout with optional dependencies separated.
Historical A4 applies only to the recorded audited revision and successful gate;
new probes do not certify a dirty current tree.

## Findings

### AU-06-F1: sdist installation is not verified by the packaging gate

**P2, confirmed verification defect; no broken sdist installation demonstrated.**
`scripts/ci.py:299-354` builds wheel and sdist and checks that both exist, but
installs only the wheel. It never installs the sdist or rebuilds a wheel from an
extracted sdist. The success text says wheel/sdist OK even though installed
artifact/py.typed assertions only apply to the wheel. Repository AGENTS.md
expects wheel and sdist installation verification.

Repair: add a separate fresh-environment sdist installation/build-roundtrip
case with outside-checkout import-origin and PEP 561 assertions; inspect archive
contents as well. Keep build/install isolation and no source shadowing.

### AU-06-F2: native artifacts have no canonical build/active-test guarantee

**P2, confirmed verification/configuration gap; coordinate AU-04.**
Hosted CI and aggregate gates do not invoke scripts/build_native.py. Native
roundtrip/differential tests in test_binary_accel.py skip when `_accel` is absent.
This checkout contains no compiled `_accel` artifact. A green suite can therefore
exercise only Python fallback. pyproject.toml includes only src/ for sdist;
native/src/_accel.c, native/include/gunz_utils_native.h and the standalone build
script are outside that inclusion. AU-04 independently confirms this layout.

Repair: specify whether acceleration is checkout-only or supported from an
sdist. If supported, include native source/header/build support and verify it
from the sdist. Require a native-active lane as well as a forced-fallback lane,
with ABI/platform tagging and source-tree artifact exclusion tested explicitly.
This review did not build or inspect real wheel/sdist archives: hatchling/build
are missing and installs were outside the assigned scope.

### AU-06-F3: benchmark handoff paths are stale; compatibility code remains owned here

**P3, confirmed documentation/path mismatch; compatibility retention is intentional.**
`docs/design/gunz-bench-migration-handoff.md` repeatedly points to
`../gunz-bench`; that path does not exist. The actual sibling is `../bench`,
whose local project metadata declares gunz-bench 0.4.0 with gunz-utils>=1.14.0.
Its native/src/_native_ext.c and docs/design/gunz-utils-subsystem-transfer.md
exist. The handoff's 0.2.0 statement is historical integration context, not the
current downstream version.

Thirty benchmark modules and plot extra remain in gunz-utils; benchmark import
emits a deprecation warning and removal is scheduled for 2.0.0. This is documented
compatibility retention, not proof that all old implementation vanished.
Run-directory publication/process-sampling gaps remain relevant to this live
compatibility code until removal. Domain performance tooling belongs downstream;
domain-neutral data plumbing C extension remains owned by gunz-utils.
Repair path references and establish downstream/upstream security-fix ownership
until the major-version removal; do not remove APIs or plot extra during audit.

### Environment/evidence limitation: successful focused tests are not CI-equivalent

The existing interpreter's packages differ from maintained pins/floors:

| Tool/package | Installed | Maintained requirement |
|---|---|---|
| Python | 3.11.14 | >=3.11; also Python 3.12 gate |
| pytest | 9.0.2 | CI/test isolation pin 9.0.3 |
| mypy | 2.3.1 | CI pin 1.19.1 |
| cryptography | 49.0.0 | secure/all >=50.0.1 |
| GitPython | 3.1.57 | project/all >=3.1.62 |
| pydantic | 2.12.5 | >=2.4.0 |
| loguru | 0.7.3 | >=0.7.0 |
| sphinx | 9.0.4 | docs extra, no pinned version |
| Ruff, hatchling, build, matplotlib | missing | required respective gates |

Repository tests explicitly enforce newer pytest and optional-security floors.
No live upstream advisory review was performed; installed-version mismatch
cannot validate behavior under the declared dependency set and must not be
reported as proof of currently patched dependencies. Focused results still
provide useful implementation evidence within this older environment.

## Reconciliation dependencies

Preserve historical evidence at its original revision; annotate current findings
rather than erasing past results or blanket-promoting/downgrading every family.
Latest integrated A4 evidence in the registry is
416c1105404fa42f499f323fead8872644848103, whereas current HEAD is
80bde76a641ce4577574fde60ec957251aee2ba0 plus dirty changes.

| Registry/family | Current reconciliation needed |
|---|---|
| ALG-054 content store | AU-01 confirmed fanout redirection, staging-name substitution and lax digest syntax; qualify writable-parent/root threat model |
| ALG-055 atomic publication | AU-01 fd leak/empty-directory publication race remain unrepaired; GAP-005 has documented/tested post-replace fsync visibility now |
| ALG-050 SecureStore / GAP-008 | AU-02 marker downgrade and rotation rollback poison remain unrepaired; AES malformed salt/hex tests exist and pass |
| ALG-022 lease / ALG-056 schedulers | AU-03 leaked rejected heartbeat coroutine, pipeline setup orphans and child-cancellation deadlock contradict broad cleanup claims |
| ALG-076/077 native | AU-04 final packet pending; active-native gate and source-distribution obligations unproven |
| ALG-066 network / subprocess / sync | Coordinator reports AU-05 IDNA post-normalization delimiter injection, synchronous bounded-capture timeout drain gap and rsync invalid-timeout marker side effect; cross-check final repro packet before registry amendment |
| Graph traversal | Coordinator reports recursive-depth limitation remains documented; do not recast as a new defect without a stronger promised contract |
| ALG-068–074 benchmark | Still shipped deprecated APIs; handoff does not discharge upstream maintenance before removal |

The coordinator has already changed docs/TASKS.md from stale Idle to the new
hierarchy. The older algorithm-audit task remains active; final closure requires
explicit remaining obligations and actual current-revision execution evidence.
No shared registry/index was modified by this worker.

## Verification evidence

Baseline HEAD 80bde76a641ce4577574fde60ec957251aee2ba0; pre-existing metadata,
changelog, release-fragment deletions, enums.py/models.py and task/index edits
were preserved. Only this assigned task file and ignored tmp/au06 output/cache
were written. No installs, network/advisory lookup, native build, publication,
branch changes, source/test/config/index edits or release metadata mutations.
Sandbox startup failed previously; narrowly escalated local reads/checks worked.

Executed using /home/adhisant/tmp/miniforge3/envs/gunz-utils/bin/python:

- `scripts/release.py check`: passed; warning version 1.14.1 lacks matching tag,
  latest v1.14.0. This does not authorize making release tags.
- `timeout 90 ... -m mypy --cache-dir tmp/au06/mypy-cache src/gunz_utils`:
  timed out, exit 124, no completed diagnostics. No typecheck pass claimed.
- `timeout 120 ... -m pytest -q -p no:cacheprovider > tmp/au06/pytest.txt`:
  timed out after partial progress, no final pass/fail/skip summary. The trailing
  shell tail command returned 0; that is not pytest success. Runtime cause not
  established; a subsequent plugin-disabled focused subset ran promptly.
- `PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 timeout 30 ... -m pytest -q -p
  no:cacheprovider tests/test_core/test_repository_contracts.py
  tests/test_core/test_ci_policy.py tests/test_core/test_audit_ci.py
  tests/test_core/test_algorithm_audit_contracts.py`: **37 passed in 1.65s**.
  This proves those policy tests, not installed packaging behavior.
- `PYTHONPATH=src ... -S` imports root and every top-level non-private module:
  58 attempted; root and 55 others passed; models/project fail without their
  optional pydantic/GitPython backends. No forbidden optional package loaded.
  These are historical optional interfaces, not an observed root-import leak.
  Source-origin reported this checkout. This is source/no-site evidence, not an
  installed-wheel isolation matrix.
- `/home/adhisant/.local/bin/python3.12 --version`: Python 3.12.13 exists.
  Its `-m pytest --version` stalled and this worker terminated that own probe;
  no usable 3.12 pytest environment or compatibility result established.

Source py.typed exists. No wheel/sdist or compiled local native artifacts were
available. Ruff, strict docs, packaging installation, full aggregate, native
platform checks, and Python 3.12 suite were not completed. No A4 claim is made.

## Proposed follow-up tasks and ownership

1. **AU-06-R1, P2, scripts/ci.py and packaging tests:** add sdist install/rebuild
   proof and archive inventory; coordinate native inclusion/source changes with
   AU-04. Keep separate native-active and fallback assertions meaningful.
2. **AU-06-R2, P2, verification environment:** prepare maintained tool pins and
   optional floors under a separately authorized install workflow, then run
   release/Ruff/mypy/full pytest/strict docs/isolation/3.12 on the exact repaired
   tree. Investigate timeout cause before repeating unrestricted full checks.
3. **AU-06-R3, P2, registry and shared task index:** coordinator alone reconciles
   AU-01 through AU-05 after final packets/reproductions, links exact baselines,
   marks defects unrepaired, and updates proof levels only after matching gates.
   Source fixes remain with their assigned subsystem owners.
4. **AU-06-R4, P3, handoff/native architecture docs:** correct ../bench location,
   retain historical integration version as history, document retained benchmark
   compatibility/security ownership and intended acceleration distribution.
   Removal remains a separate 2.0 API migration, not part of this review.

Initial verification/ownership review is complete. Repairs, complete environment
gates, and final AU-04/AU-05 packet reconciliation remain outstanding.

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
