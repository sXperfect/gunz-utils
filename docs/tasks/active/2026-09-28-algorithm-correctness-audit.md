# Repository-wide algorithm correctness audit

Status: active — A0 sweep complete and aggregate CI verified; remaining A1/A2
high-risk proof work pending
Branch: `audit/algorithm-correctness`
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
- [x] review bounded/digest streaming semantics and record remaining proof gaps.

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

- [ ] exhaustive cancellation/simultaneous-completion race tests for
      SingleFlight, worker pipelines, leases, circuit breaker and bulkhead;
- [ ] prove queue/input boundedness for every concurrency primitive.

### Filesystem/storage

- [ ] fault-inject rename/fsync/publication failure paths;
- [ ] characterize content-store fallback publication races;
- [ ] decide whether run-directory packaging needs transactional publication.

### Subprocess/resource bounding

- [ ] redesign `max_output_bytes` if a true resident-memory bound is required;
      current subprocess helpers validate captured output after collection.

### Optional/security integrations

- [ ] finish a line-by-line transactional/concurrency audit of SecureStore;
- [ ] add malformed-length/tamper vectors around secure-crypto format parsing;
- [x] compare stdlib and optional Pydantic validation behavior for the shared
      strict scalar contract; ALG-075 reached A4.

## Verification state

Hosted aggregate CI was deliberately enabled for the audit branch for the A0
sweep, then disabled again after success.

Verified revision: `f55c510e014cf0233fd18f279808d3e9b22caf4a`
Hosted run: `36382828055`

Evidence from the successful run:

- [x] release/version/changelog metadata;
- [x] Ruff;
- [x] mypy — no issues in 97 source files;
- [x] Python 3.11 full suite — 864 passed;
- [x] strict Sphinx documentation build;
- [x] packaging/isolation — zero-dep, stdlib, validation, project,
      observability, secure, plot, and wheel/sdist all passed;
- [x] Python 3.12 full suite — 864 passed;
- [x] aggregate verifier reported every gate PASS.

The final documentation/trigger-cleanup commit changes no audited source or test
logic, so execution evidence remains bound to the code revision above.

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
