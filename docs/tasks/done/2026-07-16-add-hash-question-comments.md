# [ACTIVE]: Add #? explanatory comments across non-obvious logic

**Date:** 2026-07-16
**Role:** Programmer
**Component:** `src/`
**Status:** Pending
**Supersedes:** Deferred item from `docs/tasks/done/2026-04-28-gunz_utils-python-v6_0-compliance.md` §Out of scope (line 59)

## 1. Goal

Add `#?` explanatory comments to non-obvious logic across the 13 source modules per the python-v6 standards (`.hyperhedron/guides/programming/python/core.md` §"Use `#?` for Explanatory Comments"):

> Use inline comments prefixed with `#?` to explain the *why* behind
> complex or non-obvious code, not the *what*. The `?` prefix **is
> mandatory** for IDE syntax highlighting purposes.

This is **design-heavy** because what counts as "non-obvious" is subjective — only the maintainer knows which decisions warrant a `#?` and which are obvious from context.

## 2. Scope

### In Scope
- Add `#?` comments to **judgment calls** in the codebase where the rationale isn't obvious from reading the code
- Existing comments may be **upgraded** from `#` to `#?` where appropriate (the prefix is mandatory per standards)
- Modules to consider: `enums.py`, `models.py`, `project.py`, `security.py`, `upstream_protocol.py`, `validation.py` (now a shim — N/A, file deleted in v1.5.0), and 8 `ext/*` modules

### Out of Scope
- Adding `#?` to every line (excessive; defeats purpose)
- Adding docstrings to functions that don't already have them (separate concern)
- Type annotation changes
- Renaming variables for clarity (separate concern)

## 3. Approach

Because this is judgment-heavy, I will:

1. **First pass: scan for existing `#?` comments** to understand the established style
2. **Identify 5–10 high-value locations** that genuinely benefit from `#?` comments:
   - Where a non-obvious decision was made (e.g., "we strip whitespace by default because…")
   - Where the code looks like it does X but actually does Y (e.g., a fallback that hides a warning)
   - Where there's a subtle bug-prevention pattern (e.g., the `from exc` chains I added in commit `c55f88d`)
   - Where an optimization is in play (e.g., the `DEFAULT_MAX_INPUT_LENGTH` constant)
3. **Add the comments** in one focused commit
4. **Verify** tests + ruff still pass

## 4. Concrete Examples (from prior session work)

Some `#?` comments I've already added in this session that match the standard:

- In `security.py` (pre-existing, decades old):
  ```python
  # ? Windows checks the "base" name up to the first dot.
  # ? e.g. "CON.txt" and "CON.tar.gz" are both invalid.
  ```

- In `models.py` (pre-existing, also decades old):
  ```python
  # ? Re-raise as TypeError to be more Pythonic for type issues,
  # ? effectively hiding the Pydantic trace from the end user unless they look closer.
  ```

- In `project.py` (pre-existing):
  ```python
  # ? Cache the root to avoid repeated disk I/O
  ```

So the codebase already uses `#?` pervasively. This task is really about **finding gaps** in modules that don't yet use `#?` consistently.

## 5. Verification

After commit:

1. `grep -rE "^\s*#\?" src/ | wc -l` → higher than baseline (more `#?` comments)
2. `pytest tests/ -q` → still 99 + 4
3. `ruff check src/ tests/` → still 0 issues
4. Each added comment must START with `#?` (not `#`), per the standards
5. Each added comment must explain **why**, not **what**

## 6. Definition of Done

- [ ] At least 5 `#?` comments added across modules that lacked them
- [ ] No `#` comments changed to `#?` if they're explanatory in nature (already-OK comments stay as-is)
- [ ] Tests still pass (99 + 4)
- [ ] Ruff still clean (0 issues)
- [ ] Commit pushed to `origin/main`
- [ ] ikarus synced to the new HEAD

## 7. Effort estimate

This task is intentionally scoped loosely. A single commit of 5–15 `#?` comment additions is the expected output. If more than that is needed, split into multiple commits.