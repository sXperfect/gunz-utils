# [ACTIVE]: gunz-utils Test Improvements

## Goal
Improve gunz-utils unit tests for better coverage and remove unnecessary encoding headers.

## Issues Found

### Missing Tests
- [ ] `project.py` - `resolve_project_root` has no tests
- [ ] `validation.py` - Only 2 basic tests, missing edge cases

### Code Quality Issues
- [ ] Remove unnecessary `# -*- coding: utf-8 -*-` headers from test files (test_enums.py, test_security.py, test_validation.py, test_validation_leak.py)

## Definition of Done
- [x] All 52 tests pass
- [x] `project.py` has dedicated tests (6 tests)
- [x] `validation.py` has comprehensive coverage (9 tests)
- [x] No unnecessary encoding headers in test files