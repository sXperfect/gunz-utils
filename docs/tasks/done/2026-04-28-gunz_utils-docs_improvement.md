# [REPLACED 2026-07-16]: gunz-utils Documentation Improvement

**Status:** Superseded by [`docs/tasks/active/2026-07-16-docs-pipeline-repair.md`](../active/2026-07-16-docs-pipeline-repair.md).

The original 2026-04-28 checklist was stale by 2026-07-16:

| Original claim | Reality at HEAD `6cb7ea9` |
|:---|:---|
| `project` not in api.rst | ✅ Present (api.rst line 14) |
| `security` not in api.rst | ✅ Present (api.rst line 20) |
| Need to verify Cloudflare secrets | ✅ Correct, but the workflow itself was broken in ways this task didn't enumerate |

The new task file at `docs/tasks/active/2026-07-16-docs-pipeline-repair.md` covers the real defects discovered during forensic review:

1. `deploy_docs.yml` installs `.[all]` instead of `.[docs]` → CI fails at `sphinx-build` import on every push.
2. `conf.py` uses `sphinx_rtd_theme` but `pyproject.toml` declares `furo` (user chose to keep `sphinx_rtd_theme`).
3. `conf.py` `release = '1.1.0'` is stale (current is `1.3.0`).

Three out-of-scope items moved to follow-up tasks:

- Remove `autodoc_mock_imports` from `conf.py` (requires per-module verification of rendered content).
- Fix `_static/` static-path warning.
- Phase 2 Cloudflare secrets verification (user-side action, cannot be done from agent context).

## Original checklist (archived for traceability)

### Phase 1: Add Missing Modules to api.rst
- [x] Add `project` module documentation
- [x] Add `security` module documentation

### Phase 2: CI/CD Verification for Cloudflare Pages
- [ ] Verify `CLOUDFLARE_API_TOKEN` secret is set in GitHub repo (user-side, pending)
- [ ] Verify `CLOUDFLARE_ACCOUNT_ID` secret is set in GitHub repo (user-side, pending)
- [ ] Trigger a test deploy or check recent deploy logs (blocked on CI fix in new task)

### Phase 3: Optional Enhancements
- [x] ~~Consider updating theme from `sphinx_rtd_theme` to `furo`~~ — rejected by user 2026-07-16

## Definition of Done (original)

- [x] `api.rst` documents all four modules: enums, validation, project, security
- [ ] CI deploy_docs workflow passes on main branch push → **blocked by defect, see new task**
- [ ] Cloudflare Pages site reflects latest docs → **blocked by defect + secrets, see new task**
