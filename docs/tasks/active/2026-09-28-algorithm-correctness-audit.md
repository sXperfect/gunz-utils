# Repository-wide algorithm correctness audit

Status: active — security-hardened main and algorithm-audit histories composed
and verified; integration branch is ready to merge before the next A2 sweep
Branch: `audit/algorithm-correctness`
Integration branch: `merge/algorithm-audit-main`
Integration base: `main@07244be5e6d24d83b3b7dcde62bc1702ff1f6e9d`
Audit parent: `36846e285bfec8624cb24a3b38bcfb7a6f62ad7a`
Started: 2026-09-28
Base: `main@cf3697d7457c5901ee1c927bc6dae347d5428722`

## Goal

Audit algorithmic implementations in `gunz-utils` for contract correctness,
numerical stability, parameter-domain validation, boundary/special cases,
deterministic behavior, complexity/boundedness, and failure atomicity.

The audit leaves behind a reusable proof method and maintained evidence registry,
not a one-time review.

## Canonical artifacts

- `docs/guides/algorithm-correctness-audit.md` — proof/audit method.
- `docs/audits/algorithm-registry.md` — inventory, evidence levels, findings.
- `docs/design/long-horizon-engineering-roadmap.md` — Program A links the
  canonical audit process.
- `AGENTS.md` — requires algorithmic changes to maintain audit evidence.
- focused regression tests beside each affected subsystem.

## Completed implementation sweep

### Numerical and timing correctness

- [x] replace overflow-prone hand-written sample variance with
      `statistics.stdev`;
- [x] fail explicitly when paired differences or normal-interval results exceed
      finite float range;
- [x] reject NaN/infinity/bool values from token-bucket rates, capacity,
      requests and timeouts;
- [x] enforce finite retry timing and positive integer attempt counts;
- [x] enforce finite benchmark calibration, comparison, stability and regression
      policy parameters;
- [x] enforce finite TTL/cache, circuit-breaker, bulkhead, deadline, polling and
      resource-budget timing;
- [x] close the `eventually(timeout=NaN)` non-termination hole;
- [x] validate manual-clock and deterministic-fuzz numeric domains.

### Representation and bounded algorithms

- [x] reject canonical JSON mapping keys that collide after string
      normalization;
- [x] enforce integer domains for hashing chunk/short-hash sizes;
- [x] enforce integer domains for chunk/batch/depth limits and bounded
      structures;
- [x] enforce redaction reveal-count bounds;
- [x] preserve existing varint transactionality/canonical-overflow evidence;
- [x] review bounded/digest streaming semantics and record remaining proof gaps;
- [x] add native C 64-bit unsigned varint encoding/zero-copy decoding with parity fallback (ALG-076);
- [x] add fast C JSON-clean validator to bypass duplicate heap allocations (ALG-077);
- [x] add deterministic virtual clock, faulty streams, and await boundary chaos (ALG-078).

### Parsing, process and project algorithms


- [x] fix `safe_int` so documented ordinary integer inputs are accepted;
- [x] validate async/subprocess/upstream timeout and concurrency domains;
- [x] parse Linux `/proc/<pid>/stat` without corrupting fields when command
      names contain spaces/parentheses;
- [x] terminate a launched profiler child if sampling fails;
- [x] fix project-root caches so cached roots cannot leak across independent
      anchors and late `sys.path` injection still works.

### Benchmark algorithms

- [x] validate scaling-efficiency baseline and non-baseline observations;
- [x] validate finite benchmark history/trend metrics and baseline windows;
- [x] reject boolean schema versions;
- [x] validate experiment repetition counts;
- [x] validate regression comparison/policy/stability inputs;
- [x] preserve zero-baseline behavior as an explicitly documented semantic;
- [x] record process-sampling and persistence limitations separately from
      correctness fixes.

### Documentation and governance

- [x] define A0-A4 evidence levels;
- [x] define proof packet, oracle guidance and numerical parameter checklist;
- [x] reconcile inventory against maintained public API families and benchmark
      namespace;
- [x] link the method and registry from Program A;
- [x] make registry maintenance an `AGENTS.md` rule;
- [x] add a changelog fragment.
- [x] add method-audit design documents under `docs/design/audit/`;
- [x] add exhaustive small-domain proof tests for workflow DAGs and uint64 varints;
- [x] add a one-job aggregate CI verifier that continues through independent
      gates and emits a machine-readable summary;
- [x] keep hosted triggers restricted to `main` and PRs targeting `main`;
- [x] clear the A0 inventory with focused proof tests for collections,
      formatting, identifiers, config, security paths, faults, buffers,
      provenance, network/sync, and benchmark persistence/protocol families;
- [x] execute aggregate hosted verification on `f55c510e014cf0233fd18f279808d3e9b22caf4a`
      (run `36382828055`).

## Remaining proof work

These are intentionally not hidden by the audit.

### Graph/traversal

- [x] add exhaustive four-node graph/property tests with an independent
      Kahn-style cycle oracle;
- [ ] decide whether recursion-depth limits warrant iterative traversal;
- [x] execute the exhaustive proof test; ALG-009 reached A4 in aggregate CI.

### Stateful/concurrent

- [x] add lease setup-failure and Awaitable-contract proofs;
- [x] add bounded scheduler initial-creation cleanup proofs;
- [x] add worker-pipeline bound and sibling-cancellation proofs;
- [ ] extend simultaneous-completion coverage to SingleFlight and any remaining
      cache/circuit-breaker races beyond the former A1 set.

### Filesystem/storage

- [x] fault-inject replace/publication failure paths for atomic files and
      transactional directories;
- [x] reject symlinked content-store roots/fanout ancestors and exercise the
      fallback publication branch;
- [ ] characterize the remaining cross-process fallback publication race;
- [ ] decide whether run-directory packaging needs transactional publication.

### Subprocess/resource bounding

- [x] integrate current-main streaming bounded subprocess capture and
      process-group termination with the audit timing contracts;
- [x] make benchmark workers inherit the bounded capture path;
- [x] record integrated A4 evidence after the final combined verification.

### Optional/security integrations

- [x] add SecureStore mutation/audit transaction, threaded serialization, bulk
      rollback, and key-publication recovery proofs;
- [x] enforce/document recursive stdlib validation for PEP 604 unions and
      container generics;
- [ ] add malformed-length/tamper vectors around secure-crypto format parsing;
- [x] compare stdlib and optional Pydantic validation behavior for the shared
      strict scalar contract; ALG-075 reached A4.

## Main/audit integration

- [x] preserve the full two-parent history rather than squashing either branch;
- [x] import all audit-only files and retain current-main security behavior on
      overlapping paths;
- [x] combine immutable CI action pins, pytest 9.0.3, dependency security
      floors, release preflight, and aggregate failure collection;
- [x] combine SecureStore filesystem trust with transaction/audit atomicity and
      recoverable key rotation;
- [x] combine bounded subprocess capture with finite timing contracts;
- [x] combine diagnostic redaction with recursive stdlib validation;
- [x] preserve distinct security and algorithm regression tests;
- [x] run one aggregate verification on the composed tree;
- [x] record the integrated SHA/run and restore main-only CI triggers;
- [ ] merge the verified integration branch into current `main`.

## Verification state

Two consolidated hosted verification sweeps are retained as execution evidence.

### A0 sweep

Verified revision: `f55c510e014cf0233fd18f279808d3e9b22caf4a`
Hosted run: `36382828055`

- Python 3.11: 864 passed;
- Python 3.12: 864 passed;
- release, Ruff/mypy, strict docs, packaging/isolation: PASS.

### Former A1 sweep

Verified revision: `dc243517c01f9f9b2836df0dfb4570fa1519906f`
Hosted run: `36389874370`

- [x] release/version/changelog metadata;
- [x] Ruff;
- [x] mypy — no issues in 97 source files;
- [x] Python 3.11 full suite — 943 passed;
- [x] strict Sphinx documentation build;
- [x] packaging/isolation — zero-dep, stdlib (18), validation (13),
      project (7), observability (2), secure (42), plot, and wheel/sdist passed;
- [x] Python 3.12 full suite — 943 passed;
- [x] aggregate verifier reported every gate PASS.

ALG-022, ALG-023, ALG-024, and ALG-050 through ALG-057 therefore satisfy the
repository's A4 evidence rule on the verified revision. Explicit limitations
such as the content-store fallback race and post-replace directory-fsync
semantics remain open gaps despite the A4 result for the implemented contract.

The final evidence/trigger-cleanup commit changes no audited source or test
logic, so execution evidence remains bound to `dc243517c01f9f9b2836df0dfb4570fa1519906f`.

### Integrated composed tree

Verified revision: `416c1105404fa42f499f323fead8872644848103`
Hosted run: `36403271808`

- [x] release/version/changelog preflight;
- [x] Ruff;
- [x] mypy — no issues in 97 source files;
- [x] Python 3.11 full suite — 991 passed;
- [x] strict Sphinx documentation build;
- [x] packaging/isolation — zero-dep, stdlib (19), validation (14),
      project (8), observability (4 + 4 subtests), secure (52), plot,
      and wheel/sdist passed;
- [x] Python 3.12 full suite — 991 passed;
- [x] aggregate verifier reported every post-preflight gate PASS.

This is the first verification of the composed security + algorithm-audit tree.
The cleanup commit after this section changes only documentation and restores
the intended main-only CI trigger.

## Definition of done

The long-horizon audit is complete when:

1. every maintained algorithmic family has at least A1 evidence or an explicit
   A0 reason;
2. high-risk numerical, graph, binary, concurrency and state-machine families
   reach A4;
3. every discovered correctness defect has a regression test;
4. explicit limitations have either a follow-up task or a documented accepted
   contract;
5. the full local verification gate passes on the final branch state.
