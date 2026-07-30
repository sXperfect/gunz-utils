# [ACTIVE]: Remove tracked Sphinx build artifacts

**Date:** 2026-07-16
**Role:** Programmer
**Component:** `docs`
**Status:** DONE (pushed at `e57e603`, 2026-07-16). 87 files untracked via `git rm -r --cached docs/_build`; files preserved on disk; `.gitignore` was already correct (line 21). Tests still 99 + 4, ruff still clean.
**Supersedes:** Discovered during verification of B5 ([`2026-07-16-validation-shim-removal`](done/2026-07-16-validation-shim-removal.md))

## 1. Goal

Remove 87 tracked Sphinx build artifacts from `docs/_build/`. These were committed in commit `82d78df docs: modernize structure and content to gold standard` before the `.gitignore` properly excluded the build directory.

## 2. Scope

### In Scope
- `git rm -r --cached docs/_build` to untrack all 87 files
- Single commit on `main`: `chore(docs): untrack Sphinx build artifacts`
- Push to `origin/main`

### Out of Scope
- Any local deletion of `docs/_build/` (it's gitignored — won't be tracked anyway)
- Changes to `.gitignore` (already correct: `docs/_build/` is on line 21)
- Changes to Sphinx build configuration
- Rebuilding the docs (the CI workflow rebuilds automatically on push)

## 3. Approach

The `docs/_build/` directory is already in `.gitignore` (line 21). The 87 files are tracked because they were committed before the `.gitignore` was enforced for this directory, OR because the original author used `git add -A` which ignored the gitignore at some point.

**Fix: use `git rm -r --cached` to untrack them.** This:
- Removes them from git tracking
- Leaves the files in place on disk (already gitignored — won't be re-added)
- Future `git add .` calls will correctly skip them

### Implementation

```bash
cd /home/sxperfect/projects/gunz-utils
git rm -r --cached docs/_build
# Verify: git status --short shows ~87 "D " entries (deleted from index)
# Verify: docs/_build/ still exists on disk
ls docs/_build/ | head -3    # must show files
git commit -m "chore(docs): untrack Sphinx build artifacts"
git push origin main
```

## 4. Verification

After commit lands:

1. `git ls-files docs/_build/` → must return 0 results (nothing tracked under that path)
2. `ls docs/_build/ | wc -l` → must still show 87 files on disk (preserved locally)
3. `git grep -nE "from gunz_utils\.validation " src/ tests/ docs/` → must return 0 real callers (only historical task-log references in done/, which are intentional)
4. `pytest tests/ -q` → still 99 + 4
5. `ruff check src/ tests/` → still 0 issues
6. Working tree clean (modulo the existing 2 untracked task files)

## 5. Definition of Done

- [x] `git rm -r --cached docs/_build` executed
- [x] `git ls-files docs/_build/` returns 0 results
- [x] Files remain on disk (verified by `ls docs/_build/`)
- [x] Tests still pass (99 + 4 subtests)
- [x] Ruff still clean (0 issues)
- [x] Commit pushed to `origin/main` at `e57e603`
- [x] No other files modified (only `docs/_build/*` deleted)