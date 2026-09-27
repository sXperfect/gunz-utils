# Production Foundation Utilities

## Scope

These modules provide dependency-free primitives that recur across unrelated
Gunz applications. They deliberately avoid HTTP, database, agent, and framework
policy.

## Modules

| Module | Contract |
|---|---|
| `concurrency` | Bound concurrent async work while preserving input order. |
| `retry` | Sync/async retry with exponential defaults, bounded delay, cancellation safety, and context-aware delay overrides. |
| `cache` | Bounded TTL memoization and async single-flight request coalescing. |
| `serialization` | Stable JSON normalization for hashes, cache keys, and persistence. |
| `subprocess` | Shell-free structured command execution with captured output and timing. |
| `limits` | Stateless limits plus cumulative byte/item/depth/deadline budgets. |
| `plugins` | Deterministic failure-isolated entry-point discovery. |
| `provenance` | Runtime provenance with explicit environment allowlisting. |
| `streaming` | Bounded writers, digest writers, and copy-and-hash primitives. |
| `versioning` | Versioned payload envelopes and forward migration registry. |
| `sampling` | Stable deterministic named-item sampling independent of Python hash randomization. |
| `experiments` | Pristine-state variant matrices and scalar metric comparison. |
| `structures` | Bounded retention and typed deep structural differences. |
| `instrumentation` | Lightweight success/failure execution spans. |
| `content_store` | Integrity-checked content-addressed storage with fanout and atomic materialization. |
| `signals` | Reversible process and asyncio termination/preemption handlers. |
| `network` | Standards-oriented authority URI construction and TCP reachability. |
| `stats` | Seeded bootstrap mean confidence intervals and paired effects. |
| `partitions` | Immutable disjoint named partitions with stable fingerprints. |
| `dag` | Dependency-ordered workflow execution with transitive fingerprint caching. |
| `provenance_graph` | Acyclic lineage graphs with unresolved/external input tracking. |
| `sync` | Shell-free rsync mirroring with advisory locking and atomic completion markers. |
| `leases` | Backend-neutral renewable lease heartbeat coordination for async workers. |

## Design constraints

- The core remains standard-library only.
- Retry never guesses whether an operation is idempotent; predicates and hooks let consumers classify and observe retries.
- Async cancellation propagates rather than being converted into retries.
- `map_unordered` bounds in-flight tasks and streams completion-order results for large workloads.
- TTL caches expose lightweight hit/miss/size statistics and can be cleared explicitly.
- Rate limiters expose an estimated available-token balance for diagnostics.
- Single-flight shields shared work from cancellation by one waiter.
- Canonical JSON sorts mapping keys, rejects non-finite floats, and does not
  silently encode bytes.
- Subprocess helpers never enable a shell. Callers pass an argument sequence.
- Every primitive has a focused core test and participates in the existing
  Python 3.11/3.12 CI matrix.

## Future extension boundary

The foundation now also includes rate limiting, typed environment parsing,
collection transforms, identifiers, UTC/deadline helpers, layered configuration,
explicit result values, safe diagnostics, async lifecycle helpers, and
framework-independent testing helpers.

HTTP clients, database abstractions, CLI frameworks, and domain-specific
application orchestration remain consumer-library concerns. The generic DAG
executes dependency relationships only; it does not own application policy.

## Performance engineering

The benchmark/profiling subsystem intentionally combines native Gunz process-tree
measurement with adapters to mature specialist tools rather than reimplementing
their deepest instrumentation. See
[`benchmark-profiling-tool-landscape.md`](benchmark-profiling-tool-landscape.md)
for reuse, reimplementation, integration, and performance decisions.

## Long-horizon program

Future work is organized by engineering properties and milestone exit criteria,
not individual helper features. See
[`long-horizon-engineering-roadmap.md`](long-horizon-engineering-roadmap.md).


## Cross-project foundation boundary

Hyperion and Helios-JS may depend on these mechanism-level primitives. Domain-specific crawler state, JavaScript IR, bundler semantics, protocol inference, HTTP policy, and application schemas remain in their owning repositories.
