# [DONE]: gunz-utils Python v6.0 Compliance

## Goal
Fix gunz-utils code to comply with python-v6_0.md best practices guide.

## Compliance Status (verified 2026-07-16 at HEAD `883a232`)

### Modules with complete dunder blocks (`__author__`, `__email__`, `__license__`, `__version__ = "1.3.2"`)

| Module | Status |
|:---|:---|
| `src/gunz_utils/enums.py` | ✅ (pre-existing) |
| `src/gunz_utils/security.py` | ✅ (pre-existing; missing `__version__`, follows existing repo style) |
| `src/gunz_utils/project.py` | ✅ (after `__version__` sync to 1.3.2) |
| `src/gunz_utils/models.py` | ✅ added in this task |
| `src/gunz_utils/upstream_protocol.py` | ✅ added in this task |
| `src/gunz_utils/validation.py` (compat shim) | ✅ added in this task |
| `src/gunz_utils/ext/observability_loguru.py` | ✅ added in this task |
| `src/gunz_utils/ext/project_gitpython.py` | ✅ (pre-existing) |
| `src/gunz_utils/ext/project_stdlib.py` | ✅ added in this task |
| `src/gunz_utils/ext/secure_crypto.py` | ✅ added in this task |
| `src/gunz_utils/ext/secure_store.py` | ✅ added in this task |
| `src/gunz_utils/ext/validation_pydantic.py` | ✅ (pre-existing) |
| `src/gunz_utils/ext/validation_stdlib.py` | ✅ added in this task |

### `# -*- coding: utf-8 -*-` removed (3 files)
- `src/gunz_utils/models.py`
- `src/gunz_utils/ext/observability_loguru.py`
- `src/gunz_utils/ext/secure_crypto.py`

### `t.Optional[X]` / `typing.Optional[X]` → `X | None` (4 files)
- `src/gunz_utils/project.py`
- `src/gunz_utils/ext/project_gitpython.py`
- `src/gunz_utils/ext/project_stdlib.py`
- `src/gunz_utils/models.py` (and `typing.Dict[str, Any]` → `dict[str, Any]`)

## Cleanup landed in this task

Three commits, all atomic and reverted:

```
883a232 refactor(models): use modern X | None syntax; drop typing.Dict/Any
e5fe545 refactor(project): use modern X | None syntax; sync __version__ to 1.3.2
fc906d1 chore(py-v6): add module metadata dunders; drop legacy coding headers
```

The original 2026-04-28 task's checklist was partially stale by 2026-07-16:
- `security.py` already had `__license__` (claimed missing)
- `enums.py` already had `__license__` (claimed missing)
- `validation.py` (referenced in the task) had moved to `ext/validation_pydantic.py` per the v1.3.0 ext.* split; the root `validation.py` is now a 19-line compat shim
- `project.py` was a folder with two implementation modules (`ext/project_gitpython.py` + `ext/project_stdlib.py`)
- `conf.py` intersphinx mapping was already done (lines 18-22)

## Definition of Done

- [x] All modules use modern `| None` syntax where `Optional` was used
- [x] All modules have complete metadata blocks (dunders)
- [x] `security.py` follows section-header conventions (was already compliant)
- [ ] Non-obvious logic has `#?` explanatory comments — **deferred; out of task scope, design-heavy**

## Out of scope (deferred)

- `#?` explanatory comments across non-obvious logic — design-decision-heavy, should be per-module
- `intentional` blank-line style harmonization across files (each file has slightly different spacing)
- `models.py` field reordering or renaming
- Any public API docstring expansion

## Outcome

Task archived 2026-07-16 as Done. All mechanical python-v6 modernization
is complete. Tests remain green: 81 passed + 4 subtests.