# [ACTIVE]: Migration guide for v1.5.0 breaking change

**Date:** 2026-07-16
**Role:** Writer
**Component:** `docs`
**Status:** Pending

## 1. Goal

Document the v1.5.0 breaking change (compat shim removal) in a user-facing place so external consumers know how to migrate. The CHANGELOG has the entry, but users typically look at README/quickstart first.

## 2. Scope

### In Scope

Add a "Migration from v1.4.x" or similar section to **one** of:
- `README.md` (preferred — most visible)
- `docs/source/quickstart.md` (alternative — closer to the actual code)

Recommendation: `README.md`. It's the first thing external users see.

The section should explain:
1. What changed in v1.5.0: the `gunz_utils.validation` compat shim was removed
2. Who is affected: anyone importing from `gunz_utils.validation` directly
3. The migration path:
   ```python
   # Before (v1.4.x and earlier)
   from gunz_utils.validation import type_checked, validate_call
   
   # After (v1.5.0+)
   from gunz_utils.ext.validation_pydantic import type_checked, validate_call
   # OR (recommended; lazy-loaded by default)
   from gunz_utils import type_checked, validate_call
   ```
4. Why the change was made: the shim became dead code after the v1.3.0 ext.* split once all in-repo callers migrated

### Out of Scope

- Adding a separate `MIGRATION.md` file (more discoverable than a README section, but more file overhead)
- Updating the v1.5.0 CHANGELOG entry (already done)
- Creating a deprecation warning in the package — that ship has sailed (shim is already deleted)
- Backporting a deprecation cycle (would require re-introducing the shim with a warning, then deleting it again — scope creep)

## 3. Approach

Single edit + single commit. Surgical insertion into `README.md`.

The existing `README.md` is ~3.1K. Need to read it first to find a good insertion point. Likely after the "Features" / "Usage" sections but before "Installation".

### Implementation

After committing, the README should look like:

```markdown
# Gunz Utils
... (existing content) ...

## Migration

### v1.5.0 — `gunz_utils.validation` shim removed

The backwards-compat shim at `gunz_utils.validation` was removed in
v1.5.0. The shim existed since v1.3.0 to preserve the historical import
path during the `ext.*` dependency split.

**If you were importing from `gunz_utils.validation` directly**, migrate
to one of:

```python
# Option A: import from the canonical ext.* module
from gunz_utils.ext.validation_pydantic import type_checked, validate_call

# Option B: import from the package surface (lazy-loaded, recommended)
from gunz_utils import type_checked, validate_call
```

Both resolve to the same underlying functions. Option B is preferred for
new code as it doesn't depend on the internal `ext.*` layout.

**No change needed if you imported via `from gunz_utils import …`** —
the lazy-import paths still work exactly as before.

See `CHANGELOG.md` for the full v1.5.0 entry.

... (rest of existing content) ...
```

## 4. Verification

After commit:

1. `grep -nE "Migration" README.md` → must return at least 1 line (the new heading)
2. `grep -nE "v1.5.0" README.md` → must return at least 1 line (version mention)
3. `grep -nE "from gunz_utils.ext.validation_pydantic|from gunz_utils import" README.md` → must return both patterns
4. README still renders correctly (visual check — not enforceable here, but the diff should be additive only)
5. Tests still pass (no code change): `pytest tests/ -q` → 99 + 4
6. Ruff still clean (no Python change): `ruff check src/ tests/` → 0 issues

## 5. Definition of Done

- [ ] README.md updated with a v1.5.0 migration section
- [ ] Section explains: what changed, who's affected, the two migration paths
- [ ] All 4 verification greps return expected results
- [ ] Tests still pass (99 + 4)
- [ ] Ruff still clean (0 issues)
- [ ] Commit pushed to `origin/main`
- [ ] ikarus synced to the new HEAD