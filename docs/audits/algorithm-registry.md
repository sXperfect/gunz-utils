# Algorithm Audit Registry

## Scope and evidence rules

This is the maintained inventory and evidence ledger for algorithmic behavior in
`gunz-utils`. The proof method and A0-A4 levels are defined in
[`docs/guides/algorithm-correctness-audit.md`](../guides/algorithm-correctness-audit.md).

The registry covers numerical/statistical routines, graph algorithms,
deterministic selection and hashing, parsing/canonicalization, bounded streaming,
timing/state machines, concurrency, persistence/publication, process profiling,
and benchmark calculations.

Inventory baseline: **2026-09-28**, starting from
`main@cf3697d7457c5901ee1c927bc6dae347d5428722`.

### Level reminder

- **A0** — inventoried only; no correctness claim.
- **A1** — implementation reviewed against an explicit contract/invariants.
- **A2** — A1 plus test evidence reviewed/added.
- **A3** — A2 plus focused proof/adversarial tests executed successfully.
- **A4** — A3 plus the full local verification gate passes.

This branch is intentionally capped at **A2** until tests are actually executed
in a local checkout. Added tests are evidence artifacts, not proof of successful
execution.

## Audited algorithm set

| ID | Algorithm / family | Location | Level | Main proof obligations / evidence | Current result |
|---|---|---|---|---|---|
| ALG-001 | Percentile bootstrap mean CI | `stats.bootstrap_mean_ci` | A2 | seeded determinism, confidence/sample/seed domains, finite real observations; `test_stats.py` | strict numerical parameter domains added; basic percentile semantics retained |
| ALG-002 | Paired standardized effect | `stats.paired_effect` | A2 | paired-length invariant, sample SD, singleton/zero variance, huge finite values | fixed overflow-prone variance and overflowed pair differences |
| ALG-003 | Normal mean summary / z interval | `stats.normal_mean_summary` | A2 | sample SD, singleton, z domain, representability | fixed unstable variance; unrepresentable intervals fail explicitly |
| ALG-004 | Numeric metric comparison | `experiments.compare_numeric_metrics` | A2 | missing keys, numeric filtering, relative delta | reviewed; zero-baseline semantics remain explicit follow-up |
| ALG-005 | Relative metric improvement | `experiments.metric_improvement` | A2 | direction, threshold, non-finite rejection | reviewed; near-zero scale contract should be documented further |
| ALG-006 | Cartesian parameter grid | `experiments.parameter_grid` | A2 | Cartesian product order, empty factors | reviewed; no defect found |
| ALG-007 | Stable priority hash | `sampling.stable_priority` | A2 | deterministic BLAKE2b output, seed influence | reviewed; bool-as-int seed semantics remain a minor gap |
| ALG-008 | Stable named-item sampling | `sampling.sample_named_items` | A2 | order independence, duplicate rejection, budget/filter ordering | reviewed; no defect found |
| ALG-009 | Workflow topological order | `dag.WorkflowDAG._topological_order` | A2 | dependency-before-consumer, missing dependency, cycles | correct for reviewed cases; recursion depth is a limitation |
| ALG-010 | Effective transitive fingerprint | `dag.WorkflowDAG.effective_fingerprint` | A2 | dependency sensitivity, propagation, cache invalidation | reviewed; no defect found |
| ALG-011 | Provenance DAG cycle/ancestor traversal | `provenance_graph.ProvenanceGraph` | A2 | cycle rollback, unresolved nodes, deterministic ancestors | reviewed; recursion depth is a limitation |
| ALG-012 | Unsigned 64-bit canonical varint | `binary.encode_uvarint`, `ByteReader.read_uvarint` | A2 | round trip, overflow, canonical form, truncation rollback | existing strong evidence reviewed |
| ALG-013 | Priority + recent retention | `structures.retain_priority_and_recent` | A2 | stable order, priority preservation, zero/None limits | strengthened bound validation |
| ALG-014 | Async token bucket | `rate_limit.AsyncRateLimiter` | A2 | balance in [0, capacity], no overdraw, timeout, finite parameters | fixed NaN/inf/bool state poisoning |
| ALG-015 | Benchmark loop calibration | `benchmark.runner.calibrate_loops` | A2 | monotonic loop growth, target/max bounds | fixed non-finite target and invalid max-loop domains |
| ALG-016 | Benchmark sampling/stat summary | `benchmark.runner.benchmark` | A2 | iteration bounds, min-time semantics, finite config, percentile summary | configuration hardened; focused execution pending |
| ALG-017 | Regression metric policy | `benchmark.policy.MetricPolicy`, `evaluate_metric` | A2 | valid direction, finite metrics, non-negative thresholds | fixed invalid direction/NaN/negative policy acceptance |
| ALG-018 | Multi-metric regression gate | `benchmark.gate.evaluate_regression_gate` | A2 | required metrics, policy aggregation, comparability warnings | inherits hardened policy validation |
| ALG-019 | Benchmark history trend summary | `benchmark.trends.summarize_history` | A2 | OLS slope, moving median, finite metric values, baseline window | hardened domains and unknown-metric errors |
| ALG-020 | Stability diagnostics | `benchmark.diagnostics.analyze_stability` | A2 | CV/range/outlier diagnostics, finite non-negative samples/thresholds | fixed invalid config appearing stable |
| ALG-021 | Retry backoff / deadline policy | `retry.RetryPolicy`, retry runners | A2 | bounded attempts, finite delays/timeouts, overflow-safe exponential cap | fixed NaN/inf timing acceptance and huge-exponent overflow |
| ALG-022 | Renewable lease heartbeat race | `leases.run_with_lease_heartbeat` | A1 | lease-loss precedence, cleanup, cancellation | static review complete; focused race tests still pending |
| ALG-023 | Bounded/digest streaming writes | `streaming.BoundedWriter`, `DigestWriter`, `copy_and_hash` | A1 | partial-write progress, committed-byte accounting, byte limits | static review complete; fault-injection proof pending |
| ALG-024 | Partition overlap detection | `partitions.partition_overlaps` | A1 | deterministic pair order, set intersection | static review complete; broader property tests pending |
| ALG-025 | TTL/LRU caches | `cache.ttl_cache`, `async_ttl_cache` | A2 | TTL expiry, capacity, coalesced async misses, finite TTL | fixed NaN/inf/bool TTL/capacity domains |
| ALG-026 | Circuit breaker | `resilience.AsyncCircuitBreaker` | A2 | state transitions, failure threshold, recovery timer | hardened count/timing domains; race execution pending |
| ALG-027 | Async bulkhead | `resilience.AsyncBulkhead` | A2 | concurrency bound, timeout acquisition | hardened limit/timeout domains |
| ALG-028 | Monotonic deadline arithmetic | `time_utils.monotonic_deadline`, `remaining` | A2 | finite monotonic deadlines, non-negative remaining time | fixed NaN/inf deadline semantics |
| ALG-029 | Sync/async eventually polling | `testing.eventually`, `eventually_async` | A2 | termination, interval positivity, timeout | fixed `timeout=NaN` non-termination class |
| ALG-030 | Manual clock / deterministic integer fuzz | `testkit.ManualClock`, `fuzz_integers` | A2 | monotonic clock, finite advance, integer generator bounds | hardened domains and overflow behavior |
| ALG-031 | Resource budgets | `limits.Limits`, `ResourceBudget` | A2 | byte/item/depth monotonic consumption, finite deadlines and injected clocks | fixed non-finite/bool domains and NaN-clock deadline poisoning |
| ALG-032 | Canonical JSON conversion | `serialization.to_jsonable`, `canonical_json` | A2 | deterministic mappings/sets, JSON compatibility, collision freedom | fixed normalized-key collision data loss |
| ALG-033 | Structured/content hashing parameters | `hashing.*` | A2 | deterministic digest, bounded reads, size domains | strict chunk/short-hash integer bounds added |
| ALG-034 | Chunk/batch/flatten iteration | `iteration.chunked`, `batched`, `flatten` | A2 | laziness, grouping, cycle rejection, depth bounds | strict integer/depth domains added |
| ALG-035 | Ring buffer / top-k bounds | `structures.RingBuffer`, `top_k` | A2 | capacity invariant, ordering, k bounds | strict integer bound validation added |
| ALG-036 | Recursive redaction | `redaction.redact`, `redact_dict` | A2 | secret-context propagation, non-mutation, reveal-count bound | strict reveal-count domain added |
| ALG-037 | Safe integer parsing | `parsing.safe_int` | A2 | strings/bytes/ordinary ints, base handling, bounds/fallback | fixed documented integer inputs returning fallback |
| ALG-038 | Generic async timeout wrapper | `async_utils.with_timeout` | A2 | None semantics, finite timeout, cancellation | finite timeout validation added |
| ALG-039 | Subprocess timeout/output validation | `subprocess.run_command`, `run_command_async` | A2 | structured argv, timeout/grace domains, output-size rejection | input domains hardened; output cap is post-capture, not memory-bound |
| ALG-040 | Upstream policy wrapper | `upstream_protocol.PolicyUpstream` | A2 | finite timeout, concurrency/attempt counts, idempotent retry set | parameter contracts hardened |
| ALG-041 | Scaling efficiency | `benchmark.metrics.scaling_efficiency` | A2 | valid baseline, per-point validity, ideal-scale formula | fixed invalid baseline producing nonsensical values |
| ALG-042 | Benchmark history trend | `benchmark.history.BenchmarkHistory.trend` | A2 | finite values, absolute/relative change, min/max | hardened unknown/non-finite metric handling |
| ALG-043 | Performance schema validation/migration | `benchmark.schema.*` | A2 | explicit version, shape requirements, deterministic migration | fixed `True == 1` schema-version acceptance |
| ALG-044 | Linux proc-stat parsing | `benchmark.process._parse_proc_stat` | A2 | exact field positions with spaces/parentheses in `comm` | fixed whitespace-split field corruption |
| ALG-045 | Process-tree sampling lifecycle | `benchmark.process.profile_command` | A2 | finite interval, descendant aggregation, cleanup on sampling failure | child cleanup added; short-lived descendants can still be missed |
| ALG-046 | Benchmark experiment matrix | `benchmark.experiment.run_experiment` | A2 | Cartesian combinations, repetition association/count | strict repetition domain added |
| ALG-047 | Project-root discovery/cache | `ext.project_stdlib`, `ext.project_gitpython` | A2 | ancestor search, cross-anchor cache correctness, optional sys.path injection | fixed cached root leakage and late-injection bug |
| ALG-048 | Deep nested data utilities | `dict_utils.deep_get`, `deep_set`, `deep_merge` | A2 | path validation, override semantics, list strategies, non-mutation of roots | existing evidence reviewed; nested value aliasing remains contract-sensitive |
| ALG-049 | Secure AES-GCM format/key derivation | `ext.secure_crypto` | A2 | explicit passphrase, PBKDF2/AES-GCM round trip, legacy rejection | existing security tests reviewed; malformed-length matrix still pending |
| ALG-050 | Encrypted credential store | `ext.secure_store.SecureStore` | A1 | key modes, authenticated decrypt, ACLs, audit log, file permissions | interface/tests reviewed; full transaction/concurrency sweep pending |
| ALG-051 | Stdlib runtime type checker | `ext.validation_stdlib.type_checked` | A1 | argument binding, unions, varargs/kwargs, no secret values in errors | reviewed; generic/container-depth parity remains limited |
| ALG-052 | Version migration | `versioning.*` | A1 | version validation, migration order, unsupported paths | implementation reviewed; dedicated proof packet still pending |
| ALG-053 | Plugin discovery/selection | `plugins.*` | A1 | deterministic discovery, isolation of broken plugins | implementation reviewed; differential/ordering tests need registry linkage |
| ALG-054 | Content-addressed storage | `content_store.ContentAddressedStore` | A1 | digest/path mapping, integrity verification, atomic publication | reviewed; fallback publication race/fault injection remains |
| ALG-055 | Atomic filesystem publication | `fs.*`, `io.*` atomic helpers | A1 | temp-file isolation, rename, cleanup, durability | reviewed; post-replace fsync failure semantics need explicit proof |
| ALG-056 | Core concurrency schedulers | `concurrency.*`, `pipeline.*` | A1 | task/queue bounds, ordering, cancellation cleanup | static review complete; adversarial race suite pending |
| ALG-057 | Signal/resource lifecycle | `signals.*`, `resources.*` | A1 | registration rollback, reverse cleanup, async cleanup | static review complete; fault-injection suite pending |

## Inventoried but not yet audited to A1

The following maintained algorithmic families are present in the complete
inventory but still require a dedicated proof packet. A0 is explicit so the
registry does not imply coverage that has not happened.

| Family | Main units | Level / next proof focus |
|---|---|---|
| Collections | `collections.unique/group_by/index_by/partition` | A0 — collision/order/property sweep |
| Formatting | byte/count magnitude and duration formatting | A0 — boundaries, rounding, negative values |
| Identifiers | deterministic and short IDs | A0 — collision representation and length domains |
| Configuration | recursive merge/environment override construction | A0 — precedence and aliasing |
| Security paths | `security.safe_path_join`, rooted open/name policy | A0 — symlink/TOCTOU matrix belongs with security audit |
| Fault injection | `faults.FailAfter`, `FaultSequence` | A0 — deterministic transition proof |
| Buffers | readonly/bounded buffer helpers and acceleration dispatch | A0 — aliasing/bounds/backend equivalence |
| Provenance manifests | runtime/environment capture and filtering | A0 — allowlist/determinism/secret-exclusion proof |
| Network | URI construction and reachability | A0 — IPv6/IDNA/delimiter/timeouts |
| Sync/mirror | rsync/mirror completion markers | A0 — partial-failure/publication proof |
| Benchmark artifacts | checksum registration/verification | A0 — mutation races/symlink semantics |
| Benchmark safe I/O | `benchmark.safe_io.load_result_checked` | A0 — TOCTOU, finite numeric fields, schema validation |
| Benchmark run directories | `save_run_directory` | A0 — collision and transactional publication |
| Benchmark perf integration | `perf_stat/record/script` | A0 — parser invalid values/event names/frequency domains |
| Benchmark worker protocol | `run_python_worker`, `worker_json` | A0 — finite timeout, malformed/oversized output |
| Benchmark reporting/export/plot | report/export aggregation | A0 — representation and invalid-data behavior |
| Benchmark overhead probe | `measure_runner_overhead` | A0 — zero timer and iteration domain |
| Optional Pydantic validation | validation adapter/backend equivalence | A0 — differential parity with stdlib backend |

## Resolved findings

### FIND-001 — overflow-prone variance arithmetic

Resolved for ALG-002/003 by replacing hand-written squared-deviation variance
with `statistics.stdev` and adding extreme-finite regressions. Pairwise
subtraction and final interval representability are checked explicitly.

### FIND-002 — token bucket accepted non-finite values

Resolved for ALG-014. Rates, capacities, requests and timeout values now reject
NaN/infinity/bools before internal state can be poisoned.

### FIND-003 — benchmark numerical configuration under-validation

Resolved across ALG-015-020/041-043/046 for the reviewed paths. Calibration,
stability, comparison, regression-policy, history/trend and repetition domains
now fail explicitly on invalid numerical configuration.

### FIND-004 — retry/cache/resilience/deadline NaN semantics

Resolved for reviewed timing paths. Most importantly,
`eventually(timeout=NaN)` can no longer create a non-expiring NaN deadline. Resource budgets also validate injected clock readings, and retry backoff caps huge exponents without overflowing the intermediate.

### FIND-005 — canonical mapping-key collision

Resolved for ALG-032. Distinct Python mapping keys that normalize to the same
JSON string key now raise rather than silently overwriting one another, which
also protects structured-hash/cache-key semantics.

### FIND-006 — `safe_int` violated its documented integer-input contract

Resolved for ALG-037. Ordinary integer inputs no longer go through
`int(value, base)`, which previously rejected them and returned the fallback.

### FIND-007 — Linux proc-stat parser corrupted fields for spaced commands

Resolved for ALG-044/045. `/proc/<pid>/stat` is parsed using the parenthesized
command boundary rather than generic whitespace splitting.

### FIND-008 — project-root cache ignored anchor and injection intent

Resolved for ALG-047. A cached root is reused only for anchors within that root,
and a later request for `sys.path` injection is honored.

## Open limitations / proof gaps

### GAP-001 — subprocess output limit is not a resident-memory bound

ALG-039 checks captured stdout/stderr after `subprocess.run`/communication.
It rejects oversized results but cannot prevent the capture itself from
consuming more than `max_output_bytes`. A streaming bounded-capture redesign is
required if this API is intended as a memory-safety boundary.

### GAP-002 — recursive graph depth

ALG-009/011 use recursive traversal. Correctness is covered for ordinary graphs,
but maximum safe depth is bounded by Python recursion limits. An iterative
implementation should be considered for untrusted/deep DAGs.

### GAP-003 — process profiler observation is sampled, not event-complete

ALG-045 can miss descendants that fork and exit between snapshots. Reports
should be understood as sampled observations; exact accounting requires a
different OS mechanism.

### GAP-004 — run-directory packaging is non-transactional

`benchmark.run_directory.save_run_directory` may leave a partially populated
directory if an artifact copy or final write fails. Decide whether transactional
publication is part of the public contract.

### GAP-005 — filesystem durability failure after replace

Atomic helpers can publish the new target before a subsequent directory-fsync
failure is reported. This is a standard durability distinction but must be
covered by an explicit failure-atomicity contract and injected tests.

### GAP-006 — content-store fallback publication

The normal hard-link publication path is concurrency-friendly; the fallback
replace path still needs an adversarial concurrent-publication/fault-injection
proof.

### GAP-007 — benchmark safe-I/O model validation

The checked loader bounds file size before reading but still needs a full schema
and finite-numeric validation pass, including mutation/TOCTOU considerations.

### GAP-008 — optional/security backend completeness

SecureStore and optional validation backends have meaningful existing tests,
but this branch has not yet completed every internal transaction/concurrency and
cross-backend differential proof.

## Completion rule

The long-horizon repository-wide algorithm audit is complete only when:

1. no A0 family remains without either an A1 proof packet or an explicitly
   accepted exclusion;
2. every A1/A2 proof gap is resolved or documented as a deliberate limitation;
3. high-risk numerical, graph, binary, concurrency and state-machine families
   reach A4;
4. every discovered correctness defect has a regression test;
5. `./scripts/verify.sh` passes on the final branch state;
6. this registry is updated with the final audited commit and execution evidence.
