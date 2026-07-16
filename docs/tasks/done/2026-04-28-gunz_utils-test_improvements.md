# [DONE]: gunz-utils Test Improvements

## Goal
Improve gunz-utils unit tests for better coverage and remove unnecessary encoding headers.

## Issues Found (original)

### Missing Tests
- [x] `project.py` - `resolve_project_root` has no tests → covered in `tests/test_project/test_project.py` (6 tests)
- [x] `validation.py` - Only 2 basic tests, missing edge cases → covered in `tests/test_validation/test_validation.py`

### Code Quality Issues
- [x] Remove unnecessary `# -*- coding: utf-8 -*-` headers from test files (test_enums.py, test_security.py, test_validation.py, test_validation_leak.py)

## Definition of Done (verified 2026-07-16 at HEAD `12f4240`)

- [x] All 52 tests pass → **actual: 81 tests + 4 subtests pass** (count grew because v1.3.0 ext.* split added new coverage)
- [x] `project.py` has dedicated tests (6 tests)
- [x] `validation.py` has comprehensive coverage (9 tests)
- [x] No unnecessary encoding headers in test files

## Cleanup landed in this task

Two defects were discovered during verification (the original DoD was
prematurely marked `[x]`). Both fixed before archiving:

1. **Delete legacy `tests/test_project.py`** (commit `67f108b`)
   - 53-line flat file collided with `tests/test_project/` package on the
     same module name `test_project`, causing pytest to abort collection.
   - New package covers the same 6 scenarios; verified locally before deletion.
2. **Strip `# -*- coding: utf-8 -*-` from 4 test files** (commit `12f4240`)
   - `tests/test_security_reserved.py`
   - `tests/test_enums_security.py`
   - `tests/test_core/test_security_reserved.py`
   - `tests/test_core/test_enums_security.py`
   - PEP 263 declaration is redundant for Python 3 source files.

## Final verification

```
$ pytest tests/ -q
.................................................................... [ 83%]
.............                                                            [100%]
81 passed, 4 subtests passed in 1.34s
```

Zero collection errors, zero warnings, zero encoding headers anywhere
under `tests/`.

## Outcome

Task archived 2026-07-16 as Done. The repository test suite is now
green from a clean checkout, and the test-reorganization arc started
in commit `4ad23cb` is fully resolved.