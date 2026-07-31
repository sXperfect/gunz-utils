# [ACTIVE]: Remove `HealthStatus` from gunz-utils (public API removal)

**Date:** 2026-07-16
**Role:** Programmer
**Component:** `models`
**Status:** Pending

## 1. Goal

Drop `HealthStatus` from `gunz-utils` to keep the library minimal. The class is unused internally, was added speculatively as part of the v1.3.0 public surface for downstream MCP servers, but the maintainer has decided the library should not host domain-specific response models. If a downstream consumer needs an MCP health response model, they should define it in their own repo.

This is a **public API removal** → requires a **minor version bump** (v1.5.0 → v1.6.0) per semver.

## 2. Scope

### In Scope
- Delete the `HealthStatus` class definition from `src/gunz_utils/models.py`
- Remove `HealthStatus` from `src/gunz_utils/__init__.py` imports and `__all__` list
- Remove all 3 `HealthStatus`-related tests from `tests/test_core/test_models.py` (the `TestHealthStatusUnaffected` class)
- Update the module docstring in `models.py` to remove the `HealthStatus` bullet
- Bump `__version__` from `"1.5.0"` to `"1.6.0"`
- Bump `pyproject.toml` `version` from `"1.5.0"` to `"1.6.0"`
- Bump `docs/source/conf.py` `release` from `'1.5.0'` to `'1.6.0'`
- Add a `[1.6.0]` entry to `CHANGELOG.md` explaining the removal and migration path
- THREE atomic commits:
  1. `feat(models): remove HealthStatus from public API`
  2. `chore(release): v1.6.0`
  3. (Optional bookkeeping for task archive — separate commit)

### Out of Scope
- Removing `GunzBaseModel` (still useful for downstream consumers, well-designed, properly tested)
- Touching `HealthStatus` in any external consumer repo (we don't own those)
- Adding a deprecation cycle (already gone — direct removal is cleaner for a library this small)
- Reorganizing `models.py` structure

## 3. Background

`HealthStatus` was introduced in v1.3.0 (commit `53d83c2 feat(models): add SecretMetadata dataclass for SecureStore entries` — same era) as a standardized response model for MCP server health probes. It has zero internal usage in `gunz-utils`. It's purely a public-API offering for downstream consumers.

The maintainer's 2026-07-16 directive: keep the library minimal. Domain-specific response models belong with the consumer, not with the foundational utilities library.

## 4. Approach

### Commit 1: `feat(models): remove HealthStatus from public API`

**File 1: `src/gunz_utils/models.py`**
- Delete lines 78–end (the `HealthStatus` class definition) — currently 78 to ~102 (the file ends at line 102 with the `checks: dict[str, Any]` line)
- Update the module docstring to remove the `HealthStatus` bullet (lines 13)

**File 2: `src/gunz_utils/__init__.py`**
- Change `from .models import GunzBaseModel, HealthStatus` → `from .models import GunzBaseModel`
- Remove `"HealthStatus",` from `__all__` list

**File 3: `tests/test_core/test_models.py`**
- Remove the import: `from gunz_utils.models import HealthStatus` (or change it to only import what's still needed)
- Remove the entire `TestHealthStatusUnaffected` class (3 tests, ~25 lines)
- The 3 tests:
  - `test_healthstatus_still_subclasses_basemodel`
  - `test_healthstatus_constructible_without_args`
  - `test_healthstatus_explicit_status_overrides_default`

**Steps:**
```bash
# Edit models.py
# Edit __init__.py
# Edit tests/test_core/test_models.py
# Verify: pytest tests/ -q  → must show 96 + 4 subtests (was 99 + 4; removed 3 tests)
# Verify: ruff check src/ tests/  → 0 issues
# Verify: python -c "from gunz_utils import HealthStatus" → ModuleNotFoundError (expected)
# Verify: python -c "from gunz_utils import GunzBaseModel" → still works
git add src/gunz_utils/models.py src/gunz_utils/__init__.py tests/test_core/test_models.py
git commit -m "feat(models): remove HealthStatus from public API"
```

### Commit 2: `chore(release): v1.6.0`

**File 1: `pyproject.toml`** — `version = "1.5.0"` → `version = "1.6.0"`
**File 2: `src/gunz_utils/__init__.py`** — `__version__ = "1.5.0"` → `__version__ = "1.6.0"`
**File 3: `docs/source/conf.py`** — `release = '1.5.0'` → `release = '1.6.0'`
**File 4: `CHANGELOG.md`** — Add `[1.6.0]` entry above `[1.5.0]`:

```markdown
## [1.6.0] — 2026-07-16

### Removed

- `gunz_utils.HealthStatus` (MCP server health-check response
  model). The class was added in v1.3.0 as part of the public API
  but was never used internally and is too domain-specific for a
  foundational utilities library. Downstream consumers that need
  this functionality should define their own response model:

  ```python
  # Before (v1.5.x and earlier)
  from gunz_utils import HealthStatus

  # After (v1.6.0+) — define in your own codebase
  from pydantic import BaseModel
  class HealthStatus(BaseModel):
      status: str = "UNKNOWN"
      # ... your fields here
  ```
```

**Steps:**
```bash
# Edit pyproject.toml, __init__.py, conf.py
# Edit CHANGELOG.md (insert before [1.5.0])
# Verify all version sync
git add pyproject.toml src/gunz_utils/__init__.py docs/source/conf.py CHANGELOG.md
git commit -m "chore(release): v1.6.0"
git push origin main
git tag -a v1.6.0 -m "v1.6.0 — 2026-07-16 ..."
git push origin v1.6.0
```

## 5. Verification

After both commits land:

1. `grep -rn "HealthStatus" src/ tests/` → 0 results (or only docstring mentions if any are intentional)
2. `pytest tests/ -q` → 96 passed + 4 subtests (was 99 + 4; -3 HealthStatus tests)
3. `ruff check src/ tests/` → 0 issues
4. `python -c "from gunz_utils import HealthStatus"` → `ModuleNotFoundError` (expected; the class is gone)
5. `python -c "from gunz_utils import GunzBaseModel; print(GunzBaseModel)"` → still works
6. `python -c "import gunz_utils; print(gunz_utils.__version__)"` → `1.6.0`
7. `git tag -l | grep v1.6.0` → tag exists locally
8. `git ls-remote --tags origin | grep v1.6.0` → tag exists on origin

## 6. ikarus sync

After pushing, sync ikarus:
```bash
ssh ikarus 'cd /home/adhisant/projects/gunz-utils && git fetch origin && git reset --hard origin/main && git tag -d v1.6.0 2>/dev/null; git fetch origin tag v1.6.0 && /home/adhisant/tmp/miniforge3/envs/gunz-utils/bin/pip install -e . && /home/adhisant/tmp/miniforge3/envs/gunz-utils/bin/python -m pytest tests/ -q'
```

## 7. Definition of Done

- [ ] `HealthStatus` class deleted from `models.py`
- [ ] `HealthStatus` removed from `__init__.py` imports and `__all__`
- [ ] `HealthStatus` test class removed from `tests/test_core/test_models.py`
- [ ] Module docstring updated (no `HealthStatus` bullet)
- [ ] Tests pass: 96 + 4 subtests
- [ ] Ruff clean: 0 issues
- [ ] `from gunz_utils import HealthStatus` raises `ModuleNotFoundError`
- [ ] `from gunz_utils import GunzBaseModel` still works
- [ ] Version bumped to 1.6.0 in 3 files (pyproject, `__init__.py`, conf.py)
- [ ] CHANGELOG entry added under `[1.6.0]`
- [ ] Tag `v1.6.0` cut and pushed
- [ ] ikarus synced to new HEAD, pip reinstalled, tests pass