# Task Index

Active and pending tasks for the `gunz-utils` project. Done/archived tasks live in
[`docs/TASKS_ARCHIVE.md`](TASKS_ARCHIVE.md). Detailed files for each task live
under `docs/tasks/{pending,active,done}/`.

| Task ID | Date | Description | Status |
|:---:|:---:|:---|:---:|
| [ruff-format-hash-question-conflict](tasks/pending/2026.08.26-protocol-ruff_format_hash_question_conflict.md) | 2026-08-26 | Decide/resolve the `ruff format` ↔ `#?` convention conflict (update AGENTS.md §2.6) | Pending |
| [ci-mypy-gate](tasks/pending/2026.08.26-protocol-ci_mypy_gate.md) | 2026-08-26 | Add `mypy` job to `.github/workflows/ci.yml` so type regressions block merges | Pending |
| [ci-pytest-gate](tasks/pending/2026.08.26-protocol-ci_pytest_gate.md) | 2026-08-26 | Add unified `pytest` job running `.[all]` for cross-extra integration coverage | Pending |
| [ci-ruff-format-gate](tasks/pending/2026.08.26-protocol-ci_ruff_format_gate.md) | 2026-08-26 | Conditional: add `ruff format --check` CI job if upstream convention task permits | Pending |

> Last archived: [`2026-08-06-add-hashing`](tasks/done/2026-08-06-add-hashing.md) (and 2 sibling tasks: dict-utils, iteration) (2026-08-06) — added 3 new utility modules (hashing, dict_utils, iteration). 5 commits landed, v1.8.0 release. Test count: 206 → 330 (+124).
