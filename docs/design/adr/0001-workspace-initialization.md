# ADR-0001: Workspace Initialization — `AGENTS.md` and §7 Schema

**Status:** Accepted
**Date:** 2026-07-15
**Deciders:** Repo owner (Yeremia Gunawan Adhisantoso) with OpenCode (Sisyphus) assistance

## Context
The repository lacked the `AGENTS.md` Source-of-Truth file required by the
user-level Agentic Operating Protocol, and the `.hyperhedron/` symlink farm
was present but unintegrated with any on-disk schema. Legacy `.jules/`
configs (Bolt + Sentinel) existed but were no longer maintained.

## Decision
1. **Adopt the General Global Directory Schema (§7)** end-to-end:
   - `docs/design/{specs,definitions,adr,assets}/`
   - `docs/tasks/{pending,active,done}/`
   - `docs/templates/{TASK_PROGRAMMER,TASK_RESEARCHER,TASK_GENERAL}.md`
   - `scripts/{shell,tests}/`, `configs/`, `tmp/{logs,db}/`
2. **Migrate existing task notes** from a flat `tasks/` at the repo root
   into `docs/tasks/done/<YYYY-MM-DD>-<slug>.md`, preserving history.
3. **Author `AGENTS.md`** declaring mamba as the canonical environment
   manager, Python 3.11 floor, Hatchling build, Ruff lint/format, NumPy
   docstring style, and Conventional Commits.
4. **Purge `.jules/`** from working tree and git history (`git filter-branch`
   using a ref-stash since `git-filter-repo` was not installed).
5. **Seed `docs/design/definitions/`** with YAML stubs for the five main
   modules so future SRS documents have a structural anchor.

## Consequences
- Any future component added to `src/gunz_utils/` should grow a matching
  entry in `docs/design/definitions/` and (if its behavior needs
  specification) an SRS in `docs/design/specs/`.
- Authors working in the repo must follow the rules declared in
  `AGENTS.md`, especially regarding mamba env isolation, Conventional
  Commits, and the no-`type: ignore` mandate.
- The `tmp/` directory is fully gitignored (transient data).

## Alternatives Considered
- **Skip §7 schema and keep the loose `docs/` + `tasks/` from before:**
  Rejected — this is a small library, the discipline is cheap, and the
  schema makes agent onboarding trivial.
- **Use `uv` instead of mamba:** Rejected — mamba is the canonical manager
  in this user's setup; switching would force a developer-environment rewrite.
