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
| `subprocess` | Shell-free structured command execution with captured output and timing. |

## Design constraints

- The core remains standard-library only.
- Retry never guesses whether an operation is idempotent.
- Async cancellation propagates rather than being converted into retries.
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
