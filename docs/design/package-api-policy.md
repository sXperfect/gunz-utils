# Package Architecture and Public API Policy

## Namespace-first imports

New functionality should be imported from stable subsystem namespaces rather
than automatically re-exported from `gunz_utils` root.

Preferred:

```python
from gunz_utils.benchmark import benchmark
from gunz_utils.binary import ByteReader
from gunz_utils.fs import atomic_write_bytes
from gunz_utils.pipeline import worker_map
```

The root namespace is reserved for highly stable, broadly useful compatibility
exports.

## Import-cost invariant

Core subsystem modules must not import optional third-party packages at module
import time. Optional integrations belong under `gunz_utils.ext` or perform
lazy imports inside the operation that requires them.

## Public API rules

- Every namespace with `__all__` has an API contract test.
- New root exports require an explicit compatibility justification.
- Deprecated root exports remain through the documented deprecation cycle.
- Internal implementation helpers use leading underscores.
- Cross-subsystem dependencies must point toward lower-level primitives and
  avoid import cycles.

## Acceleration

Reference implementations remain pure Python. Accelerated implementations are
optional and selected through explicit dispatch. A native backend must preserve
observable semantics and pass the same contract tests before becoming default.

## Milestone completion

M8 through M18 introduce subsystem APIs. M19 deliberately does not bulk-export
those APIs from the package root; this prevents the root namespace and
compatibility surface from growing without bound.
