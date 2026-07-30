# [PENDING]: Delete the validation compat shim

**Date:** 2026-07-16
**Role:** Programmer
**Component:** `validation`
**Status:** DONE (pushed at `36945a6`, 2026-07-16). Shim deleted, preconditions met, public API still works via lazy import.
**Supersedes:** Deferred item from `docs/tasks/done/2026-07-15-protocol-tier1_cleanup_housekeeping.md` §9

## 1. Goal

Delete the backwards-compat shim at `src/gunz_utils/validation.py` after all in-repo callers have migrated to the canonical `gunz_utils.ext.validation_pydantic` import path.

## 2. Background

The compat shim was added in commit `59ec712` to preserve the historical `from gunz_utils.validation import ...` import path after the v1.3.0 ext.* split. It re-exports `type_checked` and `validate_call` from `gunz_utils.ext.validation_pydantic`.

After [`2026-07-16-validation-migration`](active/2026-07-16-validation-migration.md) lands:
- `tests/test_validation_leak.py` no longer imports from `gunz_utils.validation`
- `docs/source/quickstart.md` no longer imports from `gunz_utils.validation`
- No other caller in the repo uses this import path

The shim becomes dead code and can be deleted.

## 3. Scope

### In Scope
- Delete `src/gunz_utils/validation.py` (the 19-line compat shim)
- ONE atomic commit with message `chore(validation): delete compat shim after caller migration`

### Out of Scope
- Any new feature work on the validation module
- Changes to `ext/validation_pydantic.py` or `ext/validation_stdlib.py`
- Changes to public API surface beyond removing the shim
- Modifying `__init__.py` to remove `validation` from any list (it's not currently in `__all__` as a string; only `type_checked` and `validate_call` are, via the `_LAZY` dict which goes through `ext.validation_pydantic` directly)

## 4. Preconditions

Before executing this task, verify:

1. **No caller of the shim remains** in the repo:
   ```bash
   git grep -nE "from gunz_utils\.validation |import gunz_utils\.validation\b"
   ```
   Must return 0 results. If any result remains, this task is BLOCKED — finish the migration first.

2. **Tests pass** at HEAD before deletion:
   ```bash
   pytest tests/ -q
   ```
   Must show 99 passed + 4 subtests. If not, debug before deleting.

3. **`ext.validation_pydantic` is fully functional** in isolation:
   ```bash
   python -c "from gunz_utils.ext.validation_pydantic import type_checked, validate_call; print(type_checked)"
   ```
   Must succeed.

## 5. Implementation Plan

### Commit 1: `chore(validation): delete compat shim after caller migration`

```bash
git rm src/gunz_utils/validation.py
# Verify
git grep -nE "from gunz_utils\.validation " src/ tests/ docs/   # must return 0
pytest tests/ -q                                              # 99 + 4 subtests
ruff check src/ tests/                                        # All checks passed
git commit -m "chore(validation): delete compat shim after caller migration"
git push origin main
```

## 6. Post-Deletion Verification

1. `python -c "from gunz_utils.validation import type_checked"` → must FAIL with `ModuleNotFoundError: No module named 'gunz_utils.validation'`. This is expected — callers have migrated.
2. `python -c "from gunz_utils import type_checked; print(type_checked.__module__)"` → must print `gunz_utils.ext.validation_pydantic` (the `_LAZY` re-export still works).
3. `pytest tests/ -q` → still 99 + 4 subtests.
4. `git grep -nE "gunz_utils\.validation " CHANGELOG.md` → the v1.4.0 entry mentions the compat shim; update it to reflect removal.

## 7. CHANGELOG Update

Add a "Removed" entry under a new `## [1.5.0]` (or `[1.4.1]` patch) section in `CHANGELOG.md`:

```markdown
### Removed
- `src/gunz_utils/validation.py` compat shim. All callers have
  migrated to `from gunz_utils.ext.validation_pydantic import ...`.
  The shim was originally added in v1.3.0 (commit 59ec712) to
  preserve the historical import path during the ext.* split.
```

Coordinate the version bump with the `__version__` sync in `__init__.py`, `pyproject.toml`, and `conf.py` if releasing a new version. If this is bundled into a larger release, defer CHANGELOG update to that release.

## 8. Definition of Done

- [x] Preconditions verified (no remaining callers, tests pass, ext path works)
- [x] `src/gunz_utils/validation.py` deleted via `git rm`
- [x] Tests still pass (99 + 4 subtests)
- [x] Ruff still clean (0 issues)
- [x] Public API via `from gunz_utils import type_checked` still works (`gunz_utils.ext.validation_pydantic`)
- [ ] CHANGELOG updated (deferred — bundle into next release per task spec §7)
- [x] Commit pushed to `origin/main` at `36945a6`

## 9. Out-of-Scope Followups

- **External consumers** may still use `from gunz_utils.validation import ...`. This is a **breaking change** for those users. Consider:
  - Coordinate with the next release (1.4.1 patch or 1.5.0 minor)
  - Document in CHANGELOG with the migration path: `gunz_utils.ext.validation_pydantic`
  - Consider a deprecation warning for one release cycle before deletion
- **This task** deletes without warning. The migration task (#b4) + a documented release note may be sufficient for internal use; external users need a deprecation cycle.