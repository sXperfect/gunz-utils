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

1. [`CONTRIBUTING.md`](../../CONTRIBUTING.md);
2. current configuration such as `pyproject.toml` and `.github/workflows/`;
3. maintained documentation under `docs/source/` and `docs/development/`.

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
