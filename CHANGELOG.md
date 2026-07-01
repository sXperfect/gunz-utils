# Changelog

All notable changes to **gunz-utils** are documented in this file.

The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

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
