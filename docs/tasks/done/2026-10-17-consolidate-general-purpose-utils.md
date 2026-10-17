# General-Purpose Utilities Consolidation & Release Tooling Hardening

**Date:** 2026-10-17
**Status:** Complete — consolidated general utilities from sibling repositories, hardened release tooling, and verified across all gates
**Predecessors:** [2026-10-17 audit network, dict, streaming fixes](2026-10-17-audit-network-dict-streaming-fixes.md)

## Summary of Changes

1. **Consolidated General Utilities**:
   - `gunz_utils.io.read_regular_bytes`: TOCTOU-safe regular file reading with `O_NOFOLLOW`, maximum size limits (`max_bytes`), and pre/post-read stat `st_ino`/`st_dev` identity verification.
   - `gunz_utils.serialization.decode_json_object` and `load_json_object`: Strict JSON decoding rejecting duplicate dictionary keys, non-finite floats, non-UTF8 encodings, and deeply nested payloads (default depth limit 64).
   - `gunz_utils.stats`: Descriptive statistics suite (`SummaryStats`, `percentile`, `median_absolute_deviation`, `mad_outlier_indices`, `summarize`) for robust data summarization and outlier detection.
   - `gunz_utils.formatting`: Terminal presentation utilities (`escape_terminal`, `supports_color`) supporting `NO_COLOR` and `FORCE_COLOR` standards.
2. **Unified Release Tooling (`scripts/release.py`)**:
   - Multi-repo auto-discovery with `--root <path>`.
   - Heading injection prevention rejecting ATX and Setext headers and git conflict markers in fragment files.
   - Transactional rollback on fragment unlinking failures.
   - Fragment git branch gating via `check-fragment --base <rev>`.
3. **Verification**:
   - 35 workflow tests added in `tests/test_core/test_release_workflow.py`.
   - Full test suites added for `io`, `serialization`, `stats`, and `formatting`.
   - All canonical gates pass: `gunz-style`, `ruff`, `mypy`, `pytest` (1,846 passed), `release.py check`.
