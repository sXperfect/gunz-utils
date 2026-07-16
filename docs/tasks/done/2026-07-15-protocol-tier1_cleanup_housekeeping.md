# Task: Tier 1 — Cleanup Housekeeping (5 commits)

**Date:** 2026-07-15
**Role:** Programmer
**Component:** `protocol` (global)
**Status:** Done (2026-07-15, push `970f9aa`)

**Outcome:** All 5 commits landed and pushed. Commit 4 absorbed into Commit 2 (4-file deletion under one commit; message amended to honestly describe the bundled deletions). Tag deleted locally. Origin pushed via regular push (`git push origin main`, no force).

## 1. Goal

Close the post-merge residue from `0a7a134` ("Merge origin/main into local
main") and harden the dev loop. Four commits, ~20 minutes total, near-zero
risk, no behavior changes. After completion, the repo is "ship-shape v1.3.0"
with a configured linter, no dead-duplicate source files, no orphan tags, and
zero broken legacy import paths.

## 2. Scope

### In Scope
1. Add `[tool.ruff]` configuration to `pyproject.toml`
2. Delete three dead-duplicate root-level source files
3. Add a compat shim at `src/gunz_utils/validation.py`
4. Delete the legacy flat test `tests/test_secure_store.py`
5. Delete the orphan local tag `pre-history-scrub`
6. Verify after each commit (ruff check + import smoke test)
7. Push the four commits to `origin/main` (regular push, no force)

### Out of Scope
- Fixing the 68 pre-existing ruff issues surfaced by commit 1 (separate PR)
- Tier 2 work (mypy config, pre-commit, SRS, doc build)
- Migrating `tests/test_validation_leak.py` and `docs/source/quickstart.md`
  to use the canonical `ext.validation_pydantic` path (separate cleanup task;
  the compat shim preserves their current import path)
- Any history rewrite, rebase, or force-push

## 3. Approach

Each commit is atomic and revertable. We commit in the order listed below
because the validation compat shim (commit 3) must land **before** the
duplicates deletion (commit 2) would otherwise also remove any
`secure_store.py` reference — actually, the shim targets `validation.py`
which is separate from `secure_store.py`/`crypto.py`/`logging.py`. Still,
the shim goes first to keep concerns cleanly separated.

Wait — reordering: the compat shim **adds** `src/gunz_utils/validation.py`
(no file exists there now), and the duplicates deletion removes
`secure_store.py`, `crypto.py`, `logging.py` (separate files). The order
between shim and duplicates deletion is therefore independent. We'll do
duplicates deletion first (lower risk), then shim (additive change), then
test cleanup, then tag removal.

Final commit order:
1. **Commit 1 — ruff config** (already completed in this session)
2. **Commit 2 — delete dead duplicates** (`secure_store.py`, `crypto.py`, `logging.py`)
3. **Commit 3 — validation compat shim** (re-create `src/gunz_utils/validation.py`)
4. **Commit 4 — delete legacy test** (`tests/test_secure_store.py`)
5. **Commit 5 — delete orphan tag** (`pre-history-scrub`)

> Note: Commit 1 was completed during the planning phase of this task
> (see `git log` for the commit message). It is included here for
> completeness; the remaining four commits are pending.

## 4. Implementation Plan

### Commit 1 (DONE) — `chore(ruff): add [tool.ruff] config to pyproject.toml`

Already landed. SHA captured in git log. No further action.

### Commit 2 — `chore: delete dead duplicate src/ files`

**Files to delete:**
- `src/gunz_utils/secure_store.py` (418 lines, byte-identical to `ext/secure_store.py`)
- `src/gunz_utils/crypto.py` (93 lines, byte-identical to `ext/secure_crypto.py`)
- `src/gunz_utils/logging.py` (47 lines, byte-identical to `ext/observability_loguru.py`)

**Why these are safe to delete:**
- None are exported via `src/gunz_utils/__init__.py`'s lazy-import shim
  (verified: only `ext/*` paths appear there)
- The only external import of the root `secure_store` module is the legacy
  `tests/test_secure_store.py` which is also being deleted in Commit 4
- The two `__main__` string literals in `secure_store.py` (line 415) are
  informational error-message text and disappear with the file

**Steps:**
```bash
git rm src/gunz_utils/secure_store.py
git rm src/gunz_utils/crypto.py
git rm src/gunz_utils/logging.py
ruff check src/ tests/                # verify no breakage
python -c "from gunz_utils import SecureStore; print(SecureStore)"  # smoke
git commit -m "..."
```

### Commit 3 — `fix(validation): add compat shim re-exporting from ext.validation_pydantic`

**Why this is needed:**
- `tests/test_validation_leak.py:2` still does `from gunz_utils.validation import type_checked`
- `docs/source/quickstart.md:37` still does `from gunz_utils.validation import validate_call`
- The merge moved `validation.py` content to `ext/validation_pydantic.py`,
  so these imports currently fail at module-load time
- The compat shim restores the legacy import path without changing the canonical location

**Shim file:** `src/gunz_utils/validation.py` (≤15 lines)
```python
"""Backwards-compat shim re-exporting from ext.validation_pydantic.

The canonical implementation lives at ``gunz_utils.ext.validation_pydantic``
following the v1.3.0 dependency split (see CHANGELOG.md). This thin shim
preserves the historical import path ``from gunz_utils.validation import …``
for callers that have not yet migrated.

New code SHOULD import from the canonical location or from the public
package surface (``from gunz_utils import type_checked``).
"""
from __future__ import annotations

from gunz_utils.ext.validation_pydantic import (
    type_checked,
    validate_call,
)

__all__ = ["type_checked", "validate_call"]
```

**Steps:**
```bash
# write the shim
ruff check src/ tests/                # verify
python -c "from gunz_utils.validation import type_checked, validate_call"
git add src/gunz_utils/validation.py
git commit -m "..."
```

### Commit 4 — `chore: delete legacy flat tests/test_secure_store.py`

**Why safe:**
- 116 lines, differs from `tests/test_secure/test_secure_store.py` by exactly
  one line (the import statement: `from gunz_utils.secure_store` vs
  `from gunz_utils`)
- The `from gunz_utils.secure_store import SecureStore` import path is being
  deleted in Commit 2 (the root `secure_store.py` is going away)
- The new `tests/test_secure/test_secure_store.py` covers the same 12 tests

**Steps:**
```bash
git rm tests/test_secure_store.py
python -m pytest tests/test_secure/ -v   # verify the new suite still passes
git commit -m "..."
```

### Commit 5 — `chore: delete orphan pre-history-scrub tag`

**Why safe:**
- Tag points at `2096647` (pre-filter-branch snapshot)
- `git merge-base --is-ancestor pre-history-scrub main` → NO (unreachable from main)
- Tag subject: "Pre-history-scrub backup tag (d8c702d + new content)" —
  forensic backup created during the filter-branch rewrite session
- No current branch references it

**Steps:**
```bash
git tag -d pre-history-scrub
git for-each-ref --format='%(refname) %(objectname:short)' refs/tags/pre-history-scrub
# (empty = good)
git commit --allow-empty -m "..."
# OR: tags don't need a commit. The deletion is a ref-only operation.
# No commit needed for tag deletion. The 'commit' is conceptual.
```

Note: `git tag -d` does **not** create a commit (it only removes a ref). No
commit is required. This "commit" is actually a ref-cleanup step, not a
commit.

### Commit 6 — Push to origin

```bash
git push origin main
# regular push, no force — these are 4 additive commits ahead of origin/main
```

## 5. Verification (after each commit)

- `ruff check src/ tests/` → No new errors vs. pre-commit baseline
- `python -c "from gunz_utils import SecureStore"` → OK
- `python -c "from gunz_utils.validation import type_checked, validate_call"` → OK
- `python -m pytest tests/test_secure/ -v` → 12 tests pass
- `git status --short` → clean
- `git branch -a` → only `main`
- `git remote -v` → unchanged
- `git for-each-ref refs/tags/pre-history-scrub` → empty

## 6. Verification (after all commits pushed)

- `git log --oneline -10` → 4 new commits at HEAD
- `git rev-parse HEAD` == `git rev-parse origin/main`
- `git ls-remote --heads origin` → only `refs/heads/main`
- `ruff check src/ tests/` → still passes the new rule set (existing 68 issues are
  pre-existing, not introduced by these commits)
- `python -c "from gunz_utils import SecureStore"` → still OK
- No `tests/test_secure_store.py` at repo root
- No `src/gunz_utils/{secure_store.py,crypto.py,logging.py}` at repo root
- `src/gunz_utils/validation.py` exists (the compat shim)
- `pre-history-scrub` tag absent locally and remotely

## 7. Verified Assumptions (from pre-flight analysis)

| Assumption | Status | Evidence |
|------------|:---:|---------|
| `[tool.ruff]` absent from `pyproject.toml` | ✅ confirmed | grep returned NO_MATCH |
| `.ruff_cache/` exists (ruff has been run) | ✅ confirmed | `0.15.16/` cache present |
| Root `secure_store.py` byte-identical to `ext/secure_store.py` | ✅ confirmed | `diff` returned no output |
| Root `crypto.py` byte-identical to `ext/secure_crypto.py` | ✅ confirmed | `diff` returned no output |
| Root `logging.py` byte-identical to `ext/observability_loguru.py` | ✅ confirmed | `diff` returned no output |
| Root `validation.py` does NOT exist | ✅ confirmed | file absent; module moved to `ext/validation_pydantic.py` |
| None of the root modules are exported via `__init__.py` | ✅ confirmed | lazy shim maps only to `ext/*` paths |
| Root `secure_store.py` only imported by `tests/test_secure_store.py` | ✅ confirmed | grep returned only the legacy test |
| Root `validation.py` referenced by `tests/test_validation_leak.py` and `docs/source/quickstart.md` | ✅ confirmed | both files use `from gunz_utils.validation import …` |
| `tests/test_secure_store.py` differs from `tests/test_secure/test_secure_store.py` by exactly 1 line | ✅ confirmed | `diff` showed only the import line |
| `docs/build_docs.sh` does NOT exist | ✅ confirmed | but `scripts/build_docs.sh` DOES exist (797 bytes); `deploy_docs.yml` correctly invokes `./scripts/build_docs.sh` — no action needed |
| `pre-history-scrub` tag unreachable from `main` | ✅ confirmed | `git merge-base --is-ancestor` returned false |
| `pre-history-scrub` is not pointed to by any current branch | ✅ confirmed | `git for-each-ref --contains` showed only the tag itself |

## 8. Risks

| Risk | Mitigation |
|------|------------|
| External consumer relies on `from gunz_utils.secure_store import …` | Compat shim not provided for this path (none was requested). Mitigation: public-API re-export was already in place via lazy shim, so this only affects direct-submodule imports. Mention in CHANGELOG. |
| `secure_store.py`'s `__main__` block (line 415) had an informational message | The literal `"Usage: python -m gunz_utils.secure_store init"` disappears with the file. The same message exists in the byte-identical `ext/secure_store.py:415`, so `python -m gunz_utils.ext.secure_store init` continues to work. |
| User wants migrated callers instead of compat shim | Defer to follow-up task. Compat shim is the smallest safe fix that preserves current behavior. |
| 68 pre-existing ruff issues trip CI once enabled | Out of scope for this commit batch. Note in the commit message of Commit 1. Recommend `ruff check --fix` PR as follow-up. |
| Local-only tag deletion needs a commit to be visible to teammates | Local tags aren't shared anyway — `git push origin main` will not push the tag deletion. Add a note: teammates can `git fetch origin --prune` if they had it tracked. |

## 9. Out-of-Scope Items (for a follow-up task file)

- Migrate `tests/test_validation_leak.py` and `docs/source/quickstart.md`
  to the canonical `from gunz_utils import type_checked` / `from gunz_utils.ext.validation_pydantic import validate_call` paths, then remove the compat shim.
- Apply `ruff check --fix` to address the 68 pre-existing issues (mostly
  import sorting, whitespace, long lines, modernization). Should be a single
  PR with a `--statistics` summary so reviewers see the delta.
- Configure `mypy` (or `pyright`) in `pyproject.toml` per AGENTS.md §2.1's
  "type hints are mandatory" mandate.
- Add a `.pre-commit-config.yaml` running ruff + mypy + pytest on commit.

## 10. Commit Messages (templates)

```
chore: delete dead duplicate src/ files

Removes three byte-identical duplicate files left behind by the v1.3.0
dependency split (commit 0a7a134). Their content is now served by the
canonical ext/* modules:

- src/gunz_utils/secure_store.py (418 lines)  → ext/secure_store.py
- src/gunz_utils/crypto.py        (93 lines)  → ext/secure_crypto.py
- src/gunz_utils/logging.py       (47 lines)  → ext/observability_loguru.py

Verified safe via:
- src/gunz_utils/__init__.py lazy shim exports only the ext/* paths
- The only external import of gunz_utils.secure_store is the legacy
  tests/test_secure_store.py, which is removed in the next commit
- The __main__ informational message in secure_store.py is preserved
  in the byte-identical ext/secure_store.py:415
```

```
fix(validation): re-export type_checked from ext.validation_pydantic via compat shim

Restores the legacy import path `from gunz_utils.validation import …`
which is still used by:
- tests/test_validation_leak.py:2
- docs/source/quickstart.md:37

The canonical implementation moved to gunz_utils.ext.validation_pydantic
in the v1.3.0 dependency split. This shim is the smallest safe fix that
preserves current callers without forcing a documentation/test churn in
this commit batch.

Migrating the legacy callers to the canonical path is tracked as a
follow-up task. After that migration lands, this shim can be deleted.
```

```
chore: delete legacy flat tests/test_secure_store.py

Removed in favor of the per-feature layout tests/test_secure/test_secure_store.py
introduced by the v1.3.0 dependency split (commit 0a7a134). The two files
were 116 lines each and differed by exactly one import statement:

  < from gunz_utils.secure_store import SecureStore
  > from gunz_utils import SecureStore

The legacy import path is also being deleted (the root-level
secure_store.py module is gone in the previous commit), so the new file
must be the canonical test going forward.
```

```
chore: delete orphan pre-history-scrub tag

Local-only forensic backup tag created during the git filter-branch
session that purged .jules/ and JULES.md. The tag points at commit
2096647 which is NOT reachable from main (verified with
`git merge-base --is-ancestor pre-history-scrub main`).

No current branch points at this tag. The v1.0.0 / v1.3.0 / v1.3.1 tags
are the authoritative release markers. The pre-history-scrub value is
recoverable from reflog if ever needed.

No commit is created — git tag -d is a ref-only operation. Teammates who
had this tag tracked locally can clean up with `git tag -d pre-history-scrub`.
```

## 11. Status
- **Started:** 2026-07-15
- **Commit 1 completed:** 2026-07-15 (ruff config)
- **Commits 2-5:** pending
- **Completed:** —
- **PR:** —