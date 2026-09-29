# SRS: Reusable Runtime Adoption Across Gunz Ecosystem

**Definition:** `docs/design/definitions/reusable_runtime.yaml`
**Design Document:** `docs/design/reusable-runtime-adoption.md`

## 1. Scope & Objective

This Software Requirements Specification (SRS) defines the operational constraints, behavioural requirements, and adoption contracts for integrating `gunz-utils` reusable runtime primitives across sibling repositories (Hyperion, Hermes, gunz-ml, and autonomous worker daemons).

## 2. Architectural Invariants

### INV-01: Zero Runtime Dependency Floor
- The core package MUST NOT import or require any third-party Python package at runtime.
- All mechanisms MUST run on pure Python 3.11+ standard library.
- Acceleration and third-party integrations (e.g. plotting, pydantic) MUST remain optional extras isolated from core import paths.

### INV-02: Namespace-First API Isolation
- Primitives MUST be exposed via their individual subsystem modules (e.g. `gunz_utils.content_store`, `gunz_utils.leases`, `gunz_utils.sampling`).
- The root package namespace (`gunz_utils`) MUST NOT bulk-re-export subsystem types without explicit backwards compatibility justification.

### INV-03: Mechanism vs. Domain Boundary
- `gunz-utils` MUST provide only pure, reusable mechanisms.
- Application-specific schemas, domain state tables, provider failure taxonomies, ML tensor math, and trading calendars MUST remain in consumer repositories.

## 3. Subsystem Behavioural Specifications

### SPEC-01: Content-Addressed Storage (`gunz_utils.content_store`)
- Ingestion of bytes or byte streams MUST compute the SHA-256 digest deterministically.
- Direct materialization MUST support hardlinking where filesystem support permits, falling back to copy without raising unhandled errors.
- Any digest mismatch between the stored payload and requested digest MUST raise `CorruptedStoreEntryError`.

### SPEC-02: Distributed Lease Coordination (`gunz_utils.leases`)
- `run_with_lease_heartbeat` MUST execute the worker payload concurrently with a periodic heartbeat loop.
- The heartbeat period MUST be strictly less than the lease duration (`heartbeat_interval < lease_duration`).
- If `renew_fn()` returns `False` or raises an unhandled error, the in-flight worker task MUST be cancelled immediately to prevent split-brain execution.

### SPEC-03: Deterministic Process-Independent Sampling (`gunz_utils.sampling`)
- Given a stable string identifier and a seed, `stable_priority` MUST produce a uniform, deterministic float score in $[0.0, 1.0)$ using BLAKE2b hashing.
- Sampling $k$ items from a set of $N$ items MUST return the exact same selection regardless of input ordering, worker process count, or machine architecture.

### SPEC-04: Pristine-State Counterfactual Experiments (`gunz_utils.experiments`)
- `VariantMatrix` MUST invoke a state-factory before applying each variant transform.
- Each variant evaluation MUST execute from pristine, isolated state to guarantee zero cross-contamination between successive runs.

### SPEC-05: Context-Aware Dynamic Retries (`gunz_utils.retry`)
- `RetryPolicy` MUST compute exponential backoff with full jitter by default.
- If a custom `delay_override` callback is provided, its non-None returned delay MUST take precedence, enabling dynamic handling of upstream HTTP `Retry-After` headers.

### SPEC-06: Preemption & Termination Interception (`gunz_utils.signals`)
- `install_termination_handler` MUST catch `SIGTERM` and `SIGINT`.
- The registered callback MUST execute once, releasing held resources or writing flush markers before optionally invoking standard shell exit codes (e.g., $128 + 15$).

## 4. Consumer Migration & Verification Contract

1. Consumers MUST pin `gunz-utils >= 1.12.0`.
2. Initial consumer PRs MUST maintain local facade shims so existing consumer imports do not break.
3. Consumer test suites MUST verify equivalence against previous local behavior prior to removing local legacy code.
