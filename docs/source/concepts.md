# Core Concepts

**Gunz-Utils** serves as the shared foundational layer for the Gunz ecosystem.

## 1. The Core Registry

In a multi-library project, sharing configurations and constants is difficult. Gunz-Utils provides the base classes (like `BaseStrEnum`) that ensure `gunz-cm` and `gunz-ml` speak the same "language" when referring to experiment modes, data formats, and processing steps.

## 2. Security Buffer

One of the primary goals of Gunz-Utils is to provide safe wrappers around standard operations. This includes:
*   **Path Sanitization:** Preventing path traversal when reading genomic data.
*   **Validation:** Ensuring that research parameters conform to expected types before heavy computation starts.

## 3. Infrastructure Discovery

The `project` module handles the complexities of discovering repository roots and managing data paths across different environments (Local Workstations vs. Slurm Cluster). By using these utilities, we ensure that code written locally "just works" when submitted to the cluster.

## 4. Optional Dependencies

Gunz-Utils' core install ships with four runtime dependencies (`pydantic`,
`cryptography`, `gitpython`, `loguru`) so that `import gunz_utils` works
out-of-the-box. Projects that want a smaller footprint can install narrower
extras (see `installation.md` for the matrix).

Beyond install-time extras, every dep-bundled module also has a
**stdlib-only fallback** available under `gunz_utils.ext.*`. For
example:

```python
# Default: pydantic-backed type_checked
from gunz_utils import type_checked

# Stdlib-only fallback: no pydantic needed at runtime
from gunz_utils.ext.validation_stdlib import type_checked as type_checked_strict
```

This lets downstream projects pick between power (pydantic) and minimal
install size (stdlib) on a per-module basis.
