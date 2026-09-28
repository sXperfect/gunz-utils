# Algorithm Audit Registry

## Scope

This is the maintained inventory and evidence ledger for algorithmic behavior in
`gunz-utils`. Audit levels follow
[`docs/guides/algorithm-correctness-audit.md`](../guides/algorithm-correctness-audit.md).

The registry is intentionally broader than numerical routines. It includes
algorithms/state machines whose correctness depends on ordering, boundedness,
atomicity, deterministic selection, graph structure, timing, or concurrency.

Last inventory pass: **2026-09-28** against `main` commit
`cf3697d7457c5901ee1c927bc6dae347d5428722`.

## Current audited set

These entries received implementation review plus review of their existing test
evidence during the initial audit pass. They remain A2 until focused tests are
executed after the audit fixes land.

| ID | Algorithm / family | Location | Level | Proof focus / evidence | Findings |
|---|---|---|---|---|---|
| ALG-001 | Percentile bootstrap mean CI | `stats.bootstrap_mean_ci` | A2 | seeded determinism, percentile bounds, finite-input validation; `tests/test_core/test_stats.py` | variance-related siblings need stable arithmetic review |
| ALG-002 | Paired standardized effect (Cohen's dz) | `stats.paired_effect` | A2 | known differences, sample SD semantics, zero variance, singleton, finiteness; `test_stats.py` | naïve squared-deviation variance can overflow |
| ALG-003 | Normal mean summary / z interval | `stats.normal_mean_summary` | A2 | known mean/SD, singleton, z validation; `test_stats.py` | naïve squared-deviation variance can overflow |
| ALG-004 | Numeric metric comparison | `experiments.compare_numeric_metrics` | A2 | missing keys, bool-vs-number semantics, relative delta; `test_experiments.py` | zero/non-finite relative semantics need explicit documentation |
| ALG-005 | Relative metric improvement decision | `experiments.metric_improvement` | A2 | direction, threshold, non-finite rejection; `test_experiments.py` | hidden `1e-12` zero-baseline scale needs contract documentation |
| ALG-006 | Cartesian parameter grid | `experiments.parameter_grid` | A2 | Cartesian order, empty product identity, empty factor rejection; `test_experiments.py` | none found in reviewed cases |
| ALG-007 | Stable BLAKE2b priority | `sampling.stable_priority` | A2 | deterministic 64-bit output, seed effect; `test_sampling.py` | bool-as-int seed semantics not explicit |
| ALG-008 | Stable named-item sampling | `sampling.sample_named_items` | A2 | input-order independence, filtering-before-budget, duplicate rejection; `test_sampling.py` | none found in reviewed cases |
| ALG-009 | Workflow topological ordering | `dag.WorkflowDAG._topological_order` | A2 | dependency-before-consumer, missing dependency, cycle rejection; `test_dag.py` | recursion depth remains proportional to graph depth |
| ALG-010 | Effective transitive fingerprint | `dag.WorkflowDAG.effective_fingerprint` | A2 | dependency order sensitivity, unfingerprinted propagation, cache invalidation; `test_dag.py` | none found in reviewed cases |
| ALG-011 | Provenance DAG cycle/ancestor traversal | `provenance_graph.ProvenanceGraph` | A2 | unresolved inputs, ancestor order, cycle rollback, replace rollback; `test_provenance_graph.py` | recursion depth remains proportional to graph depth |
| ALG-012 | Unsigned 64-bit varint encode/decode | `binary.encode_uvarint`, `ByteReader.read_uvarint` | A2 | round trip, 64-bit overflow, truncation rollback, canonical encoding; `test_m16_m18.py`, `test_m8_m19_audit_regressions.py` | strict bool input semantics not explicit |
| ALG-013 | Priority + recent bounded retention | `structures.retain_priority_and_recent` | A2 | stable order, priority preservation, zero/None limit, predicate once/item; `test_structures_retention.py` | none found in reviewed cases |
| ALG-014 | Async token bucket | `rate_limit.AsyncRateLimiter` | A2 | capacity invariant, no-overdraw, timeout behavior; several core tests | **defect:** non-finite/bool parameters can poison token state |
| ALG-015 | Benchmark loop calibration | `benchmark.runner.calibrate_loops` | A2 | lower bound and calibrated loop count; `test_native_benchmark_mechanisms.py` | **defect:** target/max-loop domains incompletely validated |
| ALG-016 | Benchmark percentile/stat summary | `benchmark.runner.benchmark`, `_percentile` | A2 | sample count/stats shape; `test_benchmark.py` | numerical parameter domains need stricter validation |
| ALG-017 | Regression metric policy | `benchmark.policy.evaluate_metric` | A2 | lower/higher-is-better threshold cases; `test_regression_policy.py` | **defect:** invalid direction/NaN/negative thresholds can silently pass |
| ALG-018 | Multi-metric regression gate | `benchmark.gate.evaluate_regression_gate` | A2 | comparability warning behavior; `test_m6_hardening.py` | inherits policy validation weakness |
| ALG-019 | Benchmark history slope/moving baseline | `benchmark.trends.summarize_history` | A1 | implementation reviewed: OLS slope, moving median, zero baseline | direct test evidence not yet located/reviewed |
| ALG-020 | Stability diagnostics | `benchmark.diagnostics.analyze_stability` | A2 | CV/range/outlier structure; benchmark mechanism tests | **defect:** NaN/negative thresholds can make invalid config appear stable |
| ALG-021 | Retry exponential backoff / deadlines | `retry._delay`, `RetryPolicy`, retry runners/decorators | A1 | implementation/timeout budget reviewed | **defect:** non-finite delay/timeout parameters accepted by common validator |
| ALG-022 | Renewable lease heartbeat race | `leases.run_with_lease_heartbeat` | A1 | deterministic lease-loss precedence and cleanup reviewed | focused race/cancellation tests still need review |
| ALG-023 | Bounded/digest streaming writes | `streaming.BoundedWriter`, `DigestWriter`, `copy_and_hash` | A1 | partial-write forward progress, byte limit, digest of committed bytes reviewed | focused test evidence still needs review |
| ALG-024 | Pairwise partition-overlap detection | `partitions.partition_overlaps` | A1 | deterministic pair ordering and set intersection reviewed | focused test evidence still needs review |

## Complete algorithm inventory

A0 entries below are intentionally **not** correctness claims. They are the
remaining inventory to drive the repository-wide sweep.

| Family | Algorithmic units | Initial level |
|---|---|---|
| Collections | stable `unique`; `group_by`; collision semantics of `index_by`; predicate partition | A0 |
| Nested data | `deep_get`; `deep_set`; recursive `deep_merge` including list dedup strategy | A0 |
| Iteration | `chunked`; `batched`; recursive/iterative flattening semantics; `first` | A0 |
| Formatting | byte/count magnitude selection and rounding; duration decomposition | A0 |
| Hashing | content/file/short hash; directory manifest/hash; structured hash | A0 |
| Serialization | recursive `to_jsonable`; deterministic/canonical JSON | A0 |
| Identifiers | deterministic IDs; short hash-derived IDs | A0 |
| Configuration | recursive config merge; environment override path construction | A0 |
| Filesystem/path | lexical and resolved containment; atomic byte/text writes; directory sync/replace primitives | A0 |
| Security | filename sanitization; safe path join/open; allow/deny name access policy | A0 |
| Redaction | key-pattern detection; recursive redaction; reveal-prefix semantics | A0 |
| Cache | sync TTL+LRU eviction; async TTL/coalesced miss; recency TTL policy; SingleFlight | A0 |
| Concurrency | limited gather; ordered/unordered concurrent map; worker pipeline/backpressure | A0 |
| Resilience | circuit-breaker state machine; bulkhead capacity/timeout | A0 |
| Time/test polling | monotonic deadlines/remaining; `eventually`; async polling | A0 |
| Fault injection | `FailAfter`; deterministic `FaultSequence` | A0 |
| Binary/buffers | byte-reader bounded reads beyond varints; readonly memory views; acceleration dispatch | A0 |
| Structures | ring buffer; `deep_diff`; `freeze_structure`; other bounded heaps/queues in module | A0 |
| Provenance | execution manifest capture/filtering; runtime provenance normalization | A0 |
| Versioning | versioned envelope validation; migration path traversal/order | A0 |
| Plugins | deterministic discovery/selection and failure isolation | A0 |
| Resource limits | consumable budgets and limit arithmetic | A0 |
| Resource lifecycle | sync/async grouped cleanup ordering/error behavior | A0 |
| Signals | registration/restoration and async signal coordination | A0 |
| Content store | content-address path derivation, put/get/verify, digest-size validation | A0 |
| Sync | rsync mirror completion-marker semantics | A0 |
| Network | URI construction/escaping; reachability timeout semantics | A0 |
| Typed validation | stdlib annotation checking recursion; Pydantic adapter equivalence | A0 |
| Project discovery | parent traversal plus Git fallback | A0 |
| Secure crypto/store | PBKDF2/AES/Fernet parameterization, authenticated decrypt failure, secure-store key derivation | A0 |
| Benchmark comparison | pairwise relative changes and zero-baseline behavior | A0 |
| Benchmark diagnostics | environment comparability warnings | A0 |
| Benchmark history | history append/load/filter/order semantics | A0 |
| Benchmark artifacts | registration, basename collision handling, checksum verification | A0 |
| Benchmark schema | validation and migration | A0 |
| Benchmark profiling | process-tree discovery, RSS/PSS/private aggregation, sparse detailed sampling | A0 |
| Benchmark derived metrics | IPC, rates, per-op metrics and zero-denominator behavior | A0 |
| Benchmark run building | aggregation of timing/profile/derived metrics/warnings | A0 |
| Benchmark experiment orchestration | parameter combinations, repetitions, result association | A0 |
| Benchmark reports | summary aggregation used by JSON/CSV/Markdown/HTML/plot output | A0 |
| Benchmark workers | worker request/result protocol, subprocess timeout/error propagation | A0 |

## Initial defects and proof gaps

### FIND-001 — unstable variance arithmetic

Affected: ALG-002, ALG-003.

Both functions compute sample variance with
`sum((x - mean) ** 2) / (n - 1)`. Squaring can overflow even when the final
standard deviation is representable. Replace the hand-written variance with a
numerically safer standard-library implementation and add extreme-finite-value
regressions.

### FIND-002 — token bucket accepts non-finite values

Affected: ALG-014.

`rate`, `capacity`, and `tokens` currently rely on inequality checks.
`NaN` bypasses those checks and can turn the internal token balance into
`NaN`. Validate real finite positive values and reject bools.

### FIND-003 — benchmark calibration/config numeric domains

Affected: ALG-015, ALG-016, ALG-020.

Calibration and stability thresholds do not consistently reject `NaN`,
infinity, invalid loop limits, or negative thresholds. Invalid measurement
configuration must fail explicitly before a benchmark result is produced.

### FIND-004 — regression policy is under-validated

Affected: ALG-017, ALG-018.

Runtime typing does not enforce the `Literal` direction. An unknown direction
falls into the "higher" branch. Negative/non-finite thresholds and non-finite
metrics may also produce plausible pass/fail values. Add runtime validation.

### FIND-005 — retry timing accepts non-finite configuration

Affected: ALG-021.

The shared retry validator checks only signs. `NaN` can reach delay/sleep
calculation and infinity can create unbounded waits. Define and enforce finite
non-negative delay/timeout values.

## Completion rule

The repository-wide algorithm audit is complete only when:

1. no A0 entries remain for algorithmic code in maintained public modules;
2. every A1/A2 proof gap has an owner/test path and is either resolved or
   documented as a deliberate limitation;
3. high-risk numerical, graph, binary, concurrency and state-machine families
   reach A4;
4. all discovered defects have regression tests;
5. `./scripts/verify.sh` passes on the final audit branch;
6. the registry commit is updated to the audited branch head and date.
