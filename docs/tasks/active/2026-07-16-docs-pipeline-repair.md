# [ACTIVE]: Documentation Pipeline Repair (replaces 2026-04-28 docs_improvement)

**Date:** 2026-07-16
**Role:** Programmer
**Component:** `docs` / `ci`
**Status:** Code fixes DONE (pushed at `6c88aa4`). Cloudflare verification pending user action — see §8.
**Supersedes:** `docs/tasks/active/2026-04-28-gunz_utils-docs_improvement.md` (the original checklist is stale: api.rst already has all 4 modules; the workflow is broken in ways the original task didn't enumerate)

## 1. Goal

Repair the Cloudflare Pages docs-deploy pipeline so that pushing to `main` actually produces a working built site. Three concrete defects, three atomic commits, ~30 min. After this lands, the Cloudflare deployment becomes verifiable end-to-end.

## 2. Discovery: what's actually broken (verified 2026-07-16 at HEAD `6cb7ea9`)

The original 2026-04-28 task listed 3 phases. Reality is narrower and more pointed.

### Defect 1 — CI workflow installs the wrong extra (CRITICAL)
**File:** `.github/workflows/deploy_docs.yml` line 24
```yaml
pip install '.[all]'
```
But `pyproject.toml` `[project.optional-dependencies]`:
```toml
all  = [pydantic, cryptography, gitpython, loguru]                    # NO sphinx
docs = [sphinx, furo, myst-parser, sphinx-autodoc-typehints]          # sphinx is here
```
The `all` extra **does not include sphinx**. The CI installs runtime deps, then immediately tries to run `sphinx-build` which is not installed. **Every push to `main` triggers a CI failure.** This has been broken since the workflow was added.

### Defect 2 — Theme is misaligned with pyproject extras
`docs/source/conf.py` line 27: `html_theme = 'sphinx_rtd_theme'`
`pyproject.toml` `[project.optional-dependencies].docs` declares `furo` (not `sphinx_rtd_theme`).

Resolution: **keep `sphinx_rtd_theme` (per user decision 2026-07-16)** — preserves the existing site look. Drop `furo` from `docs` extra; add `sphinx_rtd_theme` to `docs` extra.

### Defect 3 — `conf.py` `release` is stale
`docs/source/conf.py` line 8: `release = '1.1.0'`
Current version per `pyproject.toml`: `1.3.0`.

Minor cosmetic, but the footer renders the wrong version. Fix as part of Defect 2's commit (touches same file).

### What's NOT broken (despite old task checklist)

| Old task claim | Reality at HEAD `6cb7ea9` |
|:---|:---|
| `project` not in api.rst | ✅ Present (line 14) |
| `security` not in api.rst | ✅ Present (line 20) |
| Need to "verify Cloudflare secrets" | ✅ Cannot verify from agent context; user-side task, listed in §5 below as a follow-up |

### Pre-existing out-of-scope items (NOT fixed in this task)

- `autodoc_mock_imports` in `conf.py` mocks real deps (pydantic, gitpython, etc.). The docs render fake class signatures, not the real ones. **Real fix**: install real deps (which Defect 1 enables), then remove the mock list. Doing this requires verifying each module's autodoc rendering — bigger scope than this task. **Deferred to a follow-up** because it changes rendered content meaningfully.
- `intersphinx_mapping` includes `gunz_ml` and `gunz_cm` URLs that probably don't resolve. Build warnings only. **Deferred.**
- `html_static_path = ['_static']` but `_static/` doesn't exist (warns at build). **Deferred.**

## 3. Approach

Three atomic commits, each independently revertable. Commits go in dependency order: Defect 1 first (CI install) → Defect 2 (theme + extras) → Defect 3 (release version, lumped with Defect 2 since it touches the same file).

Actually only **two commits**:
- **Commit 1**: Fix `.github/workflows/deploy_docs.yml` — change `'.[all]'` to `'.[docs]'`. One line.
- **Commit 2**: Sync `pyproject.toml` docs extra + `conf.py` release — drop `furo`, add `sphinx_rtd_theme`, bump `release` to `1.3.0`.

After both commits, the next push to `main` should successfully build the docs (modulo the deferred out-of-scope items above, which only produce warnings, not errors).

## 4. Implementation Plan

### Commit 1 — `fix(ci): install docs extra in deploy_docs workflow`

**File:** `.github/workflows/deploy_docs.yml` line 24

```diff
-          pip install '.[all]'
+          pip install '.[docs]'
```

**Why this works:**
- The `[docs]` extra declares `sphinx`, `myst-parser`, `sphinx-autodoc-typehints` (and after Commit 2, `sphinx_rtd_theme`). All consumed by `conf.py`.
- Without Commit 2 first, the build will fail at `sphinx_rtd_theme` import. So Commit 2 must land before Commit 1's effect is observable.

Wait — that means Commit 1 alone is broken. Reordering needed:
- Commit 1 first changes `'.[all]'` → `'.[docs]'`
- Commit 2 then adds `sphinx_rtd_theme` to the `[docs]` extra

If you push after only Commit 1, CI installs `.[docs]` but `sphinx_rtd_theme` isn't there yet → fails at theme import.
If you push after both commits, CI works.

**Final commit order:**
1. **Commit 1** — workflow file fix
2. **Commit 2** — pyproject + conf.py sync

Both must be pushed together for the workflow to succeed. Document this in the commit message.

**Steps:**
```bash
# Edit .github/workflows/deploy_docs.yml line 24:
#   pip install '.[all]'   →   pip install '.[docs]'
git add .github/workflows/deploy_docs.yml
git commit -m "fix(ci): install [docs] extra in deploy_docs workflow"
```

### Commit 2 — `chore(docs): align sphinx theme + bump release version`

**Files:**
- `pyproject.toml` `[project.optional-dependencies].docs`
- `docs/source/conf.py` line 8 (`release`)

**pyproject diff:**
```diff
 docs = [
     "sphinx",
-    "furo",
     "myst-parser",
     "sphinx-autodoc-typehints",
+    "sphinx_rtd_theme",
 ]
```

**conf.py diff:**
```diff
-release = '1.1.0'
+release = '1.3.0'
```

**Why both in one commit:** Both files need to land together for `pip install .[docs]` to find `sphinx_rtd_theme` and for the rendered site footer to show the correct version. Splitting them creates a state where either theme is broken or footer is wrong.

**Steps:**
```bash
# Edit pyproject.toml docs extra
# Edit docs/source/conf.py release
git add pyproject.toml docs/source/conf.py
git commit -m "chore(docs): align theme with pyproject; bump release to 1.3.0"
```

### Commit 3 — verification commit (optional, no changes)

If we want to verify the build runs locally:
```bash
# Requires docs deps installed locally
pip install '.[docs]'
bash scripts/build_docs.sh
# Verify docs/_build/html/index.html exists
```

**This is local verification only.** It does NOT change CI behavior — CI runs on Ubuntu runners without our local mamba env.

## 5. Out of Scope (deferred to follow-up tasks)

- **Phase 2 of original task**: Cloudflare secrets verification. Cannot be done from agent context. The user must verify manually via `https://github.com/sXperfect/gunz-utils/settings/secrets/actions` (Web UI) or `gh secret list` (CLI). Listed as a TODO in this task file but marked `pending-user-action`.
- **autodoc_mock_imports removal**: requires verification of rendered content for each module (enums, validation, project, security, models, secure_store, etc.). Bigger scope. File a follow-up.
- **Theme switch to furo**: explicitly rejected per user decision 2026-07-16. Dropped.
- **Static path warning** (`_static/` doesn't exist): trivial fix, deferred.

## 6. Verification

After both commits land:

1. **Locally (if `pip install .[docs]` works):**
   ```bash
   bash scripts/build_docs.sh
   ls docs/_build/html/index.html    # must exist
   ```
2. **On push to `main`:**
   - GitHub Actions `deploy_docs` job should run.
   - First step (`pip install '.[docs]'`) succeeds.
   - Second step (`./scripts/build_docs.sh`) succeeds with at most warnings (intersphinx, missing _static).
   - Third step (Cloudflare deploy) runs only if secrets `CLOUDFLARE_API_TOKEN` and `CLOUDFLARE_ACCOUNT_ID` are set in the repo.

## 7. Definition of Done

- [x] Commit 1 lands: workflow installs `.[docs]` — **`0494cfc`** ✅
- [x] Commit 2 lands: theme + release version aligned — **`6c88aa4`** ✅
- [x] Both commits pushed to `origin/main` — HEAD == origin/main == `6c88aa4` ✅
- [ ] GitHub Actions `deploy_docs` job runs successfully on the resulting push — **will auto-trigger on next push; verify in Actions UI**
- [ ] Cloudflare Pages site reflects the latest docs (verify at https://gunz-utils.pages.dev — user-side, requires `CLOUDFLARE_*` secrets to exist)

## 8. Pending User Actions (block DoD)

### 8.1 Verify `CLOUDFLARE_API_TOKEN` exists
**Web UI (canonical path):** `https://github.com/sXperfect/gunz-utils/settings/secrets/actions`

The repository secrets list will show names only. `CLOUDFLARE_API_TOKEN` must appear in the list.

**Via `gh` CLI (if installed):**
```bash
gh secret list --repo sXperfect/gunz-utils
```

### 8.2 Verify `CLOUDFLARE_ACCOUNT_ID` exists
Same URL as 8.1. Same `gh secret list` command.

### 8.3 Verify Cloudflare Pages project `gunz-utils` exists
**Cloudflare dashboard:** `https://dash.cloudflare.com/?to=/:account/pages`

The project name must match the `--project-name=gunz-utils` flag in `deploy_docs.yml` line 36.

### 8.4 Verify wrangler token has Pages deploy permission
The `CLOUDFLARE_API_TOKEN` must include the **Cloudflare Pages: Edit** permission scope. To check or update:
1. Cloudflare dashboard → My Profile → API Tokens
2. Find the token used for gunz-utils
3. Verify "Cloudflare Pages" appears under Permissions with "Edit" access

### 8.5 Caveats discovered during research

- **Secret VALUES are never visible** after creation — GitHub masks them. Only their names and existence are checkable.
- **Triggering a test deploy** currently requires pushing to `main` (workflow runs on push). To make test runs easier without polluting git history, the workflow could add `workflow_dispatch` as a trigger — deferred as a follow-up.
- **Even with secrets in place**, the first deploy after the workflow fix may produce warnings (intersphinx `gunz_ml`/`gunz_cm` URLs don't resolve; `_static/` static path doesn't exist). These are warnings, not errors.

### 8.6 Quick verification sequence (after next push)

1. `git push` (already done at `6c88aa4`)
2. Open `https://github.com/sXperfect/gunz-utils/actions/workflows/deploy_docs.yml`
3. Verify the latest run shows green (or red — but with `ModuleNotFoundError: No module named 'sphinx_rtd_theme'` etc. addressed)
4. If green, verify `https://gunz-utils.pages.dev` renders the new docs (footer should say `1.3.0` after Commit 2's release bump)
