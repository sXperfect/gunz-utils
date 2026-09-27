# Production Foundation Utilities

## Scope

These modules provide dependency-free primitives that recur across unrelated
Gunz applications. They deliberately avoid HTTP, database, agent, and framework
policy.

## Modules

| Module | Contract |
|---|---|
| `concurrency` | Bound concurrent async work while preserving input order. |
| `retry` | Sync/async exponential retry with bounded delay and cancellation safety. |
| `cache` | Bounded TTL memoization and async single-flight request coalescing. |
| `serialization` | Stable JSON normalization for hashes, cache keys, and persistence. |
| `subprocess` | Shell-free structured command execution with captured output and timing. |\n| `limits` | Stateless limits plus cumulative byte/item/depth/deadline budgets. |\n| `plugins` | Deterministic failure-isolated entry-point discovery. |\n| `provenance` | Runtime provenance with explicit environment allowlisting. |\n| `streaming` | Bounded writers, digest writers, and copy-and-hash primitives. |\n| `versioning` | Versioned payload envelopes and forward migration registry. |

## Design constraints

- The core remains standard-library only.
- Retry never guesses whether an operation is idempotent; predicates and hooks let consumers classify and observe retries.
- Async cancellation propagates rather than being converted into retries.\n- `map_unordered` bounds in-flight tasks and streams completion-order results for large workloads.\n- TTL caches expose lightweight hit/miss/size statistics and can be cleared explicitly.\n- Rate limiters expose an estimated available-token balance for diagnostics.
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

HTTP clients, database abstractions, CLI frameworks, and application
orchestration remain consumer-library concerns.

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
\n\n## Cross-project foundation boundary\n\nHyperion and Helios-JS may depend on these mechanism-level primitives. Domain-specific crawler state, JavaScript IR, bundler semantics, protocol inference, HTTP policy, and application schemas remain in their owning repositories.\n