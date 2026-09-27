# Core Concepts

**Gunz Utils** is the shared low-level utility layer for the Gunz ecosystem. Its
design goal is reuse without importing application-specific policy into a common
library.

## 1. Domain-neutral shared primitives

A utility belongs here when its contract is useful across multiple consumers.
Examples include deterministic hashing, bounded concurrency, retries, safe file
publication, subprocess execution, redaction, provenance, sampling, statistics,
and benchmark infrastructure.

Application schemas, provider-specific semantics, market/data freshness rules,
and ML-framework-specific behavior should remain in their owning repositories
unless a stable cross-project abstraction has emerged.

## 2. Dependency-free core

The package declares no mandatory runtime dependencies. Core imports use the
Python standard library, which keeps the base install lightweight and makes
shared infrastructure easier to reuse in constrained environments.

Third-party integrations are opt-in extras rather than implicit requirements.

## 3. Explicit optional integrations

Optional backends live under `gunz_utils.ext` and selected convenience symbols
are resolved lazily from the package root.

For example:

```python
from gunz_utils import type_checked
```

uses the optional Pydantic-backed integration when its dependency is installed.

Where a stdlib alternative exists, callers can select it explicitly:

```python
from gunz_utils.ext.validation_stdlib import type_checked as type_checked_stdlib
```

See [Installation](installation.md) for the current extras matrix.

## 4. Namespace-first APIs

Large or specialized subsystems are generally accessed through their module
namespace instead of being bulk-exported at the package root. This keeps the
top-level API deliberate and reduces accidental coupling.

Examples include:

- `gunz_utils.benchmark` for benchmarking and profiling;
- `gunz_utils.provenance` and `gunz_utils.provenance_graph` for lineage;
- `gunz_utils.versioning` for versioned envelopes and migrations;
- `gunz_utils.content_store` for content-addressed storage.

## 5. Safety and reproducibility

Many utilities encode defensive behavior that is easy to get subtly wrong when
reimplemented independently: atomic publication, bounded resource usage,
shell-free subprocess execution, secret redaction, safe path handling,
deterministic serialization, stable fingerprints, and explicit provenance.

These helpers provide mechanisms rather than application policy. Consumers
remain responsible for choosing appropriate limits, retry semantics, access
rules, and domain-specific validation.
