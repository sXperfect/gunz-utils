# gunz-ml → gunz-utils reuse boundary

## Goal

Centralize dependency-free mechanisms that are useful across Gunz repositories
without pulling machine-learning semantics into the foundational utilities
package.

## Extracted in this branch

| Original gunz-ml capability | Shared gunz-utils owner | Notes |
|---|---|---|
| Stable BLAKE2b diagnostic sampling | `gunz_utils.sampling` | Generic named-item sampling, exact stable priority behavior preserved. |
| Counterfactual diagnostic matrix | `gunz_utils.experiments` | General pristine-state variant matrix and numeric metric comparison. |
| Health INFO retention algorithm | `gunz_utils.structures.retain_priority_and_recent` | Caller supplies the priority predicate; no HealthEvent dependency. |
| Experiment lineage deep diff | `gunz_utils.structures.deep_diff` | Typed structural differences with list/tuple support and cycle protection. |
| Lightweight execution Trace | `gunz_utils.instrumentation.Trace` | Generic span timing with success/failure and metadata. |
| Dataset/structured fingerprints | `gunz_utils.hashing` | Canonical structured hashes plus stable directory manifests/hashes. |
| Local content-addressed artifact store | `gunz_utils.content_store` | Streaming copy, digest validation, corruption detection. |
| Named lifecycle fault injection | `gunz_utils.faults.NamedFaultInjector` | Generic checkpoint-based deterministic failure injection. |
| SIGTERM/preemption callback | `gunz_utils.signals.install_termination_handler` | Reversible registration with optional shell-compatible exit. |
| Generic run manifest/provenance | `gunz_utils.provenance` | Git/system/package/environment/config provenance with explicit environment allowlisting. |
| Safe network URI/TCP checks | `gunz_utils.network` | Standards-oriented authority URIs and dependency-free reachability checks. |
| Research bootstrap/effect helpers | `gunz_utils.stats` | Seeded bootstrap mean CI, normal replicate summaries, and paired within-subject effects. |
| Ablation/parameter grid | `gunz_utils.experiments.parameter_grid` | Generic Cartesian named-factor combinations. |
| Train/validation/test split mechanics | `gunz_utils.partitions.PartitionManifest` | Generic immutable disjoint named partitions with stable fingerprints. |
| Dataset group leakage checks | `gunz_utils.partitions.partition_overlaps` | Generic overlap detection and disjointness assertion for hashable group IDs. |
| Provider trust allow/deny logic | `gunz_utils.security.NameAccessPolicy` | Generic named capability access policy. |
| HPO count/time budget | `gunz_utils.limits.ResourceBudget` | Existing shared-foundation item/time/deadline budget; no duplicate execution-budget type needed. |
| Fingerprint-aware experiment DAG | `gunz_utils.dag` | Dependency-ordered workflow execution with transitive cache invalidation. |
| Artifact provenance graph | `gunz_utils.provenance_graph` | Generic immutable provenance nodes, stable ancestry and unresolved external inputs. |
| Data-cache rsync mechanism | `gunz_utils.sync` | Shared shell-free rsync mirroring with optional flock coordination and atomic success markers; CLI/logging stay with consumers. |

## Existing gunz-utils capabilities that should replace gunz-ml duplicates

These should be consolidated from gunz-ml rather than copied into gunz-utils.

| gunz-ml implementation | Prefer in gunz-utils |
|---|---|
| reliability.atomic_write_bytes | `gunz_utils.io.atomic_write` / `gunz_utils.fs.atomic_write_bytes` |
| artifact SHA-256 helpers | `gunz_utils.hashing.file_hash` |
| generic artifact verification | `gunz_utils.content_store` or `gunz_utils.benchmark.artifacts` |
| regression metric budgets | `gunz_utils.benchmark.policy` + `benchmark.gate` |
| simple wall-clock timing | `gunz_utils.timing` / `gunz_utils.benchmark` |
| generic retry/concurrency patterns | existing `gunz_utils.retry`, `concurrency`, `resilience` |
| simple deterministic test faults | existing/extended `gunz_utils.faults` |

## Keep in gunz-ml

The following are mechanisms only superficially generic; their semantics belong
to the ML/tensor domain and should remain in gunz-ml:

- tensor traversal, tensor cloning and sparse tensor statistics;
- model/optimizer/scheduler/GradScaler checkpoint semantics;
- gradient, activation, parameter and optimizer health;
- Jacobian/Hessian/Fisher/GGN and representation analysis;
- PyTorch hooks and hook lifecycle auditing;
- DDP/FSDP and torch.compile parity;
- AMP-specific optimizer-step semantics;
- ML fault injection into activations, gradients and optimizer state;
- attention, residual, normalization, vision, sequence/audio diagnostics;
- HealthEvent severity, hypothesis generation and evidence ranking.

## Deferred candidates

### PyTorch extension package

A future optional `gunz_utils.ext.torch_*` layer could host tensor-tree
cloning, state-tree comparison and generic PyTorch runtime helpers used by more
than one ML repository.

This branch deliberately does not add such an extra because gunz-utils currently
keeps its core dependency-free and repository policy requires explicit approval
before adding dependencies.

### URI/database helpers

gunz-ml contains multiple URI builders with inconsistent encoding and
database-specific behavior. A shared URI API should be designed independently
instead of transferring either implementation unchanged.

## gunz-ml migration gate

The current gunz-ml development and CI workflows sometimes install a sibling
gunz-utils checkout, but current `pyproject.toml` does not declare gunz-utils
as a runtime dependency and production source currently has no hard gunz-utils
imports.

Therefore this extraction branch does not silently change gunz-ml package
metadata. Once dependency policy is made explicit, gunz-ml can:

1. replace `health.sampling.stable_priority/sample_named_items` with shared imports;
2. replace the generic core of `health.diagnostic_matrix`;
3. implement health retention as a thin priority predicate adapter;
4. replace `experiment.lineage.deep_diff`;
5. replace `observability.Trace`;
6. compose data fingerprints from shared hashing;
7. replace the local artifact store;
8. replace generic named fault/preemption helpers;
9. replace artifact lineage graph mechanics with the shared provenance graph;
10. replace cache synchronization mechanics with `gunz_utils.sync` while retaining gunz-ml-specific CLI/logging policy;
11. replace dataset leakage overlap mechanics with `gunz_utils.partitions`;
12. replace generic ablation grids and replicate statistics with `gunz_utils.experiments` and `gunz_utils.stats`.

ML-specific wrapper names can remain for backwards compatibility.


## Cross-repository consumer audit

The extracted APIs were checked against repeated mechanisms in other Gunz
repositories.

### Hyperion

- custom atomic byte/JSON publication should use shared filesystem/JSON helpers;
- resolver retry loops can use `gunz_utils.retry.RetryPolicy` and
  `async_run_with_retry`;
- crawler object storage can use `gunz_utils.content_store` with two-level
  fanout, direct byte/stream ingestion, and hardlink/copy materialization;
- crawler provenance can use `gunz_utils.provenance_graph`;
- cache mirroring can use `gunz_utils.sync`.

Media-type validation, crawler-specific failure codes, browser escalation and
snapshot-promotion policy remain Hyperion-owned. The current Hyperion
`ContentAddressedAssetStore.adopt()` write-then-copy flow can become direct
`put_bytes()` plus optional materialization.

### Hermes

- provider retry/backoff can use the shared retry executor while retaining
  Hermes' FailureClass taxonomy;
- exact provider Retry-After values and fixed schedules are supported through
  RetryPolicy.delay_override in both sync and async execution;
- file hashing and dataset fingerprints should compose shared hashing rather
  than maintain one-off SHA-256 loops;
- generic dataset partition identity can use PartitionManifest where applicable.

Trading calendars, market freshness semantics, provider capabilities and
financial completeness checks remain Hermes-owned.

### Helios / Hyperion / orchestration repositories

The shared DAG, provenance graph, deterministic sampling, execution provenance,
fault injection, signal handling, structured tracing and content-addressed
storage are intentionally domain-neutral and can be adopted without bringing in
gunz-ml or PyTorch.


### Persistence boundaries

The cross-repository audit intentionally did **not** introduce a generic SQLite
checkpoint database. Hermes, Hyperion and My-Hermes all use SQLite, but their
schemas represent different domain invariants: market-data chunks, crawler
frontiers/history, and control-plane/task state. A shared persistence layer
should emerge only after at least two consumers have a truly compatible storage
contract.

Likewise, these policies remain consumer-owned for now:

- Hyperion snapshot validation/promotion semantics;
- Hermes recency-dependent market-data freshness TTLs;
- trading calendars and provider capability windows;
- application-specific checkpoint schema migrations.

The shared layer provides the mechanisms around them: atomic IO, retry,
content-addressed storage, provenance, DAGs, signals, locking/synchronization,
hashing and bounded resource policies.
