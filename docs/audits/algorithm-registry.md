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
- **A4** — A3 plus the canonical aggregate verification gate passes on the same revision, locally or in hosted CI.

Execution evidence is recorded per audited revision. Hosted CI run
`36382828055` passed the canonical aggregate verifier on
`f55c510e014cf0233fd18f279808d3e9b22caf4a`: release, Ruff/mypy, 864 Python 3.11 tests, strict docs,
all packaging/isolation cases, and 864 Python 3.12 tests.

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
| ALG-009 | Workflow topological order | `dag.WorkflowDAG._topological_order` | A4 | dependency-before-consumer, missing dependency, cycles; exhaustive four-node directed-graph test against independent Kahn oracle | exhaustive proof executed in CI; recursion depth remains a limitation |
| ALG-010 | Effective transitive fingerprint | `dag.WorkflowDAG.effective_fingerprint` | A2 | dependency sensitivity, propagation, cache invalidation | reviewed; no defect found |
| ALG-011 | Provenance DAG cycle/ancestor traversal | `provenance_graph.ProvenanceGraph` | A2 | cycle rollback, unresolved nodes, deterministic ancestors | reviewed; recursion depth is a limitation |
| ALG-012 | Unsigned 64-bit canonical varint | `binary.encode_uvarint`, `ByteReader.read_uvarint` | A4 | exhaustive 0..65535 reference/round trip, uint64 boundaries, canonical form, malformed/truncation rollback | exhaustive/reference proof executed in CI |
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
| ALG-058 | Collection transforms | `collections.unique/group_by/index_by/partition` | A4 | stable order, duplicate semantics, unhashable values, key-derived collisions | focused proof suite executed successfully |
| ALG-059 | Human-readable formatting | `formatting.*` | A4 | SI/IEC boundaries, duration decomposition, precision domain, non-finite/bool rejection, huge integer counts | domain coercion hardened and executed |
| ALG-060 | Deterministic/short identifiers | `identifiers.*` | A4 | determinism, prefix consistency, string contracts, length bounds and bool rejection | parameter contracts hardened and executed |
| ALG-061 | Layered configuration construction | `config.merge_configs`, `env_overrides` | A4 | recursive precedence, caller non-mutation, prefix/separator/path-segment validity | malformed override paths now fail explicitly |
| ALG-062 | Security path containment/open | `security.safe_path_join`, `open_path_under_base`, `NameAccessPolicy` | A4 | parent escape rejection, deny precedence, POSIX final-component no-follow | fixed final-symlink contract; broader parent-component race remains platform-dependent |
| ALG-063 | Deterministic fault injection | `faults.FailAfter`, `FaultSequence` | A4 | exact one-based transitions, configured failure indices, call accounting | focused transition proof executed |
| ALG-064 | Read-only buffers/backend dispatch | `buffers.as_readonly_view`, `dispatch` | A4 | zero-copy aliasing, read-only enforcement, exact backend selection | focused aliasing/dispatch proof executed |
| ALG-065 | Provenance manifests | `provenance.*` | A4 | allowlisted environment, copied/frozen caller mappings, identifier/version domains | immutability and allowlist evidence executed |
| ALG-066 | URI construction/TCP reachability | `network.*` | A4 | IPv6 brackets, IDNA, user-info escaping, ports, finite timeout | non-finite timeout hole fixed and executed |
| ALG-067 | Rsync mirror completion protocol | `sync.rsync_mirror` | A4 | source normalization, destructive-argument rejection, success-only completion marker | success/failure publication proof executed |
| ALG-068 | Benchmark artifact registry | `benchmark.artifacts.*` | A4 | checksum/tamper detection, regular-file identity, symlink rejection | symlink artifacts now rejected |
| ALG-069 | Checked benchmark result loading | `benchmark.safe_io.load_result_checked` | A4 | bounded read, required structure, finite samples/stats, integer/schema domains | loader now bounds actual bytes read and validates persisted fields |
| ALG-070 | Benchmark run-directory publication | `benchmark.run_directory.save_run_directory` | A4 | artifact-name collision handling, copied checksum validity, run metadata | collision proof executed; transactional publication remains GAP-004 |
| ALG-071 | Linux perf integration | `benchmark.perf.*` | A4 | event/frequency domains, unavailable counters, non-finite parser values | invalid domains/non-finite counters hardened |
| ALG-072 | Benchmark worker protocol | `benchmark.worker.*` | A4 | module/interpreter/timeout domains, failure propagation, strict JSON | strict JSON and timing domains proven; captured output remains unbounded |
| ALG-073 | Benchmark reporting/export/plot transforms | `benchmark.report/export/plot` | A4 | profile representation, CSV export, CPU-core transform, invalid metric rejection, real plot smoke | proof and isolated matplotlib smoke executed |
| ALG-074 | Benchmark overhead probe | `benchmark.overhead.measure_runner_overhead` | A4 | positive integer iterations, bool rejection, zero timer-resolution semantics | focused proof executed |
| ALG-075 | Optional Pydantic validation adapter | `ext.validation_pydantic.type_checked` | A4 | valid scalar behavior, strict-int differential parity, redacted validation errors | strict-mode differential proof executed; default Pydantic coercion remains intentional backend behavior |

## A0 sweep result

The initial A0 backlog is cleared. Families ALG-058 through ALG-075 were
reviewed, given focused proof tests, and executed successfully in hosted
aggregate CI run `36382828055` on `f55c510e014cf0233fd18f279808d3e9b22caf4a`.

A green A4 execution level does not erase explicitly documented limitations.
GAP-004 and the worker/process/resource gaps below remain active where the
public contract is narrower than a stronger transactional or memory-bound
guarantee.

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

### FIND-009 — rooted open erased the final symlink before O_NOFOLLOW

Resolved for ALG-062. `open_path_under_base` previously used the resolved path
for the POSIX open, so a final in-base symlink had already disappeared before
`O_NOFOLLOW` could reject it. The containment check still resolves the target,
but the descriptor-relative open now preserves the caller's final component.

### FIND-010 — A0 parameter-domain coercion

Resolved across ALG-059-061/066/071-072/074. Formatting, identifier,
configuration, TCP, perf, worker, and overhead APIs now reject invalid bool,
non-finite, empty, or malformed parameter values before work starts.

### FIND-011 — checked benchmark loader trusted persisted numeric structure

Resolved for ALG-069. The loader now performs a bounded binary read and validates
sample finiteness, count/schema integer domains, statistics, system metadata, and
parameter structure before constructing the result.

### FIND-012 — performance artifacts followed symlinks

Resolved for ALG-068. Artifact registration and verification now reject symlinks
instead of treating a symlink to a regular file as the registered file identity.

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

### GAP-007 — benchmark worker output is not memory bounded

ALG-072 uses `subprocess.run(..., capture_output=True)`. Its timeout and JSON
protocol are audited, but stdout/stderr have no streaming byte cap. Add a
bounded-capture protocol if worker output can be untrusted or arbitrarily large.

### GAP-008 — SecureStore backend completeness

SecureStore has meaningful existing tests, but this branch has not yet completed
every internal transaction/concurrency and malformed-format proof. The optional
Pydantic validation adapter itself is now covered by ALG-075.

## Completion rule

The long-horizon repository-wide algorithm audit is complete only when:

1. no A0 family remains without either an A1 proof packet or an explicitly
   accepted exclusion;
2. every A1/A2 proof gap is resolved or documented as a deliberate limitation;
3. high-risk numerical, graph, binary, concurrency and state-machine families
   reach A4;
4. every discovered correctness defect has a regression test;
5. the canonical aggregate verifier passes on the audited code revision;
6. this registry is updated with the final audited commit and execution evidence.
