# Changelog

All notable changes to **gunz-utils** are documented in this file.

The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [1.3.2] — 2026-07-16

### Changed

- Documentation build pipeline aligned with `pyproject.toml`. The
  `docs` extra now declares `sphinx_rtd_theme` (matching `conf.py`)
  and no longer declares `furo`. Workflow installs `.[docs]`
  instead of `.[all]`, so CI can actually build the docs.
- `conf.py` `release` bumped to `1.3.0` (was stale at `1.1.0`).

### Added

- Compat shim at `src/gunz_utils/validation.py` re-exporting
  `type_checked` and `validate_call` from `ext.validation_pydantic`.
  Preserves the historical `from gunz_utils.validation import …`
  import path for callers that have not yet migrated to the v1.3.0
  `ext.*` layout.
- `[tool.ruff]` configuration in `pyproject.toml` (line-length 88,
  Pyflakes + pycodestyle + bugbear + isort + pyupgrade).

### Fixed

- `tests/test_project.py` (legacy 53-line flat test) collided with
  the new `tests/test_project/` package on the same module name,
  causing pytest to abort collection. The legacy file is removed;
  `tests/test_project/test_project.py` covers the same 6 scenarios.
- Four test files had redundant `# -*- coding: utf-8 -*-` headers
  stripped (`test_security_reserved.py`, `test_enums_security.py`,
  and the same pair under `tests/test_core/`).

### Removed

- Three dead-duplicate root-level source files left over from the
  v1.3.0 `ext.*` split: `src/gunz_utils/secure_store.py`,
  `src/gunz_utils/crypto.py`, `src/gunz_utils/logging.py`. None
  were reachable through the public package surface
  (lazy-import shim in `__init__.py` only exposes `ext.*` paths).
- Cloudflare Pages deploy step from the `deploy_docs` workflow.
  The CI now builds the docs to verify the build works, but does
  not upload them. `CLOUDFLARE_API_TOKEN` and `CLOUDFLARE_ACCOUNT_ID`
  are no longer consumed by any workflow.

## [1.3.1] — 2026-07-08

### Fixed

- `gunz_utils.__version__` reported `"1.1.0"` from a v1.3.0 install.
  Synced to `"1.3.0"` to match `pyproject.toml` and the v1.3.0 tag.

### Removed

- Four stale `__version__ = "1.0.0"` duplicates from `enums.py`,
  `security.py`, `ext.validation_pydantic`, and `ext.project_gitpython`.
  `__init__.py` is the canonical source now.

## [1.3.0] — 2026-06-29

### Added

- `loguru>=0.7.0` is now a declared runtime dependency, matching its
  two import sites (`gunz_utils.project`, `gunz_utils.logging`).
- `[project.optional-dependencies]` groups: `validation`,
  `project`, `observability`, `secure`, `all`, plus the existing
  `docs` group. Allows narrower installs of the heavy bundles.
- `[dependency-groups]` (PEP 735): `dev`, `test`, `lint` for dev/CI.
- New module `gunz_utils.ext.*` for explicit backend selection:
  - `ext.validation_pydantic` — `type_checked` (pydantic backend,
    default).
  - `ext.validation_stdlib`   — `type_checked` (stdlib fallback).
  - `ext.project_gitpython`   — `resolve_project_root` (gitpython +
    loguru, default).
  - `ext.project_stdlib`      — `resolve_project_root` (stdlib path
    walk + git rev-parse fallback).
  - `ext.observability_loguru`, `ext.observability_stdlib`,
    `ext.secure_crypto`, `ext.secure_store`.
- `gunz_utils.__init__` re-exports `UpstreamClient`, `BaseUpstream`,
  and the four `UpstreamError` subclasses from the new
  `upstream_protocol` module.

### Fixed

- `__init__.py` was previously frozen at `__version__ = "1.0.0"` and
  did not re-export the post-v1.0.0 modules. Both corrected.

## [1.1.0] — 2026-06-29

Added `gunz_utils.crypto`, `gunz_utils.logging`, `gunz_utils.models`,
`gunz_utils.secure_store`, `gunz_utils.upstream_protocol` and the
`cryptography>=42.0.0`, `gitpython>=3.1.0` runtime deps.

## [1.0.0] — 2026-06-29

Initial BSD-3 release with `BaseStrEnum`, `BaseIntEnum`,
`OptionalBaseStrEnum`, `sanitize_filename`, `safe_path_join`,
`type_checked`, `resolve_project_root`.
