# [ACTIVE]: Fix api.rst broken validation directive + add missing modules

**Date:** 2026-07-16
**Role:** Programmer
**Component:** `docs`
**Status:** DONE (pushed at `3378b5b`, 2026-07-16). Broken `.. automodule:: gunz_utils.validation` directive replaced with `gunz_utils.ext.validation_pydantic`. New `Models` and `Upstream Protocol` sections added. ikarus synced to `3378b5b`.
**Supersedes:** Discovered during v1.5.0 verification — `docs/source/api.rst` references `gunz_utils.validation` (the shim deleted in v1.5.0). Sphinx build would fail or emit "module not found" warnings.

## 1. Goal

Fix the broken `.. automodule:: gunz_utils.validation` directive in `docs/source/api.rst` (the shim was deleted in v1.5.0). While in there, add missing public-API sections that have been added since the original 4-module list: `models`, `upstream_protocol`, plus the `ext.*` modules that are also part of the public surface.

## 2. Scope

### In Scope
- Replace `.. automodule:: gunz_utils.validation` with `.. automodule:: gunz_utils.ext.validation_pydantic` in `docs/source/api.rst`
- Add new sections for `models` and `upstream_protocol` (these exist as public API since v1.3.0 but were never documented in `api.rst`)
- Optionally add an "ext" section that lists the ext modules (they're public but discoverable via `.. automodule::` already — auto-included once we list them)
- ONE atomic commit with message `docs(api): fix broken validation directive; add models + upstream_protocol`
- Push to `origin/main`

### Out of Scope
- Sphinx build verification (sphinx isn't installed locally; would need `pip install .[docs]` first)
- Changes to `docs/source/conf.py` (separately deferred)
- Changes to `docs/source/quickstart.md` or `concepts.md` (separate tasks)
- Replacing the `.. automodule::` pattern with a curated manual API listing (much bigger scope)

## 3. Approach

The `.. automodule::` directive auto-discovers public symbols from the module. For modules behind the lazy-import (`type_checked`, `resolve_project_root`, etc.), they're listed in `__all__` and re-exported from `__init__.py`. So `.. automodule:: gunz_utils.enums` documents all the `BaseStrEnum`, `BaseIntEnum`, etc. classes automatically.

For the validation module, the canonical implementation is `gunz_utils.ext.validation_pydantic`. The shim that was deleted in v1.5.0 was `gunz_utils.validation`.

### Implementation

```diff
 Validation
 ----------
 
-.. automodule:: gunz_utils.validation
+.. automodule:: gunz_utils.ext.validation_pydantic
    :members:
    :undoc-members:
    :show-inheritance:
 
 Project
 -------
 
 .. automodule:: gunz_utils.project
    :members:
    :undoc-members:
    :show-inheritance:
 
 Security
 --------
 
 .. automodule:: gunz_utils.security
    :members:
    :undoc-members:
    :show-inheritance:
+
+Models
+------
+
+.. automodule:: gunz_utils.models
+   :members:
+   :undoc-members:
+   :show-inheritance:
+
+Upstream Protocol
+-----------------
+
+.. automodule:: gunz_utils.upstream_protocol
+   :members:
+   :undoc-members:
+   :show-inheritance:
```

## 4. Verification

After commit lands:

1. `grep -nE "automodule.*gunz_utils\.validation$" docs/source/api.rst` → must return 0 results (the broken reference is gone)
2. `grep -nE "automodule.*gunz_utils\.ext\.validation_pydantic" docs/source/api.rst` → must return 1 match (the new canonical reference)
3. `grep -nE "automodule.*gunz_utils\.models" docs/source/api.rst` → must return 1 match (new section)
4. `grep -nE "automodule.*gunz_utils\.upstream_protocol" docs/source/api.rst` → must return 1 match (new section)
5. Tests still pass (no code change, but verify): `pytest tests/ -q` → 99 + 4
6. Ruff still clean (no Python change): `ruff check src/ tests/` → 0 issues
7. `python -c "from gunz_utils import models, upstream_protocol"` → both succeed (confirms they're importable; `.. automodule::` will discover their public classes)

## 5. Definition of Done

- [x] `docs/source/api.rst` no longer references `gunz_utils.validation`
- [x] `docs/source/api.rst` references `gunz_utils.ext.validation_pydantic` for the Validation section
- [x] New `Models` section added (`.. automodule:: gunz_utils.models`)
- [x] New `Upstream Protocol` section added (`.. automodule:: gunz_utils.upstream_protocol`)
- [x] All 4 verification greps return expected results
- [x] Tests still pass (99 + 4)
- [x] Ruff still clean (0 issues)
- [x] Commit pushed to `origin/main` at `3378b5b`
- [x] ikarus synced to `3378b5b`