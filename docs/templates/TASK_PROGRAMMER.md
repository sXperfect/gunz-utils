# Task: <Short kebab-case title>

**Date:** YYYY-MM-DD
**Role:** Programmer
**Component:** `<component_slug>` (e.g. `gunz_utils.enums`)
**Status:** Pending → Active → Done

## 1. Goal
One-paragraph summary of what this task is delivering and **why**.

## 2. Scope
### In Scope
- Concrete deliverable 1
- Concrete deliverable 2

### Out of Scope
- Things explicitly NOT being done in this task

## 3. Approach
High-level plan. Reference specific files and patterns from `src/gunz_utils/`.
Use existing utilities when possible (per `AGENTS.md` §4.2 Reuse Mandate).

## 4. Implementation Plan
1. Step 1 — file + change
2. Step 2 — file + change
3. Step 3 — tests added/updated

## 5. Verification
- [ ] `ruff check src/ tests/`
- [ ] `ruff format --check src/ tests/`
- [ ] `mypy src/gunz_utils`
- [ ] `pytest tests/`
- [ ] `lsp_diagnostics` clean on changed files
- [ ] All existing tests still pass

## 6. Notes
Free-form notes, links to upstream issues, design tradeoffs, etc.

## 7. Status
- **Started:** YYYY-MM-DD
- **Completed:** YYYY-MM-DD
- **PR:** #<number>
