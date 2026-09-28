# Long-Horizon Engineering Roadmap

## Objective

Evolve `gunz-utils` into a small, dependable production foundation and
performance-engineering SDK. Work is organized by system properties rather than
individual helper functions.

Every milestone must improve at least one of:

1. correctness;
2. robustness;
3. speed or measurement overhead;
4. reproducibility;
5. API/schema stability;
6. cross-platform behavior;
7. observability and debuggability.

## Engineering invariants

These are permanent requirements.

### Core

- Core imports remain standard-library only.
- Optional integrations never make core imports fail.
- Public `__all__` entries must resolve and remain unique.
- Cancellation must not be swallowed.
- Resource acquisition must have deterministic cleanup.
- User secrets must not leak through diagnostics or exceptions.
- Filesystem writes that promise atomicity must remain atomic on failure.
- Bounded APIs must bound both active work and queued/input consumption.

### Performance measurement

- Measurement overhead must be observable and configurable.
- Raw samples are retained; summaries never replace source measurements.
- Missing OS metrics are represented as unavailable, never fabricated as zero.
- Baseline/candidate comparisons must surface environment incompatibilities.
- Process-tree metrics include descendants, not only the Python launcher.
- Expensive metrics have independent sampling controls.
- Backend-native artifacts are preserved even when normalized.

### Compatibility

- Serialized schemas are explicitly versioned.
- Readers support at least the previous schema version during migrations.
- Public removals require a deprecation cycle.
- CLI output intended for machines has a stable schema and explicit version.
- Cross-platform unsupported behavior fails explicitly.

## Program A — Correctness and adversarial testing

The canonical per-algorithm audit method is
[`docs/guides/algorithm-correctness-audit.md`](../guides/algorithm-correctness-audit.md).
It defines A0-A4 evidence levels, proof obligations, numerical parameter-domain
checks, special cases, oracle requirements, and failure-atomicity review. The
maintained implementation/evidence inventory is
[`docs/audits/algorithm-registry.md`](../audits/algorithm-registry.md).

An algorithm is not considered fully verified merely because examples pass:
high-risk implementations should reach A4, which requires the focused proof
tests plus the repository's full local verification gate.

### A1. Property-based invariants

Implement deterministic/property-style generators without requiring Hypothesis
at runtime. Cover:

- serialization round trips and canonical determinism;
- deep merge associativity where semantics permit;
- path traversal/symlink containment;
- redaction never exposing configured secret values;
- cache capacity/TTL invariants;
- retry attempt/deadline invariants;
- rate limiter token conservation;
- concurrency ordering and boundedness;
- circuit-breaker state transitions;
- benchmark result/schema round trips.

### A2. Fault injection

Create reusable fault injectors for:

- filesystem write/rename/fsync failure;
- subprocess timeout/cancellation/signals;
- partial reads/writes;
- task cancellation at every await boundary;
- clock advancement;
- worker crashes;
- malformed/truncated JSON;
- inaccessible/disappearing `/proc` entries.

### A3. Stress and race testing

Run repeated high-contention scenarios for:

- SingleFlight;
- TTL caches;
- rate limiter;
- bulkhead;
- circuit breaker;
- atomic writes;
- concurrent subprocess lifecycle;
- process-tree sampling while descendants rapidly fork/exit.

Exit criterion: no known correctness defect under deterministic stress suites.

## Program B — Performance and overhead

### B1. Benchmark the library itself

Build benchmark groups for:

- iteration/batching;
- hashing;
- serialization;
- redaction;
- cache hit/miss;
- concurrency scheduling;
- rate limiter;
- process-tree sampling;
- PSS/full-memory sampling;
- benchmark runner overhead.

Store baselines by release and compare locally.

### B2. Profiler hot path

Replace full `/proc` rescans with incremental descendant tracking where safe.
Separate cheap and expensive sampling paths. Avoid allocating full dataclass
graphs on every high-frequency sample; use compact internal records and
materialize public objects at the boundary.

Measure profiler overhead at 1000, 100, 20, 10 and 1 ms intervals.

Targets:

- RSS-only sampling should have low single-digit CPU overhead on ordinary trees.
- Detailed PSS sampling must be independently rate limited.
- Disabled metrics should incur effectively zero collection cost.

### B3. Allocation and copy reduction

Audit hot paths for:

- unnecessary list materialization;
- repeated sorting;
- duplicate encoding/decoding;
- avoidable dict/dataclass conversion;
- excessive exception construction;
- repeated filesystem metadata reads.

Use before/after benchmarks for every optimization.

## Program C — Measurement validity

### C1. Environment capture

Capture:

- CPU model/topology;
- logical/physical CPU information where available;
- kernel/OS;
- Python/runtime;
- CPU affinity;
- load average;
- frequency/governor/turbo metadata when accessible;
- container/cgroup limits;
- Git commit/dirty state;
- relevant environment variables only through an allowlist.

### C2. Noise diagnostics

Implement:

- coefficient of variation;
- robust outlier diagnostics;
- drift across sample order;
- warmup instability;
- insufficient sample duration;
- background CPU/load warnings;
- affinity mismatch;
- environment comparability score/warnings.

### C3. Derived metrics

Centralize:

- IPC;
- cycles/op;
- branch-miss rate;
- cache-miss rate;
- CPU cores utilized;
- CPU seconds/op;
- read/write throughput;
- memory-time integral;
- PSS/RSS ratio;
- scaling speedup and efficiency;
- throughput/latency tradeoff.

Exit criterion: reports explain whether a performance conclusion is trustworthy.

## Program D — Reproducible benchmark execution

### D1. Native worker protocol

Replace ad-hoc stdout JSON with a versioned worker request/result protocol.
Support fresh interpreters, multiple workers, deterministic seeds, timeouts,
crash reporting and stderr capture.

### D2. Isolation controls

Support:

- GC policy;
- CPU affinity;
- environment allowlist;
- working directory;
- setup/teardown hooks;
- warmup/calibration;
- minimum run duration;
- process priority where safely available.

### D3. Parameter experiments

Support Cartesian parameter matrices, repetitions, labels and derived scaling
metrics without requiring Hyperfine/ASV.

Exit criterion: another Gunz repository can define and reproduce a complete
benchmark experiment using only `gunz-utils`.

## Program E — Unified performance data model

### E1. PerformanceRun v1

Finalize:

- identity;
- timestamp;
- Git provenance;
- environment;
- benchmark timing;
- process-tree profile;
- hardware counters;
- derived metrics;
- artifacts;
- warnings;
- parameters.

### E2. Schema evolution

Implement migrations, schema validation, unknown-field preservation where
possible, and backward-compatible readers.

### E3. Artifact registry

Track native artifacts with:

- type;
- path/URI;
- media type;
- producer;
- checksum;
- size;
- optional compression;
- description.

Exit criterion: one run directory is self-describing and portable.

## Program F — Reporting and regression analysis

### F1. Reports

Generate:

- JSON;
- CSV;
- Markdown;
- self-contained HTML;
- plots;
- machine-readable regression result.

### F2. History

Support histories across commits/releases, moving baselines, trend slopes,
change-point hints and parameter-scaling plots.

### F3. Regression policy

Policies should support absolute and relative thresholds, metric direction,
noise/stability requirements and environment comparability requirements.

## Program G — Security and robustness

Audit all new benchmark/profiling surfaces for:

- shell injection;
- path traversal;
- unsafe artifact filenames;
- environment/secret leakage;
- unbounded stdout/stderr;
- unbounded result files;
- malicious JSON sizes/nesting;
- symlink attacks;
- process cleanup;
- profiler permission failures.

External commands must remain argv-based by default.

## Program H — Cross-platform architecture

Define a backend interface:

```text
ProcessSampler
  LinuxProcSampler
  WindowsSampler
  MacOSSampler
```

Linux remains the reference/full-feature backend. Windows/macOS implementations
may expose fewer metrics but must use the same unavailable-metric semantics.

Do not emulate unsupported counters with misleading approximations.

## Program I — Native vs external tooling

Prefer native clean-room implementations for useful mechanisms from
predominantly Python tools when they reduce dependencies and integrate better.

Keep external engines when the difficult part is native/kernel/runtime
instrumentation:

- Linux perf;
- Memray native allocation tracking;
- py-spy interpreter sampling;
- heaptrack allocator instrumentation.

External adapters and native mechanisms must normalize into the same
`PerformanceRun` contract.

## Program J — API and release discipline

- Introduce a deprecation helper and policy.
- Maintain API-contract tests.
- Add schema-contract fixtures.
- Record public changes as conflict-free files under `changes/` and assemble
  the changelog only during release preparation.
- Use strict semantic versioning enforced by `scripts/release.py`.
- Keep `pyproject.toml` as the sole static package-version source.
- Keep feature-branch Actions disabled; `scripts/verify.sh` is the development
  gate, with hosted CI only for pushes to `main` and PRs targeting `main`.

## Milestones

### M1 — Trustworthy core

Programs A + G. Focus on invariants, fault injection and stress tests.

### M2 — Low-overhead profiler

Programs B + C. Quantify and reduce measurement distortion.

### M3 — Reproducible experiments

Programs D + E. Stable worker protocol and portable PerformanceRun artifacts.

### M4 — Regression platform

Program F. Histories, policies, reports and scaling analysis.

### M5 — Portability and stability

Programs H + J. Backend interfaces, schema/API migration and release discipline.


### M6 — Production hardening and self-measurement

Close integration gaps left by M1–M5:

- enforce benchmark public API integrity;
- validate and migrate serialized PerformanceRun schemas;
- verify artifact size/checksum integrity;
- combine metric thresholds with comparability warnings in regression gates;
- measure the benchmark framework's own overhead;
- maintain contract tests for all of the above.

Exit criterion: corrupted artifacts, unsupported schemas, broken exports, and
environment-invalid regressions fail explicitly rather than producing plausible
but misleading results.


### M7 — Profiler efficiency and experiment orchestration

Integrate the measurement stack into reproducible experiments:

- Cartesian parameter matrices with explicit repetitions;
- automatic PerformanceRun construction from timing/resource measurements;
- automatic provenance, derived metrics, stability and load warnings;
- portable run directories containing run.json and checksummed artifacts;
- benchmark-package public API contract enforcement.

Exit criterion: consumer repositories can execute parameter experiments and
produce portable, self-describing run directories without custom orchestration.


### M8–M10 — Data, filesystem and serialization foundation

Completed with bounded structures, atomic/transactional filesystem primitives,
JSONL streaming, canonical fingerprints and bounded stream hashing.

### M11–M13 — Runtime, observability and configuration

Completed with bounded worker pipelines/backpressure, dependency-free
instrumentation, and typed configuration values with provenance.

### M14–M15 — Security limits and deterministic testing

Completed with reusable resource limits, manual time and seeded fuzz inputs.

### M16–M18 — Acceleration boundary, binary data and resource lifecycle

Completed with zero-copy buffer views, optional acceleration dispatch, bounded
binary/varint primitives, and deterministic sync/async resource groups.

### M19 — Package architecture

Subsystem-first imports are the default. New subsystem APIs are not
automatically added to the package root. See
[`package-api-policy.md`](package-api-policy.md).

### M20 — Cross-project foundation

Completed foundation for Hyperion, Helios-JS, and other Gunz repositories:

- failure-isolated plugin discovery;
- consumable resource budgets;
- allowlisted runtime provenance;
- versioned schema envelopes and migrations;
- result-aware retry policies;
- bounded digest streaming;
- atomic deterministic JSON publication;
- repaired filesystem, resilience, and package-root API defects.

Consumer repositories should import these mechanisms from subsystem namespaces and keep domain semantics local.

## Definition of done

The subsystem is mature when:

- correctness and stress invariants are automated;
- profiler overhead is benchmarked and bounded;
- benchmark conclusions carry stability/comparability diagnostics;
- experiments reproduce from self-contained run artifacts;
- schemas and APIs have explicit compatibility policy;
- native and external profiler data share one model;
- consumer repositories no longer need custom benchmark infrastructure.
