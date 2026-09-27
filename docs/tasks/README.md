# Task Records

Task records document substantial engineering work without making historical
notes part of the current contributor policy.

## Directories

- `active/`: work that is currently in progress.
- `pending/`: accepted work that has not started.
- `done/`: immutable historical records for completed or superseded work.

The current active index is [`docs/TASKS.md`](../TASKS.md). Completed records
are indexed in [`docs/TASKS_ARCHIVE.md`](../TASKS_ARCHIVE.md).

## Historical-record rule

Files under `done/` preserve the state and reasoning that existed when the work
was performed. They may mention removed agent tooling, old CI layouts, obsolete
paths, superseded dependency policies, or commands that should no longer be
used.

Do not derive current repository policy from an archived task. Current policy is
defined by:

1. executable configuration such as `pyproject.toml`, `.github/workflows/`, and repository scripts;
2. [`CONTRIBUTING.md`](../../CONTRIBUTING.md);
3. [`AGENTS.md`](../../AGENTS.md) for agent-facing operational rules;
4. maintained documentation under `docs/source/`, `docs/development/`, `docs/design/`, and `docs/guides/`.

## Naming

Prefer a date-prefixed, descriptive filename:

```text
YYYY-MM-DD-<scope>-<short-description>.md
```

Existing historical names are preserved rather than renamed solely for style.

## Completion

When a task is complete:

1. record verification evidence and any known follow-up work;
2. move the task file to `done/`;
3. remove it from the active table in `docs/TASKS.md`;
4. add it to `docs/TASKS_ARCHIVE.md`.

Do not copy large implementation details into the archive index; the task file
itself is the durable record.
