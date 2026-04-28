# [ACTIVE]: gunz-utils Python v6.0 Compliance Fixes

## Goal
Fix gunz-utils code to comply with python-v6_0.md best practices guide.

## Issues Found

### security.py
- [ ] Remove unnecessary `# -*- coding: utf-8 -*-` (Python 3 doesn't need this)
- [ ] Add section separator headers (`# ==== ... ====`)
- [ ] Add module metadata block (\_\_author\_\_, \_\_email\_\_, \_\_license\_\_, \_\_version\_\_)
- [ ] Add `#?` explanatory comments for non-obvious logic

### validation.py
- [ ] Replace `t.Optional` with modern `| None` syntax
- [ ] Add module metadata block
- [ ] Add `#?` explanatory comments for non-obvious logic

### project.py
- [ ] Add `__license__` to metadata block (currently has `__author__`, `__version__` only)

### enums.py
- [ ] Add `__license__` to metadata block (currently has `__author__`, `__email__`, `__version__` only)

### conf.py (optional)
- [ ] Add intersphinx mapping for gunz_cm and gunz_ml if needed

## Definition of Done
- [ ] All modules use modern `| None` syntax (not `t.Optional`)
- [ ] All modules have complete metadata blocks
- [ ] security.py follows section header conventions
- [ ] Non-obvious logic has `#?` explanatory comments