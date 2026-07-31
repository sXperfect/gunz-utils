# Changelog

All notable changes to **gunz-utils** are documented in this file.

The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [1.6.0] — 2026-07-16

### Removed

- `gunz_utils.HealthStatus` (MCP server health-check response
  model). The class was added in v1.3.0 as part of the public
  API but was never used internally and is too domain-specific
  for a foundational utilities library. Downstream consumers
  that need this functionality should define their own
  response model:

```python
# Before (v1.5.x and earlier)
from gunz_utils import HealthStatus

# After (v1.6.0+) — define in your own codebase
from pydantic import BaseModel
class HealthStatus(BaseModel):
    status: str = "UNKNOWN"
    # ... your fields here
```

## [1.5.0] — 2026-07-16

### Changed

- Two callers migrated from the `gunz_utils.validation` compat shim
  to the canonical `gunz_utils.ext.validation_pydantic` path:
  - `tests/test_validation_leak.py` (line 2)
  - `docs/source/quickstart.md` (line 37)
- `docs/_build/` Sphinx build artifacts no longer tracked in git.
  87 files that were committed in `82d78df` are now untracked.
  The `.gitignore` line `docs/_build/` was already correct; only the
  pre-existing tracked state needed cleanup. Local builds still
  produce artifacts in `docs/_build/` (gitignored) as before.

### Removed

- **`src/gunz_utils/validation.py`** — backwards-compat shim originally
  added in v1.3.0 (commit `59ec712`) to preserve the historical
  `from gunz_utils.validation import ...` import path during the
  ext.* split. Now dead code (all callers migrated). **Breaking
  change** for external consumers still using the legacy path —
  migrate to `from gunz_utils.ext.validation_pydantic import ...`
  or `from gunz_utils import type_checked, validate_call` (the
  latter works via the `_LAZY` dict in `__init__.py`).

## [1.4.0] — 2026-07-16

### Added

- `GunzBaseModel` — shared Pydantic v2 base class in
  `src/gunz_utils/models.py`. Encapsulates the strictness defaults
  that every HyperHedron domain model should inherit:
  `extra="forbid"`, `str_strip_whitespace=True`,
  `validate_assignment=True`. Re-exported as
  `from gunz_utils import GunzBaseModel` and added to `__all__`.
- `tests/test_core/test_models.py` — 16 unit tests covering
  `GunzBaseModel` configuration, behavior, subclass override, and
  the public API re-export. Test count: 81 → 97.

### Fixed

- `HealthStatus()` no-arg construction now succeeds; the `status`
  field defaults to `"UNKNOWN"` (a sentinel for "not yet checked")
  instead of raising `ValidationError`. Two regression tests added
  to pin the new behavior. Test count: 97 → 99.
- Six `except` clauses now chain their raised exceptions with
  `from exc` (B904). Catches were previously unnamed or lacked the
  explicit `from` clause, which suppressed the original cause.
- Ruff auto-fix pass on 39 issues: unsorted imports (19), blank
  lines with trailing whitespace (11), missing newlines at end of
  file (5), `setattr` with constant (4).

### Changed

- Python v6.0 compliance sweep: 13 modules now have the full
  dunder block (`__author__`, `__email__`, `__license__`,
  `__version__ = "1.4.0"`); 3 files had `# -*- coding: utf-8 -*-`
  removed; 4 files had `t.Optional` / `typing.Optional` /
  `typing.Dict` replaced with modern `X | None` / `dict[str, Any]`
  syntax.
- Ruff line-length enforcement is now satisfied:
  `ruff check src/ tests/` reports 0 issues across the codebase.
  36 line-too-long (E501) violations were fixed via line wrapping
  and implicit string concatenation.

### Removed

- **CI**: `deploy_docs.yml` no longer uploads to Cloudflare
  Pages (the step was removed entirely). Both `ci.yml` and
  `deploy_docs.yml` triggers are pinned to the sentinel branch
  `never`, so GitHub Actions no longer runs on push or pull
  request. Local CI via [`act`](https://github.com/nektos/act)
  remains the supported workflow.

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
