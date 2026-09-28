# Repository-wide algorithm correctness audit

Status: active
Branch: `audit/algorithm-correctness`
Started: 2026-09-28
Base: `main@cf3697d7457c5901ee1c927bc6dae347d5428722`

## Goal

Audit every algorithmic implementation in `gunz-utils` for contract
correctness, numerical stability, parameter-domain validation, boundary/special
cases, deterministic behavior, complexity/boundedness, and failure atomicity.

The audit must leave behind reusable proof guidance and a maintained evidence
registry rather than a one-time review.

## Canonical artifacts

- `docs/guides/algorithm-correctness-audit.md` — proof/audit method.
- `docs/audits/algorithm-registry.md` — inventory, levels, evidence, findings.
- `docs/design/long-horizon-engineering-roadmap.md` — broader correctness
  program; link the audit method from Program A.
- regression tests beside the existing subsystem tests.

## Workstreams

### W1 — Audit framework and inventory

- [x] create dedicated audit branch from current main;
- [x] define A0-A4 evidence levels;
- [x] define proof packet and numerical parameter checklist;
- [x] create initial repository-wide algorithm inventory;
- [x] identify high-risk first-wave algorithms;
- [ ] reconcile inventory against every maintained public module and benchmark
      submodule so no algorithmic unit is omitted.

### W2 — Numerical/statistical correctness

- [x] review stats, experiment comparisons, benchmark calibration/policy,
      stability diagnostics, retry timing, and rate limiter parameter domains;
- [ ] replace overflow-prone sample variance calculations;
- [ ] enforce finite/bounded token-bucket inputs;
- [ ] enforce finite/bounded retry timing inputs;
- [ ] enforce valid benchmark calibration and stability parameters;
- [ ] enforce regression-policy direction/threshold/metric validity;
- [ ] add extreme-magnitude, NaN, infinity, zero-baseline, singleton and bound
      regression tests.

### W3 — Graph/traversal/deterministic selection

- [x] review workflow DAG topological order/fingerprint propagation;
- [x] review provenance graph cycle/ancestor behavior;
- [x] review stable named-item sampling;
- [ ] add exhaustive small-graph/property tests where current examples are
      insufficient;
- [ ] characterize recursion-depth limits and decide whether iterative traversal
      is required.

### W4 — Binary/streaming/bounded algorithms

- [x] review 64-bit canonical varint transactionality/overflow behavior;
- [x] static-review bounded/digest writer forward-progress rules;
- [ ] audit all partial read/write paths and content-store streaming paths;
- [ ] add exhaustive varint boundary vectors and malformed encodings;
- [ ] verify failure atomicity for every mutable cursor/writer.

### W5 — Stateful/concurrent algorithms

- [x] initial token bucket review;
- [x] static-review lease-loss precedence;
- [ ] TTL/LRU cache and async coalescing;
- [ ] SingleFlight;
- [ ] circuit breaker;
- [ ] bulkhead;
- [ ] worker pipeline/backpressure;
- [ ] signal/resource lifecycle;
- [ ] cancellation and simultaneous-completion race tests.

### W6 — Hashing/serialization/filesystem/security

- [ ] canonical JSON and structured hashes;
- [ ] directory manifests/hashes;
- [ ] partition/content fingerprints;
- [ ] path containment and atomic filesystem algorithms;
- [ ] redaction recursion;
- [ ] crypto/store derivation and authenticated-decryption contracts.

### W7 — Benchmark/profiling algorithms

- [ ] benchmark percentiles and descriptive summaries;
- [ ] pairwise comparison and zero-baseline semantics;
- [ ] history slope/moving baseline;
- [ ] process-tree discovery/aggregation;
- [ ] derived metrics;
- [ ] regression gate;
- [ ] artifact checksum/packaging;
- [ ] schema migration;
- [ ] experiment orchestration.

### W8 — Documentation and policy integration

- [ ] link the audit guide/registry from Program A of the long-horizon roadmap;
- [ ] add an algorithm-change rule to `AGENTS.md`;
- [ ] add changelog fragment for behavioral fixes;
- [ ] keep registry levels synchronized with test evidence.

### W9 — Verification

Hosted feature-branch CI must remain disabled. Use repository-local gates.

- [ ] focused tests for each repaired subsystem;
- [ ] `python scripts/ci.py lint`;
- [ ] `python scripts/ci.py test`;
- [ ] `python scripts/ci.py docs`;
- [ ] `./scripts/verify.sh`;
- [ ] promote qualifying registry entries to A3/A4 only after execution.

## Definition of done

- comprehensive algorithm inventory with no unexplained A0 omissions;
- every audited entry has contract, domains, invariants, oracle/test evidence,
  special cases, and complexity/boundedness notes where relevant;
- numerical APIs explicitly define NaN/infinity/zero/boundary behavior;
- every discovered defect has a regression test;
- high-risk families reach A4;
- docs and registry are current at the final branch head;
- no hosted CI is enabled or triggered solely for this feature branch.
