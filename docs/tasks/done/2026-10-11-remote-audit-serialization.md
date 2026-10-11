# Remote audit: serialization

Status: focused repairs complete; executable files frozen for root integration
Parent: [Integration task](2026-10-11-remote-audit-repairs.md)
Checkout: /tmp/gunz-utils-fix-audit-20261011-672bfb1
Baseline: `672bfb1790c0b52e7494ae9ff5171e80fab3a9fc`

## Ownership and boundaries

Changed only binary.py, serialization.py, dict_utils.py, new dedicated
`tests/test_core/test_remote_audit_serialization_20261011.py`, and this task.
Existing shared 20261011 regressions, native C, shared registry/docs/configuration,
main checkout and private linter sources were not edited. Root owns fragments,
shared docs/registry, full gates and any commit/publication.

## Reproduction and repairs

The new finite 12-case module first reproduced **5 failures, 7 passes**: three
supported integer subclasses rejected by the exact-int gate and two canonical
set/frozenset ordering failures from equivalent mapping insertion order.

### Subclass compatibility: runtime repaired

`encode_uvarint` now rejects bool explicitly and accepts isinstance(value, int),
restoring IntEnum and ordinary/custom integer subclass support. Custom arithmetic
and comparison behavior still follows `_py_encode_uvarint`; the existing native
wrapper delegates these subclasses to that reference. No int coercion strips
subclass behavior. Bool/noninteger rejection, uint64 bounds, native recursion/
depth budgets and existing strict tests remain unchanged.

### Canonical set order: runtime repaired

The prior repr sort key retained mapping insertion order, although the final JSON
encoder normalized the same mapping keys. Converted set items now sort by compact
JSON keys using sort_keys, ensure_ascii=False and allow_nan=False. This makes
valid hashable Mapping set/frozenset canonical outputs independent of equivalent
insertion order. New exact-byte and decoded-value oracles cover both containers.

`default=repr` is used only to form ordering keys for existing passthrough objects;
it never replaces payload values or enables those objects in the actual canonical
encoder. A dedicated identity/rejection test proves that an opaque set member
remains the same object in to_jsonable and is rejected by canonical_json.
Canonical ordering for some prior set representations can change; root's fixed
fragment should describe this deterministic-format correction. Arbitrary unsupported
Python objects retain their existing caller-defined repr/copy behavior.

### AUD-010 / copy isolation: documentation corrected, accepted alias limit

No runtime copy policy changed. Existing strict
`test_merge_isolation_with_uncopyable_leaf_object` explicitly requires original
leaf identity when deepcopy raises; this is decisive compatibility evidence.
Root agreed to preserve it and correct the public overclaim rather than silently
breaking supported behavior or suppressing that test.

Public/internal deep_merge docs now distinguish copied containers from leaves
following their deepcopy protocol. A protocol can return itself, and failed
copies retain original identity; shared mutable state can therefore affect the
original after result mutation. The new mutable uncopyable-leaf case demonstrates
that accepted alias while independently asserting copied container/list isolation.
AUD-010 is **not** a fully isolated runtime repair. Callers requiring universal
independence must supply leaves whose copy protocol produces independent objects.
All existing cycle/DAG/container isolation proofs remain strict.

## Style and focused verification

Installed gunz_style.fix.fix_source(..., {'style'}) was applied only to owned
files with exact before/after AST-equivalence checking: source files required zero
mechanical edits, new test required 11 style-only edits. Import banners and local
isort split directives, gunz-style signatures, #? notes and Ruff88 were preserved.
No private linter repository edits or source-wide unrelated reformatting occurred.

Commands use absolute worktree source PYTHONPATH and disable plugin autoload:

```bash
PYTHONPATH=/tmp/gunz-utils-fix-audit-20261011-672bfb1/src \
PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 /tmp/gunz-utils-audit-20261008/bin/python \
  -m pytest -q tests/test_core/test_remote_audit_serialization_20261011.py \
  tests/test_core/test_dict_utils.py tests/test_core/test_serialization.py \
  tests/test_core/test_audit_native_safety_regressions.py \
  tests/test_core/test_binary_accel.py tests/test_core/test_parser_native_resource_audit.py
```

Ordinary focused runs: Python3.11 **121 passed, 31 expected native-only skips,
6 subtests**, 1.03s; Python3.12 **121 passed, 31 expected skips, 6 subtests**, .92s.

`tmp/serialization-20261011/matrix.py` loads the existing maintained native verifier
without editing it, appends only dedicated/dict test paths to its in-memory tuple,
and runs each backend with explicit RS03_EXPECT_NATIVE=0/1. Every leg verifies
source origin and actual hook activation. Compiled artifacts are built only in
isolated source copies under this worktree's ignored tmp; no src extension exists.

```bash
PYTHONPATH=/tmp/gunz-utils-fix-audit-20261011-672bfb1/src \
  /tmp/gunz-utils-audit-20261008/bin/python tmp/serialization-20261011/matrix.py
PYTHONPATH=/tmp/gunz-utils-fix-audit-20261011-672bfb1/src \
  /tmp/gunz-utils-audit-20261008-py312/bin/python tmp/serialization-20261011/matrix.py
```

| Interpreter | Forced fallback | Actual asserted native |
|---|---|---|
| Python3.11.14 | 121 passed, 31 expected native skips, .96s | 152 passed, zero skips, .96s |
| Python3.12.13 | 121 passed, 31 expected native skips, .85s | 152 passed, zero skips, 1.05s |

Both original strict subclass regressions and new canonical/copy-limit cases pass
on both actual native legs. Native export/refcount/weakref/depth proofs also pass.
Pinned pytest9.0.3; Ruff0.14.10 passes on all owned source/test files; mypy1.19.1
succeeds on those four files. Final edits after the runtime matrix only adjusted
import directives and precise leaf-copy documentation; static checks reran.

## Remaining integration and platform limits

Only Linux was executed. No new native Windows/macOS, OOM, sanitizer, complete
package-wide audit, or canonical full-gate certification is claimed. Existing
caller byte/width/shared-graph budgets and unsupported-object behavior remain.
Root performs independent review, fragments, registry reconciliation and full
static/docs/packaging/main/compat/native integration gates. No commit, branch
switch, merge, push, remote job, external message or production store action.

Executable source and dedicated test are frozen; any meaningful additional edit
requires coordinator reconciliation before final verification.


## Coordinator integration
All six canonical local gates pass on the frozen corrected snapshot; see the
[completed parent](2026-10-11-remote-audit-repairs.md) and its source fingerprint.
