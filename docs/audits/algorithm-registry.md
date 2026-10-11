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

The former A1 sweep is independently verified by hosted CI run
`36389874370` on `dc243517c01f9f9b2836df0dfb4570fa1519906f`: release, Ruff/mypy, 943 Python 3.11
tests, strict docs, all packaging/isolation cases, and 943 Python 3.12 tests.

## Integration verification status

The algorithm-audit history is composed onto security-hardened
`main@07244be5e6d24d83b3b7dcde62bc1702ff1f6e9d` on
`merge/algorithm-audit-main`.

The combined implementation was verified on
`416c1105404fa42f499f323fead8872644848103` by hosted CI run `36403271808`. Release preflight, Ruff,
mypy, strict documentation, packaging/isolation, 991 Python 3.11 tests, and 991
Python 3.12 tests all passed. Previously audited A4 families whose implementations
were recomposed during integration are therefore revalidated on this integrated
revision.

The integrated tree deliberately keeps newer `main` security behavior
(immutable CI action pins, dependency floors, bounded subprocess capture,
filesystem/file-identity hardening, diagnostic redaction, and crypto downgrade
protection) while layering the algorithm-audit contracts and proof suites on
top.

## CI/runtime follow-up — 2026-10-09

The [focused follow-up record](2026-10-09-ci-runtime-followup.md) starts from
`fix/ci-rate-limiter-clock@a44731baaa04ad81394feae3f8edd16e01043aaa` and records
retry callback/deadline corrections, exact token-capacity validation, procfs
identity checks, process-group cleanup, and truthful memory observations.
Focused proof suites passed on Python 3.11.17 and 3.12.14. The affected families
below are recorded at A3; older A4 evidence for other families is not a claim that
this scoped review re-audited the entire repository.

## Audited algorithm set

### Cross-process follow-up on 3f474ad

[The process proof program](../tasks/done/2026-10-08-storage-process-proofs.md)
adds bounded acknowledged spawn-process schedules on Python 3.11/3.12. SP-01
has 12 passing CAS cases; SP-02 has 10 passing real-flock/SQLite coordination
cases. SP-03 now passes all 26 strict crash cases after the approved mode-switch
recovery repair. SP-04 adds ten ordinary rejected-authentication and cleanup/fsync
failure regressions. Full canonical verification passed all six gates on both
interpreters; the completed parent records the actual source-input fingerprint.

The confirmed SP-04 recovery defect leaves obsolete opposite-mode primary key/
salt material after current-candidate unlock; the leftover salt blocks future
file-mode rotation. After the user authorized the concrete patch, authenticated
normal-candidate recovery now completes opposite-primary cleanup. Unchanged strict
crash tests and the complete aggregate gate now pass on both Python versions. Wrong credentials
and damaged policy preserve current/pending bytes in the executed proof packet.
Historical A4 rows below do not certify these new schedules by themselves.

### 2026-10-08 follow-up status

The [follow-up task hierarchy](../tasks/done/2026-10-08-audit-follow-up.md)
reviews `80bde76a641ce4577574fde60ec957251aee2ba0` plus the dirty working tree on
`audit/follow-up-20261008`. AU-01 through AU-06 are complete initial reviews;
reproduced source defects and verification/documentation gaps produced AR-01
through AR-11. Historical A4 rows below retain evidence for their original
revision; they do not certify this new working tree.

| Families | Current repair/proof packet |
|---|---|
| ALG-022 / ALG-056 | Rejected heartbeat coroutine closure, partial pipeline setup cleanup, terminal child cancellation and shielded owned-task draining |
| ALG-039 | Synchronous bounded-capture deadline includes inherited-pipe draining; POSIX readers can stop without waiting for escaped descendants |
| ALG-050 | Authenticated strict/legacy record policy, explicit trusted legacy upgrade, durable-generation reconciliation after failed rotation cleanup |
| ALG-054 | Descriptor-relative fanout operations, opened-source verification/copy, reserved staging descriptors, strict ASCII digest domain |
| ALG-055 | Atomic-write setup descriptor closure and atomic directory no-replace publication on supported OS/filesystem combinations |
| ALG-066 / ALG-067 | URI authority validation after IDNA normalization and finite sync timeout rejection before marker mutation |
| ALG-012 / ALG-076 / ALG-077 | Native recursion protection and integer-subclass fallback parity; compiled-present and forced-absent execution required by test gate |
| Package/CI contracts | Both distribution formats installed and checked outside checkout; wheel rebuilt from extracted sdist; native support inventoried and activation checked |

Focused repair evidence is recorded in each AR task. The final pinned aggregate
verifier passed all six gates on both supported interpreters; the execution-tree
fingerprint and counts are recorded in the completed parent task. This status
table does not blanket-promote historical A4 levels.

Residual contracts remain explicit: root/ancestor trust and mutable returned
Paths, mutable-parent final-name substitution detected after publication with a
potential substituted final entry left on failure, non-POSIX path guarantees,
Windows descendant-pipe reader lifetime, whole-store authenticated snapshot
rollback freshness, recursive deep graphs, non-transactional benchmark run
directories, sampled process-tree observations, and caller-owned input budgets.

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
| ALG-014 | Async token bucket | `rate_limit.AsyncRateLimiter` | A3 | balance in [0, capacity], exact integer capacity comparison, normalized request arithmetic, timeout, representable finite parameters; `test_deadline_regressions.py` | fixed large-integer validation/zero-delay loops and conversion-overflow handling; both interpreters passed |
| ALG-015 | Benchmark loop calibration | `benchmark.runner.calibrate_loops` | A2 | monotonic loop growth, target/max bounds | fixed non-finite target and invalid max-loop domains |
| ALG-016 | Benchmark sampling/stat summary | `benchmark.runner.benchmark` | A2 | iteration bounds, min-time semantics, finite config, percentile summary | configuration hardened; focused execution pending |
| ALG-017 | Regression metric policy | `benchmark.policy.MetricPolicy`, `evaluate_metric` | A2 | valid direction, finite metrics, non-negative thresholds | fixed invalid direction/NaN/negative policy acceptance |
| ALG-018 | Multi-metric regression gate | `benchmark.gate.evaluate_regression_gate` | A2 | required metrics, policy aggregation, comparability warnings | inherits hardened policy validation |
| ALG-019 | Benchmark history trend summary | `benchmark.trends.summarize_history` | A2 | OLS slope, moving median, finite metric values, baseline window | hardened domains and unknown-metric errors |
| ALG-020 | Stability diagnostics | `benchmark.diagnostics.analyze_stability` | A2 | CV/range/outlier diagnostics, finite non-negative samples/thresholds | fixed invalid config appearing stable |
| ALG-021 | Retry backoff / deadline policy | `retry.RetryPolicy`, retry runners | A3 | bounded attempts, callback/predicate time accounting, exact deadline, finite delays/timeouts, overflow-safe cap; `test_deadline_regressions.py` | corrected all six callback-budget and deadline paths; invalid huge integers fail before work; both interpreters passed |
| ALG-022 | Renewable lease heartbeat race | `leases.run_with_lease_heartbeat` | A4 | lease-loss precedence, cleanup, cancellation, Awaitable support, setup-failure cleanup | setup/race proofs executed successfully in aggregate CI; rejected-coroutine cleanup evidence in AR-06 |
| ALG-023 | Bounded/digest streaming writes | `streaming.BoundedWriter`, `DigestWriter`, `copy_and_hash` | A4 | partial-write progress, committed-byte accounting, byte limits, strict JSONL constants | partial-write/failure and strict-JSONL proofs executed successfully |
| ALG-024 | Partition overlap detection | `partitions.partition_overlaps`, `PartitionManifest` | A4 | deterministic pair order, overlap oracle, immutable manifest, invalid-shape handling | exhaustive small-domain overlap proof executed successfully |
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
| ALG-039 | Subprocess timeout/output validation | `subprocess.run_command`, `run_command_async` | A4 | structured argv, finite timeout/grace domains, streaming output cap, exit/drain deadline, owned cleanup | historical composed-tree proof; AR-08 sync and NP-04 async deadline proofs; actual Windows/macOS and final OS reap limits remain |
| ALG-040 | Upstream policy wrapper | `upstream_protocol.PolicyUpstream` | A2 | finite timeout, concurrency/attempt counts, idempotent retry set | parameter contracts hardened |
| ALG-041 | Scaling efficiency | `benchmark.metrics.scaling_efficiency` | A2 | valid baseline, per-point validity, ideal-scale formula | fixed invalid baseline producing nonsensical values |
| ALG-042 | Benchmark history trend | `benchmark.history.BenchmarkHistory.trend` | A2 | finite values, absolute/relative change, min/max | hardened unknown/non-finite metric handling |
| ALG-043 | Performance schema validation/migration | `benchmark.schema.*` | A2 | explicit version, shape requirements, deterministic migration | fixed `True == 1` schema-version acceptance |
| ALG-044 | Linux proc-stat parsing | `benchmark.process._parse_proc_stat` | A3 | exact fields with spaces/parentheses/non-UTF-8 command bytes, matching procfs identity; `test_process_profile_regressions.py` | preserved arbitrary command bytes and rejected foreign PID namespaces; deterministic proofs passed |
| ALG-045 | Process-tree sampling lifecycle | `benchmark.process.profile_command` | A3 | prelaunch capability validation, PID/start-time lifetime identity, cumulative observed monotonic counters, known/unknown memory, owned group cleanup, bounded reap and original failure preservation | exited observed children and PID reuse are now accounted across samples; deterministic regressions passed in focused reconstructed execution; event-incomplete sampling remains GAP-003 |
| ALG-046 | Benchmark experiment matrix | `benchmark.experiment.run_experiment` | A2 | Cartesian combinations, repetition association/count | strict repetition domain added |
| ALG-047 | Project-root discovery/cache | `ext.project_stdlib`, `ext.project_gitpython` | A2 | ancestor search, cross-anchor cache correctness, optional sys.path injection | fixed cached root leakage and late-injection bug |
| ALG-048 | Deep nested data utilities | `dict_utils.deep_get`, `deep_set`, `deep_merge` | A2 | path validation, override semantics, list strategies, non-mutation of roots | existing evidence reviewed; nested value aliasing remains contract-sensitive |
| ALG-049 | Secure AES-GCM format/key derivation | `ext.secure_crypto` | A2 | explicit passphrase, PBKDF2/AES-GCM round trip, legacy rejection | existing security tests reviewed; malformed-length matrix still pending |
| ALG-050 | Encrypted credential store | `ext.secure_store.SecureStore` | A4 | key modes, authenticated decrypt, ACLs, mutation/audit atomicity, threaded serialization, rotation recovery | historical isolation had 42 tests; current authenticated policy/rotation recovery evidence in AR-04 |
| ALG-051 | Stdlib runtime type checker | `ext.validation_stdlib.type_checked` | A4 | argument binding, PEP 604 unions, recursive containers, literals/Annotated, varargs/kwargs, redacted errors | recursive/type-boundary proofs executed; stdlib isolation had 18 passing tests |
| ALG-052 | Version migration | `versioning.*` | A4 | version/envelope validation, one-step migration order, missing/downgrade paths, failure stop | focused migration/failure-boundary proof executed successfully |
| ALG-053 | Plugin discovery/selection | `plugins.*` | A4 | deterministic ordering, sibling failure isolation, instantiation errors, process-control propagation | focused discovery/isolation proof executed successfully |
| ALG-054 | Content-addressed storage | `content_store.ContentAddressedStore` | A4 | digest/path mapping, integrity verification, symlinked fanout rejection, serialized fallback publication, materialization domains | anchored copy/publication evidence in AR-01; adversarial path/fallback proofs plus deterministic concurrent-writer fallback regression; cooperating writers share a symlink-safe advisory publication lock |
| ALG-055 | Atomic filesystem publication | `fs.*`, `io.*` atomic helpers | A4 | temp isolation, replace failure cleanup, directory publication, no-overwrite symlinks, explicit pre/post-replace durability semantics | no-replace/descriptor cleanup in AR-02/03; injected tests prove pre-replace fsync failure preserves the old target and post-replace directory-fsync failure may leave the new target visible while raising |
| ALG-056 | Core concurrency schedulers | `concurrency.*`, `pipeline.*` | A4 | task/queue bounds, initial-scheduling cleanup, ordering, worker-failure cancellation | adversarial setup/cancellation/worker-bound proofs executed successfully; lifecycle regressions in AR-05 |
| ALG-057 | Signal/resource lifecycle | `signals.*`, `resources.*` | A4 | partial registration rollback, idempotent restore, reverse sync/async cleanup | lifecycle/failure proofs executed successfully |
| ALG-058 | Collection transforms | `collections.unique/group_by/index_by/partition` | A4 | stable order, duplicate semantics, unhashable values, key-derived collisions | focused proof suite executed successfully |
| ALG-059 | Human-readable formatting | `formatting.*` | A4 | SI/IEC boundaries, duration decomposition, precision domain, non-finite/bool rejection, huge integer counts | domain coercion hardened and executed |
| ALG-060 | Deterministic/short identifiers | `identifiers.*` | A4 | determinism, prefix consistency, string contracts, length bounds and bool rejection | parameter contracts hardened and executed |
| ALG-061 | Layered configuration construction | `config.merge_configs`, `env_overrides` | A4 | recursive precedence, caller non-mutation, prefix/separator/path-segment validity | malformed override paths now fail explicitly |
| ALG-062 | Security path containment/open | `security.safe_path_join`, `open_path_under_base`, `NameAccessPolicy` | A4 | parent escape rejection, deny precedence, POSIX final-component no-follow | fixed final-symlink contract; broader parent-component race remains platform-dependent |
| ALG-063 | Deterministic fault injection | `faults.FailAfter`, `FaultSequence` | A4 | exact one-based transitions, configured failure indices, call accounting | focused transition proof executed |
| ALG-064 | Read-only buffers/backend dispatch | `buffers.as_readonly_view`, `dispatch` | A4 | zero-copy aliasing, read-only enforcement, exact backend selection | focused aliasing/dispatch proof executed |
| ALG-065 | Provenance manifests | `provenance.*` | A4 | allowlisted environment, copied/frozen caller mappings, identifier/version domains | immutability and allowlist evidence executed |
| ALG-066 | URI construction/TCP reachability | `network.*` | A4 | IPv6 brackets, IDNA, user-info escaping, ports, finite timeout | historical timing proof; post-IDNA authority validation evidence in AR-07 |
| ALG-067 | Rsync mirror completion protocol | `sync.rsync_mirror` | A4 | source normalization, destructive-argument rejection, success-only completion marker | historical publication proof; invalid timeout preserves marker before rejection in AR-09 |
| ALG-068 | Benchmark artifact registry | `benchmark.artifacts.*` | A4 | checksum/tamper detection, regular-file identity, symlink rejection | symlink artifacts now rejected |
| ALG-069 | Checked benchmark result loading | `benchmark.safe_io.load_result_checked` | A4 | bounded read, required structure, finite samples/stats, integer/schema domains | loader now bounds actual bytes read and validates persisted fields |
| ALG-070 | Benchmark run-directory publication | `benchmark.run_directory.save_run_directory` | A4 | artifact-name collision handling, copied checksum validity, run metadata, rollback of files created by a failed publication | collision proof plus rollback regressions cover later-copy failure, pre-existing artifacts, and cleanup-error precedence; older unreferenced artifacts are not garbage-collected |
| ALG-071 | Linux perf integration | `benchmark.perf.*` | A4 | event/frequency domains, unavailable counters, non-finite parser values | invalid domains/non-finite counters hardened |
| ALG-072 | Benchmark worker protocol | `benchmark.worker.*` | A4 | module/interpreter/timeout domains, failure propagation, strict JSON, bounded capture | integrated bounded worker capture and redacted diagnostics passed on the composed tree |
| ALG-073 | Benchmark reporting/export/plot transforms | `benchmark.report/export/plot` | A4 | profile representation, CSV export, CPU-core transform, invalid metric rejection, real plot smoke | proof and isolated matplotlib smoke executed |
| ALG-074 | Benchmark overhead probe | `benchmark.overhead.measure_runner_overhead` | A4 | positive integer iterations, bool rejection, zero timer-resolution semantics | focused proof executed |
| ALG-075 | Optional Pydantic validation adapter | `ext.validation_pydantic.type_checked` | A4 | valid scalar behavior, strict-int differential parity, redacted validation errors | strict-mode differential proof executed; default Pydantic coercion remains intentional backend behavior |
| ALG-076 | Native 64-bit varint codec & zero-copy parsing | `binary.encode_uvarint`, `binary.ByteReader.read_uvarint`, `_accel.*` | A4 | 64-bit uint range `[0, 2^64-1]`, canonical MSB continuation, rejection of non-canonical redundant zero bytes and overflow, zero-copy buffer view, pure-Python fallback parity | historical 28-test packet; non-exact integer semantics and active/fallback verification in AR-10/11 |
| ALG-077 | Fast JSON-clean validation & allocation bypass | `serialization.to_jsonable`, `streaming.write_jsonl`, `_accel.is_json_clean` | A4 | depth bounding (`max_depth=100`), strict byte rejection, finite float bounds, chunked streaming I/O batching, pure-Python fallback | historical roundtrip packet; interpreter-independent native depth safety and active/fallback verification in AR-10/11 |
| ALG-078 | Adversarial chaos and stream/await fault injection | `faults.VirtualClock`, `faults.FaultyStream`, `faults.AwaitBoundaryChaos` | A4 | deterministic monotonic clock progression, partial read/write truncation, EIO/ENOSPC injection, cooperative await cancellation | 5 focused unit and contract tests executed |
| ALG-079 | SingleFlight producer resource ownership | `cache.SingleFlight.run` | A3 | shared producer lifetime, waiter cancellation, registry release after completion, rejected coroutine submission closure | RS-01/RP-02 bounded lifetime and cache proofs pass on both Python versions; broader family guarantees are not inferred from this ownership packet |


## A0 sweep result

The initial A0 backlog is cleared. Families ALG-058 through ALG-075 were
reviewed, given focused proof tests, and executed successfully in hosted
aggregate CI run `36382828055` on `f55c510e014cf0233fd18f279808d3e9b22caf4a`.

A green A4 execution level does not erase explicitly documented limitations.
The remaining gaps below record contracts that are intentionally narrower than
stronger recursive-depth, event-complete sampling, or backend-completeness
guarantees.

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

### FIND-013 — lease/concurrency setup escaped cleanup scope

Resolved for ALG-022/056. Initial task creation now occurs inside the same
cleanup scope as steady-state execution, and the lease helper accepts the full
Awaitable contract rather than only coroutine objects.

### FIND-014 — JSONL accepted non-standard NaN/infinity constants

Resolved for ALG-023. Streaming JSON Lines now rejects non-standard numeric
constants on both encode and decode, matching the repository's strict JSON
semantics.

### FIND-015 — stdlib validator did not enforce documented PEP 604/container types

Resolved for ALG-051. The stdlib backend now handles PEP 604 unions, recursive
list/dict/tuple/set/frozenset element types, Literal, Annotated base types, and
Callable outer types. Backend-specific decorator options are rejected rather
than silently ignored.

### FIND-016 — SecureStore mutation and success audit could commit separately

Resolved for ALG-050. Individual and bulk secret mutations now couple successful
audit events to the same SQLite transaction. Bulk failures roll back all secret
changes and persist one post-rollback batch-denial event when possible.

### FIND-017 — content-store fanout ancestors could be symlinked

Resolved for ALG-054. Store roots and every digest fanout ancestor are checked
for symlinks before publication/access, preventing a malicious prefix directory
from redirecting a content path outside the intended store tree.

### FIND-018 — transactional directory could replace a dangling symlink target

Resolved for ALG-055. Publication treats both existing filesystem entries and
dangling symlinks as occupied targets, preserving the advertised no-overwrite
behavior.

### FIND-019 — subprocess output bound became a true streaming cap

Resolved for ALG-039 by integrating the newer `main` bounded-capture
implementation with the audit timing contracts. Overflow terminates the process
group promptly instead of buffering arbitrary output before checking the limit.
The combined behavior passed hosted run `36403271808`.

### FIND-020 — benchmark worker inherited bounded subprocess capture

Resolved for ALG-072. Benchmark workers now use the bounded subprocess path
while retaining strict JSON, finite timeout validation, and diagnostic
redaction. The combined worker/package proofs passed hosted run
`36403271808`.

### FIND-021 — process profile totals lost exited child counters

Resolved for ALG-045. Final CPU, I/O, fault, and context-switch totals no longer
use the maximum simultaneous aggregate snapshot. The profiler keeps a private
ledger keyed by Linux `(pid, start_time_ticks)` and retains the greatest observed
monotonic counter values for each process lifetime. Observed children therefore
remain represented after exit, while numeric PID reuse is treated as a distinct
lifetime. The public profile/sample schema is unchanged. Deterministic regressions
cover exited children and reused PIDs. Exact event-complete accounting remains
outside the sampled profiler contract under GAP-003.

### FIND-022 — failed run-directory publication left partial artifacts

Resolved for ALG-070. `save_run_directory` now records artifacts created by the
current call and removes them if a later copy, registration, or manifest write
fails. It removes newly created empty directories when possible while preserving
pre-existing files/directories. Cleanup failures are added as type-only exception
notes and do not replace the initiating error. `_copy_regular_source` applies the
same rule when cleanup of a partially copied target fails. Existing unreferenced
artifacts from earlier successful publications remain outside this rollback
contract.

### FIND-023 — durability failure semantics were under-specified in the registry

Resolved for ALG-055 without changing runtime behavior. Existing injected tests
prove both sides of the durability boundary: file `fsync` failure before replace
preserves the old target, while parent-directory `fsync` failure after replace
raises after the new target has become visible. The latter is a durability
uncertainty, not a claim of rollback atomicity.

### FIND-024 — content-store fallback could overwrite a cooperating winner

Resolved for ALG-054. All cooperating publishers now take a symlink-safe advisory
lock in the target fanout directory before checking or publishing a digest path.
The normal hard-link path and the hard-link-failure `os.replace` fallback share
that critical section. A deterministic two-writer regression forces fallback and
proves that the second writer waits, verifies the first writer's target, and does
not execute another replacement. The contract does not protect against unrelated
processes that deliberately ignore the advisory lock.

## Open limitations / proof gaps

### GAP-002 — recursive graph depth

ALG-009/011 use recursive traversal. Correctness is covered for ordinary graphs,
but maximum safe depth is bounded by Python recursion limits. An iterative
implementation should be considered for untrusted/deep DAGs.

### GAP-003 — process profiler observation is sampled, not event-complete

ALG-045 can miss descendants that fork and exit between snapshots. Reports
should be understood as sampled observations; exact accounting requires a
different OS mechanism.


### GAP-008 — SecureStore backend completeness

Current SecureStore transaction/policy/recovery regressions and existing AES
malformed salt/hex cases are recorded in AU-02 and AR-04. Remaining proof work
now includes broader multiprocess/platform schedules beyond the passing
SP-01 through SP-04 packets and fixed key/salt read/decode budgets. RS-02 now
adds independent OpenSSL AES/PBKDF/component and bounded lifetime evidence;
RP-01 preserves those proofs alongside repaired authentication/recovery cases.
Do not continue to classify the independent known-answer/component matrix as
wholly absent; its exact scope and limitations are in the RS-02 record.
Do not describe malformed-format coverage as wholly absent. The optional
Pydantic validation adapter itself is covered by ALG-075.

### GAP-010 — actual Windows/macOS execution

[Native platform tasks](../tasks/active/2026-10-08-platform-verification.md)
separate Linux preparation and mocked dispatch evidence from real Windows/macOS
kernel, filesystem, lock, process and compiler execution. Native verification
requires both Python 3.11 and 3.12 and explicit accounting for skipped coverage.
No native host has been confirmed; no audit level is promoted by preparation.
The portable verifier's stable Linux preparation report records both interpreters,
unchanged source fingerprints and 18 filesystem/46 SecureStore/20 subprocess/
35 fallback/57 compiled-native passes per interpreter, with 22 explicitly
native-only fallback exclusions. Its native-platform completion flag remains
false. See NP-03 for commands and local JSON/JUnit provenance.
The integrated follow-up report supersedes the original 20 subprocess cases with
34, including the repaired async drain proofs; it again records stable source
and zero unexplained skips. All six canonical integration gates pass, with
1,370 full-suite passes/29 skips and 57 compiled-native passes per Python version.

ALG-039's async drain concern was reproduced by two independently bounded
controlled-process/StreamReader cases before repair. The implementation now
applies one deadline across exit and drain, wakes on overflow/read failure, and
cancels/joins owned tasks and closes owned capture transports before reaping.
[NP-04](../tasks/active/2026-10-08-platform-async-drain.md) records 92 focused
passes plus 14 subtests on each supported Python version, including a finite
real-child cleanup probe. Combined integration verification passed all six gates. The
CPython private StreamReader transport dependency, final OS reap and escaped
descendant ownership remain explicit limits; real Windows/macOS proof is pending.

### 2026-10-08 resource/security repair follow-up

[RS-01 through RS-03](../tasks/done/2026-10-08-resource-security-audit.md)
reproduced six resource cleanup regressions, four SecureStore authentication/
recovery regressions and two native/reference depth-budget parity cases before
source repair. The user authorized [RP-01 through RP-03](../tasks/done/2026-10-08-resource-security-repairs.md).

- ALG-025/056/079: rejected consumed/generated coroutines close before ownership
  publication; owned scheduler children drain through repeated cancellation,
  retaining initiating failures and cooperative descriptor cleanup. Positive
  weakref/cache/task/fd checks remain strict. Focused proof: 101 passes plus seven
  subtests per supported Python version.
- ALG-050: guarded mutations authenticate current policy and numeric generation
  inside SQLite write exclusion; raw-writer interleavings are tested for owned
  and joined transactions. Missing material cannot initialize a database with
  prior metadata/secrets/audit history; format-invalid primary file keys do not
  hide independently valid pending recovery. Unsafe-file errors still propagate.
  Focused proof: 160 secure tests pass per version. This does not authenticate a
  whole old snapshot's freshness or promise arbitrary concurrent hostile-root safety.
- ALG-077: Python depth rejection precedes acceleration, and only the native
  optimization budget is capped at 129, beyond its existing depth128 fallback
  boundary. Caller recursion budgets and reference values/errors remain intact.
  Both native matrices pass 91 tests; fallback passes 60 with 31 exact native-only
  exclusions. Finite C buffer/refcount/weakref/allocation probes found no additional
  leak; they do not prove all allocations or arbitrarily long workloads safe.

Coordinator integration passed all six canonical gates. Main Python 3.11 had
1,440 passes/38 skips; final Python 3.12 had 1,444 passes/38 skips. Four final
verifier exclusion regressions were separately executed on both runtimes (41
verifier cases total); final lint and typing passed. Stable-source evidence
records 18 filesystem/75 secure-store/34 subprocess/60 fallback/91 compiled-native
passes per version, with 31 exact native-only fallback exclusions and zero other
gaps. See the completed parent for JSON paths and executable fingerprint. Fixed-format key/salt read budgets and
early fixed-field crypto admission remain documented follow-ups under GAP-008;
arbitrary valid payload limits remain caller-owned. Actual Windows/macOS evidence
is pending. Historical A4 rows are not blanket-promoted by these focused packets.

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

## Merge reconciliation — 2026-10-11

The local audit branch is being integrated with main@b105e26. Main retains
its newer process_imap API, style/docstring changes, cumulative process lifetime
accounting, run-directory rollback and cooperating content-store publication
locking. Audit authentication, recovery, cancellation and native parity repairs
and their strict regressions are retained. Older GAP-004/005/006 descriptions
from the audit branch do not reopen guarantees already reconciled on main.
Native-platform execution is numbered GAP-010 to avoid conflating it with the
2026-10-09 observed-process-lifetime GAP-009 record. Historical proof counts
remain evidence for their original trees; this merge needs fresh integration
verification before commit. That verification completed successfully; see the
[merge record](../tasks/done/2026-10-11-main-audit-merge.md) for corrected
publication schedules, full-suite/backend counts and exact rerun provenance.
Serialized cooperating CAS publication preserves the winning inode on both
paths; raw noncooperating replacement remains a reader snapshot risk. No actual
Windows/macOS or hosted-CI claim is added.


## Remote branch follow-up — 2026-10-11

Scoped review starts at `fix/audit-bugs-20261011@672bfb1`.
The [execution record](2026-10-11-comprehensive/local-verification.md) and
[task hierarchy](../tasks/done/2026-10-11-remote-audit-repairs.md) retain
baseline failures, independent finite probes and compatibility decisions.

- ALG-012/076: supported integer subclasses keep reference arithmetic/comparison
  semantics; booleans and nonintegers fail explicitly. Actual compiled and forced
  fallback execution remains required.
- ALG-025: clearing advances generation; older producers can finish for existing
  callers but cannot publish into the new generation. Pending calls require one
  live event loop; no cross-thread event-loop safety claim is made.
- ALG-032: supported normalized JSON set elements are sorted by canonical JSON
  keys, independent of mapping insertion order. Unsupported passthrough leaves
  are still rejected by the actual encoder; no arbitrary-object canonicality claim.
- ALG-033: traversal and file-opening errors propagate instead of returning a
  partial directory fingerprint. Links are excluded; explicitly supplied root
  aliases resolve as before. There is no atomic filesystem snapshot guarantee.
- ALG-066/067: owned synchronization metadata is hidden from source payloads
  and protected from deletion; rule reset/external rule sources that can erase
  those protections are rejected before target or marker mutation. Real local
  rsync and bounded spawn-process lock/crash schedules are required evidence.
- ALG-048: containers and copyable leaves are isolated; leaves whose copy fails
  retain identity under the existing tested compatibility contract.
- Process mapping: options validate before source consumption; automatic worker
  count is limited by observed finite work; arbitrary integer thresholds do not
  overflow platform-sized slice arguments. Configured lookahead and window
  budgets bound submission; they are not unconditional memory/deadline limits.
  Callable preflight uses the executor encoder and preserves registered reducers;
  exception-only imports do not enable any deserialization API. Existing strict
  security-import guards remain unchanged.

The frozen-source canonical local gate passes all six checks on input SHA256
`bd23ab31df2a8fd7d15954cd61c79e7e6693775a189a8f398928daa4fc789cbe`. Scoped repaired/proven contracts have local A4 integration
evidence within the linked packet; broader family and native-host limitations
remain as recorded. Historical A4 evidence alone did not certify this branch.


## Round-five remote verification — 2026-10-11

[The round-five record](2026-10-11-comprehensive/round-5-static-followup.md)
verifies `d94adfe` plus local style, proof and contract-documentation corrections.
ALG-025 synchronous clear now prevents earlier-generation producers from
publishing; existing callers keep their return/error outcome. Independent
concurrent misses remain permitted and run outside the cache bookkeeping lock.
ALG-031 is explicitly single-owner or externally synchronized; deadline checks
are cooperative and do not replace body exceptions with expiry failures.

Independent before/after and finite lifecycle proofs plus all six canonical
local gates pass (1716 tests per interpreter, actual native 91 each). Scoped
contracts have local A4 evidence on input SHA256 `f7615473b8c32f494e89fc1f28ede57f138d1cf9c56f2a224d8d41c095a68f80`; this does not
certify unexecuted hosts or invent budget thread safety. Existing family-wide
levels and broader proof gaps remain as recorded.


## Offline rounds 6–9 — 2026-10-12

[Local execution](2026-10-11-comprehensive/2026-10-12-offline-verification.md)
starts from `af0366f`. Scoped A3 packets establish iterative standard-container
traversal with preserved shallow/original oracles, cycle/value order, Result
variant integrity including None, finite cleanup timeout domains and cancellation,
and ALG-013 invalid-bound rejection before source consumption. ALG-029 polling
and handler/environment ownership are explicitly cooperative/caller-controlled.
Full interpreter/native suites and offline static/docs/artifact variants pass.
No canonical A4 promotion is claimed from reused cached dependencies or
unexecuted Windows/macOS hosts. Input SHA256: `b912b51a45747a6325e2cf930e27948696360e989c0ce9cb8cabc664c59d91fb`.
