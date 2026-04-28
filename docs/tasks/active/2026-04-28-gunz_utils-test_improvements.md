# [ACTIVE]: gunz-utils Test Improvements

## Goal
Improve gunz-utils unit tests for better coverage and remove unnecessary encoding headers.

## Issues Found

### Missing Tests
- [ ] `project.py` - `resolve_project_root` has no tests
- [ ] `validation.py` - Only 2 basic tests, missing edge cases

### Code Quality Issues
- [ ] Remove unnecessary `# -*- coding: utf-8 -*-` headers from test files (test_enums.py, test_security.py, test_validation.py, test_validation_leak.py)

## Proposed Improvements

### 1. Add `project.py` tests
- Test `resolve_project_root` finds correct git root
- Test caching behavior (_PROJECT_ROOT global)
- Test sys.path injection
- Test error on non-git directory

### 2. Expand `validation.py` tests
- Multiple argument validation failures
- Error message formatting
- Custom pydantic config passing
- Edge cases (empty args, None values)

### 3. Expand `security.py` tests
- `safe_path_join` edge cases (symlinks, relative paths, multiple path components)
- More path traversal scenarios

### 4. Remove encoding headers
- Remove `# -*- coding: utf-8 -*-` from all test files

## Definition of Done
- [ ] All 40+ tests pass
- [ ] `project.py` has dedicated tests
- [ ] `validation.py` has comprehensive coverage
- [ ] No unnecessary encoding headers in test files