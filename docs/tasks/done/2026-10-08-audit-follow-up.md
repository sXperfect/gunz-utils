# Audit follow-up: parallel review and evidence reconciliation

**Date:** 2026-10-08
**Status:** Done — six reviews and eleven scoped repair tasks verified
**Owner:** Coordinator
**Baseline:** `main@80bde76a641ce4577574fde60ec957251aee2ba0` plus existing working-tree changes
**Predecessor:** [Repository-wide algorithm audit](../active/2026-09-28-algorithm-correctness-audit.md)

## Goal

Produce a current, evidence-backed audit backlog and review the highest-risk
boundaries in parallel. Historical A4 evidence does not certify this working
tree. Distinguish reproducible defects, missing proof, stale documentation, and
deliberate contract limitations.

## Task hierarchy and dependencies

| ID | Child task | Priority | Execution |
|---|---|---|---|
| AU-01 | [Filesystem publication](2026-10-08-audit-filesystem-publication.md) | P1 | First parallel wave |
| AU-02 | [SecureStore and crypto](2026-10-08-audit-secure-store-crypto.md) | P1 | First parallel wave |
| AU-03 | [Concurrency and cancellation](2026-10-08-audit-concurrency-cancellation.md) | P1 | First parallel wave |
| AU-04 | [Native acceleration](2026-10-08-audit-native-acceleration.md) | P2 | Second parallel wave |
| AU-05 | [Graph depth and input bounds](2026-10-08-audit-graph-input-bounds.md) | P2 | Second parallel wave |
| AU-06 | [Packaging, ownership, and evidence](2026-10-08-audit-packaging-evidence.md) | P2 | Baseline review now; final reconciliation after AU-04/05 |

Three worker agents can run alongside the coordinator. AU-01 through AU-05
are independent source reviews; AU-06 depends on their results. Initial
delegation covered AU-01 through AU-03. Their initial reviews are complete;
AU-04 through AU-06 are now delegated. Repairs remain separate follow-up work.

## Shared execution contract

### Repair phase authorization

Initial AU-01 through AU-06 reviews are complete. Following the user's
instruction to proceed, source repairs are authorized on
`audit/follow-up-20261008`, preserving all pre-existing edits. A worker may now
edit only its assigned repair sources, dedicated tests, task record and uniquely
named changelog fragment. Coordinator owns shared indexes, registry, and final
integration checks. Do not commit or publish. Review-phase restrictions below
describe the completed initial review, not the newly assigned repair phase.

- Read repository `AGENTS.md`, the security audit methodology, and the algorithm
  correctness guide before reviewing. Existing task records are historical evidence.
- Review the current working tree without switching branches, resetting edits,
  committing, publishing, or altering release metadata.
- Initial worker scope is review, temporary local probes, and updates to the
  assigned child task file only. Do not edit source, tests, sibling task files,
  the registry, or shared indexes during this wave.
- Put temporary probes under ignored `tmp/` in a uniquely named directory.
  Use installed tooling; report missing tools rather than installing packages.
- Use synthetic inputs. Keep vulnerability details local; follow `SECURITY.md`
  before any external disclosure.
- Every finding records source location, contract, trigger, observed outcome,
  severity rationale, existing test coverage, proposed repair, and verification.
- Separate executed evidence from inspection. Record interpreter, command,
  outcome, skips, baseline revision, and relevant dirty files. Do not promote
  A3/A4 without successful required execution on the corresponding revision.
- Propose implementation follow-ups with explicit file ownership and regression
  checks. Coordinator reconciles overlaps before assigning repair work.

## Coordinator work

### Confirmed first-wave repair backlog

The three initial reviews found ten reproducible defects. No source repair has
been performed. Conditional filesystem and database-tampering findings retain
their stated attacker access assumptions; probe failure injection is not a claim
that all real-world storage failures produce the same result.

| Repair | Owned boundary | Findings | State |
|---|---|---|---|
| [AR-01](2026-10-08-repair-cas-publication-materialization.md) | CAS | AU01-F1/F2/F5 | Done |
| [AR-02](2026-10-08-repair-directory-no-replace.md) | Transactional directories | AU01-F3 | Done |
| [AR-03](2026-10-08-repair-atomic-write-descriptor-cleanup.md) | Atomic write | AU01-F4 | Done |
| [AR-04](2026-10-08-repair-secure-store-policy-recovery.md) | SecureStore | AU-02-F1/F2 | Done |
| [AR-05](2026-10-08-repair-pipeline-lifecycle.md) | Worker pipeline | AU-03-F1/F2 | Done |
| [AR-06](2026-10-08-repair-lease-coroutine-cleanup.md) | Lease heartbeat | AU-03-F3 | Done |
| [AR-07](2026-10-08-repair-network-idna-authority.md) | URI authority after IDNA | AU-05 normalization finding | Done |
| [AR-08](2026-10-08-repair-subprocess-drain-deadline.md) | Synchronous capture deadline | AU-05 pipe-drain finding | Done |
| [AR-09](2026-10-08-repair-sync-timeout-before-marker.md) | Sync validation atomicity | AU-05 marker finding | Done |
| [AR-10](2026-10-08-repair-native-safety-parity.md) | Native stack safety and subclass parity | AU04-F1/F2 | Done |
| [AR-11](2026-10-08-repair-verification-matrix.md) | Native activation and sdist roundtrip | AU-04/AU-06 verification gaps | Done |

Focused existing suites: AU-01 135 tests + 4 subtests; AU-02 64 tests;
AU-03 192 tests + 67 subtests. Counts overlap and must not be summed as unique
coverage. These ran on pytest 9.0.2; cryptography was 49.0.0, below current
maintained pins/floors. AU-06 must retain this limitation. No full gate ran.

1. Create and index this hierarchy; delegate the first three reviews.
2. Locate an existing usable test environment and share its interpreter path.
3. Collect worker evidence, review reproductions, and consolidate priorities.
4. Preserve pending tasks and implementation proposals; auditing a boundary does
   not mean a discovered defect is repaired.
5. AU-06 reconciles registry/task status only after current evidence is known.
   Run `./scripts/verify.sh` before claiming full verification of a repaired tree.

## Acceptance

- [x] Each delegated review has a source/test inventory and explicit findings.
- [x] Findings identify confirmed failures separately from proof gaps.
- [x] Implementation follow-ups include ownership and meaningful regression checks.
- [x] Remaining tasks and environment limitations are visible in the index.
- [x] Full-audit completion is supported by current-revision canonical verification.

## Results

Task hierarchy drafted and indexed. First-wave agents `audit_filesystem`,
`audit_secure_store`, and `audit_concurrency` completed AU-01 through AU-03.
The same workers now own AU-04 (native), AU-06 (verification), and AU-05
(graphs/input boundaries), respectively. Each has exclusive ownership of its
current child task record. AU-01 through AU-06 initial review is complete.
AR-01 through AR-11 source/test/documentation repairs are implemented; the
canonical combined verification passed. User edits in enums.py, models.py,
version/changelog and consumed fragments remain intact. No commit or publication
has been performed.

The existing interpreter
`/home/adhisant/tmp/miniforge3/envs/gunz-utils/bin/python` has Python 3.11.14,
pytest, mypy, and cryptography available. Ruff is absent. The default Codex
interpreter lacks pytest; use the existing environment for focused proof work.
The isolated final environments use Python 3.11.14 and Python 3.12.13 with
pytest 9.0.3, Ruff 0.14.10 and mypy 1.19.1. Declared optional floors are met,
including cryptography 50.0.2 and GitPython 3.2.0. Initial older-environment
results remain historical evidence. Source repairs now have pinned focused
checks, native activation and real wheel/sdist roundtrip evidence. Full aggregate
verification remains pending; historical A4 levels have not been promoted.

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
