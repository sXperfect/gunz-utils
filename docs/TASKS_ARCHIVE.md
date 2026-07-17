# Task Archive

Historical record of completed tasks for the `gunz-utils` project. Detailed
files for each task live under `docs/tasks/done/`.

| Task ID | Date | Description | Status |
|:---:|:---:|:---|:---:|
| [2024-05-24-windows-reserved](tasks/done/2024-05-24-security-fix_windows_reserved_filenames.md) | 2024-05-24 | Fix Windows Reserved Filenames Vulnerability in `sanitize_filename` | Done |
| [2025-02-18-safe-path-join](tasks/done/2025-02-18-security-add_safe_path_join.md) | 2025-02-18 | Add `safe_path_join` security utility to prevent path traversal | Done |
| [2025-02-18-reserved-replacement](tasks/done/2025-02-18-security-fix_reserved_filename_replacement.md) | 2025-02-18 | Fix bypass of reserved filename check via empty `replacement` | Done |
| [2025-02-18-dos-enum](tasks/done/2025-02-18-enums-fix_dos_input_length.md) | 2025-02-18 | DoS protection in Enum utilities via input length validation | Done |
| [2025-10-18-fuzzy-lookup](tasks/done/2025-10-18-enums-perf_optimize_fuzzy_lookup.md) | 2025-10-18 | Optimize `BaseStrEnum` fuzzy matching by caching raw values | Done |
| [2025-10-27-enum-access](tasks/done/2025-10-27-enums-perf_optimize_attribute_access.md) | 2025-10-27 | Optimize Enum attribute access (`__ALIASES__`, lazy maps) | Done |
| [2025-12-24-leak](tasks/done/2025-12-24-validation-fix_prevent_information_leakage.md) | 2025-12-24 | Prevent information leakage in `type_checked` validation errors | Done |
| [2026-07-01-deps-split](tasks/done/2026-07-01-build-deps_split_v1.3.0.md) | 2026-07-01 | v1.3.0 dependency split: `gunz_utils.ext.*` modules with stdlib fallbacks, CI job matrix, test reorganization | Done |
| [2026-07-15-tier1-cleanup](tasks/done/2026-07-15-protocol-tier1_cleanup_housekeeping.md) | 2026-07-15 | Tier 1 cleanup housekeeping: ruff config, delete dead-duplicate src files, validation compat shim, delete legacy flat test, delete orphan tag | Done |
| [2026-04-28-test-improvements](tasks/done/2026-04-28-gunz_utils-test_improvements.md) | 2026-07-16 | Test improvements: dedicated `project.py` tests, comprehensive `validation.py` coverage, encoding-header cleanup. Archived with two defect-fix commits (`67f108b` legacy flat test removal + `12f4240` encoding-header strip) | Done |
| [2026-04-28-docs-improvement](tasks/done/2026-04-28-gunz_utils-docs_improvement.md) | 2026-07-16 | Original docs-improvement checklist (Phase 1 api.rst coverage) — replaced by [`2026-07-16-docs-pipeline-repair`](tasks/active/2026-07-16-docs-pipeline-repair.md) after forensic review found `deploy_docs.yml` was installing `.[all]` instead of `.[docs]`, breaking CI on every push | Done (replaced) |
