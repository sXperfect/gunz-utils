# [ACTIVE]: Migrate validation callers off the compat shim

**Date:** 2026-07-16
**Role:** Programmer
**Component:** `validation`
**Status:** DONE (pushed at `494c885`, 2026-07-16). Both callers migrated, no `from gunz_utils.validation` callers remain in src/ or tests/ or docs/source/. Shim at `src/gunz_utils/validation.py` is now dead code and ready for removal — see [`2026-07-16-validation-shim-removal`](../pending/2026-07-16-validation-shim-removal.md).
**Supersedes:** Deferred item from `docs/tasks/done/2026-07-15-protocol-tier1_cleanup_housekeeping.md` §9 + `docs/tasks/done/2026-04-28-gunz_utils-docs_improvement.md` (which marked migration as out-of-scope at the time).

## 1. Goal

Two callers in the codebase still import `gunz_utils.validation` (the compat shim from commit `59ec712`). Migrate them to the canonical `gunz_utils.ext.validation_pydantic` path so that:
1. The compat shim becomes unused
2. A follow-up task can safely delete the shim (see `2026-07-16-validation-shim-removal.md`)

## 2. Scope

### In Scope
- `tests/test_validation_leak.py` — currently does `from gunz_utils.validation import type_checked` (line 2)
- `docs/source/quickstart.md` — currently does `from gunz_utils.validation import validate_call` (line 37)
- Both files: change to `from gunz_utils.ext.validation_pydantic import <name>`

### Out of Scope
- Deletion of the compat shim at `src/gunz_utils/validation.py` — separate task
- Adding `GunzBaseModel` example to quickstart — separate task
- Updating `docs/source/api.rst` (it auto-discovers via `.. automodule::`) — separate task
- Any new validation feature work
- Any code-style cleanups beyond the import change

## 3. Approach

Two surgical edits, both one-line. Verify tests + ruff after each.

### Commit 1: `refactor(validation): migrate callers off gunz_utils.validation compat shim`

**File 1: `tests/test_validation_leak.py`**
- Line 2: `from gunz_utils.validation import type_checked`
- → `from gunz_utils.ext.validation_pydantic import type_checked`

**File 2: `docs/source/quickstart.md`**
- Line 37: `from gunz_utils.validation import validate_call`
- → `from gunz_utils.ext.validation_pydantic import validate_call`

**Steps:**
```bash
# Edit tests/test_validation_leak.py
# Edit docs/source/quickstart.md
# Verify: pytest tests/ -q  (99+4 still pass)
# Verify: ruff check src/ tests/  (still clean)
git add tests/test_validation_leak.py docs/source/quickstart.md
git commit -m "refactor(validation): migrate callers off gunz_utils.validation compat shim"
git push origin main
```

## 4. Verification

After commit lands:

1. `git grep -nE "from gunz_utils\.validation " src/ tests/ docs/` → must return 0 results
   - This proves no remaining caller imports through the shim
2. `pytest tests/ -q` → 99 passed + 4 subtests
3. `ruff check src/ tests/` → All checks passed
4. `python -c "from gunz_utils.validation import type_checked, validate_call; print(type_checked.__module__)"` → still works (shim not deleted yet)

## 5. Definition of Done

- [x] `tests/test_validation_leak.py` imports from `gunz_utils.ext.validation_pydantic`
- [x] `docs/source/quickstart.md` imports from `gunz_utils.ext.validation_pydantic`
- [x] No code references `gunz_utils.validation` as an import path (verified by `git grep`)
- [x] Tests still pass (99 + 4 subtests)
- [x] Ruff still clean (0 issues)
- [x] Commit pushed to `origin/main` at `494c885`

## 6. Follow-up task

After this lands, the compat shim at `src/gunz_utils/validation.py` becomes dead code (no caller imports it). A separate task file at `docs/tasks/pending/2026-07-16-validation-shim-removal.md` should delete it.