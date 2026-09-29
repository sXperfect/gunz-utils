# Reusable Runtime Adoption Across Gunz Repositories

## 1. Purpose and Architectural Invariants

This design document defines the integration architecture and adoption blueprints for consuming `gunz-utils` (starting from release `v1.12.0`) across sibling projects—including **Hyperion**, **Hermes**, **gunz-ml**, **My-Hermes**, autonomous agent runtimes, and shared service daemons.

The primary architectural contract of `gunz-utils` is:

1. **Zero Runtime Dependencies:** The core package has no mandatory third-party dependencies. It is pure Python 3.11+.
2. **Mechanism vs. Domain Separation:** `gunz-utils` provides domain-neutral *mechanisms* (concurrency, leases, CAS storage, deterministic sampling, atomic I/O, retry backoff, DAG workflows). Sibling repositories own their *domain schemas and policies* (crawler taxonomies, trading calendars, financial completeness rules, ML tensor operations, model architectures).
3. **Namespace-First Imports:** Subsystems are imported from their specific module namespaces (e.g., `gunz_utils.leases`, `gunz_utils.content_store`) rather than polluting the root package namespace.
4. **Typed PEP 561 Compliance:** Every public module is strictly typed, covered by tests, and ships with the `py.typed` marker.

---

## 2. Consumer Integration Blueprints

### 2.1 Hyperion (Distributed Knowledge & Crawler Engine)

Hyperion operates distributed web crawlers, asset extractors, and content processing pipelines requiring high-integrity storage, safe directory mirroring, and worker fencing.

| Hyperion Component | Shared `gunz-utils` Primitive | Hyperion-Owned Domain Responsibility |
|:---|:---|:---|
| **Asset Object Storage** | `gunz_utils.content_store.ContentAddressedStore` | Media type inference, crawler manifest records, and database indexing. |
| **Directory Cache Mirror** | `gunz_utils.sync.rsync_mirror` | Snapshot promotion policy, storage mount paths, and operational CLI triggers. |
| **Crawler Asset Lineage** | `gunz_utils.provenance_graph.ProvenanceGraph` | Crawler node types, URL seeds, and entity graph relations. |
| **Distributed Worker Leases** | `gunz_utils.leases.run_with_lease_heartbeat` | Database claim/renew SQL queries, heartbeat persistence, and partition assignments. |
| **Safe Atomic Asset Writes** | `gunz_utils.io.atomic_write` / `gunz_utils.fs.atomic_write_bytes` | Media payload formatting and HTTP response caching. |

#### Implementation Pattern: 2-Level Fanout Content Store
Hyperion's `ContentAddressedAssetStore.adopt()` can transition from write-then-copy mechanics to direct streaming ingestion:
```python
from gunz_utils.content_store import ContentAddressedStore

# 2-level directory fanout: store_root/ab/cd/abcdef1234...
cas = ContentAddressedStore(store_root, fanout_levels=2)

# Stream download bytes directly into CAS
with open(temp_download_path, "rb") as stream:
    entry = cas.put_stream(stream)

# Entry digest is SHA-256 verified and immutable
assert cas.verify(entry.digest)

# Materialize hardlink or copy for external tools
cas.materialize(entry.digest, destination_path, mode="hardlink")
```

---

### 2.2 Hermes & My-Hermes (Financial Analytics & Provider Integration)

Hermes connects to volatile third-party financial APIs, market data streams, and quantitative calculation engines requiring robust retry policies, rate limiting, and cache freshness controls.

| Hermes Component | Shared `gunz-utils` Primitive | Hermes-Owned Domain Responsibility |
|:---|:---|:---|
| **API Provider Retry** | `gunz_utils.retry.RetryPolicy` + `delay_override` | `FailureClass` classification and provider-specific error mapping. |
| **Market Data Cache TTL** | `gunz_utils.cache.RecencyTTLPolicy` | Trading calendars, exchange holidays, and historical cutoff dates. |
| **Dataset Fingerprints** | `gunz_utils.hashing.structured_hash` / `file_hash` | DataFrame schema normalization and time-series alignment. |
| **Provider Rate Limiting** | `gunz_utils.rate_limit.TokenBucketRateLimiter` | Provider tier quotas, bursting allowances, and pricing tiers. |
| **Secure Token/Config I/O** | `gunz_utils.io.atomic_write(..., permissions=0o600)` | API secret allowlists and YAML environment variables. |

#### Implementation Pattern: Context-Aware Dynamic Retry
Hermes handles HTTP `429 Too Many Requests` with upstream `Retry-After` headers:
```python
from gunz_utils.retry import RetryPolicy, async_run_with_retry

def extract_retry_after(exc: BaseException) -> float | None:
    if isinstance(exc, ProviderRateLimitError):
        return exc.retry_after_seconds
    return None

policy = RetryPolicy(
    max_attempts=5,
    initial_delay=0.5,
    max_delay=60.0,
    delay_override=extract_retry_after,
)

result = await async_run_with_retry(policy, fetch_market_snapshot, symbol="AAPL")
```

---

### 2.3 gunz-ml (Machine Learning & Neural Diagnostics)

`gunz-ml` develops model diagnostics, ablation sweeps, and training experiments. `gunz-utils` provides the dependency-free experiment harness and statistical foundation without pulling PyTorch or CUDA into the base utility layer.

| `gunz-ml` Component | Shared `gunz-utils` Primitive | `gunz-ml`-Owned Domain Responsibility |
|:---|:---|:---|
| **Diagnostic Item Sampling** | `gunz_utils.sampling.sample_named_items` | Diagnostic targets and model checkpoint layers. |
| **Counterfactual Matrix** | `gunz_utils.experiments.VariantMatrix` | Model weights, optimizer state, and loss evaluation. |
| **Hyperparameter Grid** | `gunz_utils.experiments.parameter_grid` | Model architectures, learning rates, and scheduler configs. |
| **Health Event Retention** | `gunz_utils.structures.retain_priority_and_recent` | `HealthEvent` definitions, severity ranking, and hypothesis generation. |
| **Experiment Lineage Diff** | `gunz_utils.structures.deep_diff` | Tensor state diffs and checkpoint weight comparisons. |
| **Partition Leakage Guards** | `gunz_utils.partitions.partition_overlaps` | Patient/sample IDs, time-series boundaries, and split ratios. |
| **Statistical Significance** | `gunz_utils.stats.bootstrap_mean_ci` | Metric definitions and evaluation metrics. |

#### Implementation Pattern: Pristine-State Counterfactual Matrix
```python
from gunz_utils.experiments import VariantMatrix, pristine_state

def create_fresh_state():
    return {"baseline_loss": 0.42, "mutated": False}

matrix = VariantMatrix(create_fresh_state)
matrix.add_variant("disable_feature_x", lambda s: s.update({"mutated": True}))
matrix.add_variant("adjust_threshold", lambda s: s.update({"threshold": 0.8}))

results = matrix.run_all(evaluate_loss_fn)
```

---

### 2.4 Autonomous Agents & Worker Daemons

Worker processes, agent swarms, and background jobs require robust lifecycle safety, execution fencing, and resource budgeting.

| Agent / Daemon Need | Shared `gunz-utils` Primitive | Consumer-Owned Responsibility |
|:---|:---|:---|
| **Worker Fencing & Liveness** | `gunz_utils.leases.run_with_lease_heartbeat` | Database / Redis lease table and split-brain resolution. |
| **Cluster Preemption Handling** | `gunz_utils.signals.install_termination_handler` | Checkpoint flushes and in-flight job cleanup before exit. |
| **Execution Step / Time Limits** | `gunz_utils.limits.ResourceBudget` | LLM token counts, search tree depths, and tool budgets. |
| **Task Workflow Execution** | `gunz_utils.dag.WorkflowDAG` | Task dependency schemas and step execution functions. |
| **Lightweight Span Tracing** | `gunz_utils.instrumentation.Trace` | Observability sinks and dashboard visualizers. |

#### Implementation Pattern: Renewable Lease Coordination
```python
import asyncio
from gunz_utils.leases import LeaseTiming, run_with_lease_heartbeat

timing = LeaseTiming(lease_duration=10.0, heartbeat_interval=3.0)

async def work_loop():
    while True:
        await do_worker_step()
        await asyncio.sleep(1)

# Heartbeat runs concurrently; if renewal returns False, work_loop is cancelled immediately
await run_with_lease_heartbeat(
    renew_fn=renew_lease_in_db,
    work_fn=work_loop,
    timing=timing,
)
```

---

### 2.5 Defensive Core Primitives (Universal Adoption)

Any Python tool, CLI, or microservice can standardize on these defensive primitives:

* **Crash-Safe Atomic I/O (`gunz_utils.io.atomic_write`)**: Uses POSIX `os.replace` to prevent corrupted partial files when writing configuration, cache records, or serialized models.
* **Path Traversal Protection (`gunz_utils.fs.safe_path_join`, `open_path_under_base`)**: Resolves paths against a trusted base root and rejects `..` traversal or symlink escapes.
* **Secret Redaction (`gunz_utils.redaction.redact_diagnostics`, `mask_secret`)**: Cleanses raw exceptions, dictionary payloads, and environment captures before writing to logs.
* **Safe Name Access Policy (`gunz_utils.security.NameAccessPolicy`)**: Enforces explicit allow/deny pattern matching for plugin discovery, API endpoints, or provider namespaces.
* **Functional Error Handling (`gunz_utils.result.Result`, `Ok`, `Err`)**: Expresses recoverable operation results without unhandled exception bubbling.

---

## 3. Boundary Matrix: What Belongs Where

To prevent repository coupling and architectural drift, use this boundary matrix:

```
┌─────────────────────────────────────────────────────────────┐
│                    gunz-utils (Shared)                      │
│  - Pure Python mechanisms (Zero external runtime deps)      │
│  - Concurrency & Async Lease Heartbeats                     │
│  - Content-Addressed Storage (CAS) & Directory Sync         │
│  - Deterministic BLAKE2b Sampling & Experiment Matrix       │
│  - Non-parametric Bootstrap & Replicate Statistics          │
│  - Atomic I/O, Safe Paths, and Secret Redaction             │
│  - Workflow DAGs, Provenance Graphs & Resource Budgets      │
└──────────────────────────────┬──────────────────────────────┘
                               │ consumed by (via PyPI/git)
                               ▼
┌─────────────────────────────────────────────────────────────┐
│                 Consumer Sibling Repositories               │
│                                                             │
│   Hyperion        Hermes           gunz-ml         Agents   │
│   ┌────────┐     ┌────────┐       ┌────────┐     ┌────────┐ │
│   │Crawler │     │Trading │       │PyTorch │     │LLM     │ │
│   │Schemas │     │Calendar│       │Tensors │     │Prompts │ │
│   │URL Meta│     │Quotes  │       │CUDA    │     │Tools   │ │
│   └────────┘     └────────┘       └────────┘     └────────┘ │
└─────────────────────────────────────────────────────────────┘
```

| Mechanism / Domain | Belongs in `gunz-utils` | Belongs in Consumer Repository |
|:---|:---:|:---:|
| SHA-256 CAS file management | Yes | No |
| MIME-type detection & HTTP headers | No | Yes (Hyperion) |
| Async lease heartbeat & fencing | Yes | No |
| Database lease table SQL schema | No | Yes (Hyperion / Hermes) |
| Exponential backoff & jitter | Yes | No |
| Provider failure classification | No | Yes (Hermes) |
| Deterministic hash priority sampling | Yes | No |
| PyTorch tensor traversal & cloning | No | Yes (gunz-ml) |
| Cartesian parameter grid generation | Yes | No |
| Hyperparameter search objectives | No | Yes (gunz-ml) |
| Atomic file replacement | Yes | No |
| User configuration schemas | No | Yes (All) |

---

## 4. Consumer Adoption and Migration Protocol

When adopting `gunz-utils` in a consumer project:

1. **Explicit Dependency Declaration**:
   Declare `gunz-utils >= 1.12.0` in the consumer's `pyproject.toml` or `requirements.txt`.
2. **Backward-Compatible Consumer Shims**:
   Keep existing consumer import paths intact during initial adoption:
   ```python
   # Inside consumer repository (e.g. gunz_ml/health/sampling.py)
   from gunz_utils.sampling import sample_named_items, stable_priority
   ```
3. **Parity Testing**:
   Run existing consumer unit tests against the imported `gunz-utils` mechanism to confirm exact behavioral equivalence.
4. **Local Code Deletion**:
   Once parity tests pass, delete duplicated local helper implementations.
5. **No Domain Upstreaming**:
   Refuse any pull request that seeks to add domain-specific third-party libraries (e.g., `torch`, `pandas`, `scipy`, `httpx`) to `gunz-utils` core.
