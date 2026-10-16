# Task: Audit Repairs — Network Timeout, Dict Merge Depth, Streaming Bounds, and Style Suppressions

**Date:** 2026-10-17
**Role:** Programmer
**Component:** `gunz_utils.network`, `gunz_utils.dict_utils`, `gunz_utils.streaming`, `gunz_utils.ext.project_*`
**Status:** Done

## 1. Goal
Implement targeted correctness and safety enhancements identified in the deep audit scan:
1. Enforce cumulative deadline bounding in `tcp_reachable` across multi-homed / multi-IP address resolutions.
2. Guard `dict_utils.deep_merge` against stack overflow / `RecursionError` on deeply nested mappings with configurable depth limits.
3. Protect `streaming.iter_jsonl` from memory exhaustion via optional maximum line length validation.
4. Align `GS007` AST linter suppressions to same-line syntax in `project_gitpython.py` and `project_stdlib.py`.

## 2. Scope
### In Scope
- `src/gunz_utils/network.py`: Enforce cumulative `deadline = time.monotonic() + timeout` in `tcp_reachable` loop.
- `src/gunz_utils/dict_utils.py`: Add `max_depth: int | None = 100` parameter with depth validation to `deep_merge`.
- `src/gunz_utils/streaming.py`: Add `max_line_length: int | None = None` parameter to `iter_jsonl`.
- `src/gunz_utils/ext/project_gitpython.py` & `project_stdlib.py`: Fix `gunz-style: ignore[GS007]` same-line placement.
- `src/gunz_utils/enums.py`: Reject non-strings in `from_fuzzy_string` / `from_fuzzy_int_string`, normalize `__ALIASES__` keys and `BaseIntEnum` member-name separators, and reject `bool` in `BaseIntEnum.get_or_none` and `_max_input_length`.
- `src/gunz_utils/sync.py` & `src/gunz_utils/concurrency.py`: Reject bare `str`/`bytes` `extra_args`, control characters in `completion_marker`/`extra_args`, and non-boolean flags (`lock`, `delete`, `fallback_serial`).
- Regression tests for all new parameters and failure modes.
- Pass `gunz-style --staged`, Ruff, Mypy, and Pytest.
- Add changelog fragment in `changes/`.

### Out of Scope
- Breaking existing API defaults or contracts without deprecation.
- Adding third-party runtime dependencies.

## 3. Implementation Plan
1. Step 1 — `network.py`: Cumulative timeout in `tcp_reachable` + regression in `test_network.py`.
2. Step 2 — `dict_utils.py`: `max_depth` parameter in `deep_merge` + regression in `test_dict_utils.py`.
3. Step 3 — `streaming.py`: `max_line_length` in `iter_jsonl` + regression in `test_streaming.py`.
4. Step 4 — `ext/project_*.py`: Same-line `GS007` suppression.
5. Step 5 — `enums.py`, `sync.py`, `concurrency.py`: Input boundary and alias/separator normalization hardening.
6. Step 6 — Verify via `gunz-style`, Ruff, Mypy, Pytest, and release check.

## 4. Verification
- [x] `gunz-style --staged`
- [x] `ruff check src tests benchmarks scripts`
- [x] `mypy src/gunz_utils`
- [x] `pytest` (1788 passed, 11 skipped, 0 failed; down from 12 skipped via `/dev/fd` support)
- [x] `python scripts/release.py check`
- [x] `python scripts/verify_native.py` (91 passed)

## 5. Status
- **Started:** 2026-10-17
- **Completed:** 2026-10-17 (Status: Done)

