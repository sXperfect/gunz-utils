# `gunz-utils` Dep-Split Plan (v1.3.0)

Status: **Executed** as v1.3.0 — released 2026-07-01 (tag `v1.3.0` → merge `e89dd5c`).
Phases P0–P4 merged to `main` across commits `0297b01` → `e5495cb`; P5 (tag+push) applied.
Subsequent patch v1.3.1 (`f52c04e`) fixed `__version__` drift and removed stale duplicate `__version__` declarations.
Baseline: `main` at `d8c702d` (v1.1.0) on 2026-06-29.
Target release: **v1.3.0** (skipping 1.2.0 because there is no breaking change
at the public surface — same docstrings, same callable signatures; only the
import-time dep exposure changes).
Branch: `feat/deps-split` from current `main@d8c702d`. Phases commit linearly
in order: P0 → P1 → P2 → P3 → P4. Each commit is self-contained and revertable.

---

## 1. Current state (verified at v1.1.0)

Public modules and their hard third-party deps on `main@d8c702d`:

| Module | Third-party deps | In `__init__.py`? |
|---|---|---|
| `enums.py` | — | yes (`BaseStrEnum`, `BaseIntEnum`, `OptionalBaseStrEnum`) |
| `security.py` | — | yes (`sanitize_filename`, `safe_path_join`) |
| `upstream_protocol.py` | — (stdlib only) | **no** (only reachable via submodule) |
| `models.py` | `pydantic` | **no** |
| `validation.py` | `pydantic` | yes (`type_checked`) |
| `project.py` | `gitpython`, `loguru` | yes (`resolve_project_root`) |
| `logging.py` | `loguru` | **no** |
| `crypto.py` | `cryptography` | **no** |
| `secure_store.py` | `cryptography` (+ stdlib `sqlite3`) | **no** |

`pyproject.toml` declares:

```toml
dependencies = [
    "pydantic>=2.0.0",
    "cryptography>=42.0.0",
    "gitpython>=3.1.0",
]
```

**`loguru` is still undeclared** despite being imported by both
`project.py` and `logging.py`. The most recent commit `d8c702d` (the one
that closes the gitpython declaration) is incomplete; `loguru` is the
remaining hole.

`__init__.py` is also stale: it imports/re-exports only the original 5
names and still carries `__version__ = "1.0.0"` even though the package
is now at v1.1.0 with 4 new public modules not exported at the top
level. New public imports must still go through `from gunz_utils.X
import …`, which is functional but loses the discoverability that the
prior PR-A work tried to fix.

CI is currently `pip install .` (no extras) running `unittest discover
tests`. There is no test selection by feature.

---

## 2. Goal (re-scoped to v1.3.0)

Same family of outcomes as the v1.0.0-era plan, narrowed against the
actual v1.1.0 surface:

1. **Declare `loguru`** so `pip install gunz-utils` actually works.
2. **Group heavy third-party deps under named optional extras** so users
   who don't need them don't have to install them:
   - `[secure]` → `cryptography` (for `crypto`, `secure_store`,
     `upstream_protocol` is stdlib and stays free)
   - `[validation]` → `pydantic` (unchanged from prior plan)
   - `[project]` → `gitpython` + `loguru` (for `project`)
   - `[observability]` → `loguru` (for `logging`)
   - `[all]` → union of the above
3. **Stdlib fallbacks for two modules** — the prior plan's full v2.0.0
   thesis was to split every dep-bundled module. Rescoping to v1.3.0:
   only the two modules with clean stdlib alternatives get them:
   - `resolve_project_root`: gitpython backend stays default, but a
     new `gunz_utils.ext.project_stdlib.resolve_project_root` path
     becomes the zero-cost option for users who install
     `pip install gunz-utils` (no extras).
   - `type_checked`: pydantic backend stays default. A new
     `gunz_utils.ext.validation_stdlib.type_checked` becomes
     available. `from gunz_utils import type_checked` still uses
     pydantic (zero default-API breakage). The stdlib path is the
     install-needed-for-it fallback, mirroring the pydantic
     `[email]` precedent.
4. **Lazy `__init__.py` (PEP 562 `__getattr__`)** so `import gunz_utils`
   no longer pulls all four deps transitively.
5. **Sync `__init__.py`'s `__version__` and `__all__`** with the new
   module set; re-export the secure/observability/upstream-protocol
   names so they're discoverable.
6. **No breaking change at the docstring level.** Public callables
   keep identical signatures; only optional/extra-driven behavior and
   import-time cost change.

`pip install gunz-utils` after v1.3.0 still installs `pydantic +
cryptography + gitpython + loguru`. The split buys:
- a clean dependency surface (every runtime import is declared),
- the ability to install lighter subsets (`gunz-utils[validation]`
  gives you `pydantic` and `_stdlib` paths for everything else),
- and a Pythonic escape hatch (`from gunz_utils.ext.*` for power users).

---

## 3. Verified precedents (re-collected for v1.1.0 context)

1. **Pydantic's own extras** — `email`, `timezone` in
   `[project.optional-dependencies]` with `try/except ImportError` at
   function-call time. ([pydantic/networks.py:991-997](https://github.com/pydantic/pydantic/blob/main/pydantic/networks.py#L991-L997))
2. **stdlib git-root walk** — PyTorch's `lintrunner.py`, NVIDIA's
   `warp/list_contributors.py`, servo's `vcs.py`. Walk-up
   `.git`/`pyproject.toml` then `subprocess.run(["git", "rev-parse",
   "--show-toplevel"])`.
3. **stdlib-only type_checked** — `inspect.signature` + `isinstance`
   against `typing.get_type_hints(func)` covers the parameter shapes
   the existing `test_validation*.py` exercises. The error shape must
   match `Argument '<name>': <msg> (got type '<type>')`.
4. **PEP 562 `__getattr__` lazy module attrs** — official since Python
   3.7; pandas / urllib3 / requests use it.
5. **PEP 735 `[dependency-groups]`** — zarr-python and Qiskit use
   `dev`, `test`, `lint` groups there. Keep user-facing extras in
   `[project.optional-dependencies]`.

---

## 4. Target layout

```
src/gunz_utils/
    __init__.py                  # PEP 562 lazy __getattr__ + eager stdlib re-exports
    enums.py                     # stdlib only — unchanged
    security.py                  # stdlib only — unchanged
    upstream_protocol.py         # stdlib only — unchanged (re-export from __init__.py)
    models.py                    # pydantic — kept here (small)
    ext/
        __init__.py              # re-exports all extra backends
        validation_pydantic.py   # moved out of validation.py (pydantic backend)
        validation_stdlib.py     # NEW — stdlib type_checked
        project_gitpython.py     # moved out of project.py (gitpython+loguru backend)
        project_stdlib.py        # NEW — stdlib path-walk backend
        observability_loguru.py  # moved out of logging.py (loguru backend)
        observability_stdlib.py  # NEW — stdlib logging handler for setup_logging shape
        secure_crypto.py         # moved out of crypto.py
        secure_store.py          # moved out of secure_store.py

# The legacy top-level validation.py / project.py / logging.py / crypto.py /
# secure_store.py modules are removed in PR P1 — their public names
# (`type_checked`, `resolve_project_root`, `setup_logging`, `encrypt`,
# `decrypt`, `get_derived_key`, `get_system_passphrase`, `SecureStore`,
# `SecretMetadata`) are re-exported from __init__.py via the lazy
# `__getattr__` indirection so existing `from gunz_utils import X`
# continues to work.
```

`gunz_utils.ext.*` are the *explicit* opt-in paths. Users who want the
stdlib backend write `from gunz_utils.ext.validation_stdlib import
type_checked` instead of getting the pydantic one by default.

---

## 5. `__init__.py` (lazy)

```python
"""Shared low-level python utilities for the Gunz ecosystem."""

# Eager imports: stdlib-only modules (zero third-party cost).
from .enums import BaseStrEnum, BaseIntEnum, OptionalBaseStrEnum
from .security import sanitize_filename, safe_path_join
from .upstream_protocol import (
    UpstreamClient, BaseUpstream,
    UpstreamError, UpstreamTimeoutError,
    UpstreamAuthError, UpstreamNotFoundError,
    UpstreamUnavailableError,
)

__version__ = "1.3.0"

# Lazy map: third-party-backed names are NOT imported at top-level.
_LAZY = {
    # validation
    "type_checked":                   ".ext.validation_pydantic",
    # project
    "resolve_project_root":          ".ext.project_gitpython",
    # observability
    "setup_logging":                  ".ext.observability_loguru",
    # secure
    "encrypt":                        ".ext.secure_crypto",
    "decrypt":                        ".ext.secure_crypto",
    "get_derived_key":                ".ext.secure_crypto",
    "get_system_passphrase":          ".ext.secure_crypto",
    "SecureStore":                    ".ext.secure_store",
    "SecretMetadata":                 ".ext.secure_store",
    # models (small, single-class pydantic module — kept eager-friendly via lazy map)
    "HealthStatus":                   ".models",
}

def __getattr__(name: str):                       # PEP 562
    if name not in _LAZY:
        raise AttributeError(f"module 'gunz_utils' has no attribute {name!r}")
    import importlib
    return getattr(importlib.import_module(_LAZY[name], __name__), name)


__all__ = [
    # stdlib core
    "BaseIntEnum", "BaseStrEnum", "OptionalBaseStrEnum",
    "sanitize_filename", "safe_path_join",
    # upstream protocol (stdlib)
    "UpstreamClient", "BaseUpstream",
    "UpstreamError", "UpstreamTimeoutError",
    "UpstreamAuthError", "UpstreamNotFoundError",
    "UpstreamUnavailableError",
    # lazy / extras
    "type_checked", "resolve_project_root", "setup_logging",
    "encrypt", "decrypt", "get_derived_key", "get_system_passphrase",
    "SecureStore", "SecretMetadata", "HealthStatus",
    # version
    "__version__",
]
```

Net effect: `import gunz_utils` requires *only* `pydantic` to be installed
*if the user reaches into `_LAZY[validation]`-mapped attributes at any
point*. `pydantic`, `cryptography`, `gitpython`, `loguru` are all
declared in `dependencies`, so `pip install gunz-utils` brings them
in. Lazy `__getattr__` is therefore mostly an optional-future-proofing
mechanism that lets us later move any of those into extras without a
breaking change.

---

## 6. Stdlib fallbacks

### 6.1 `ext/project_stdlib.resolve_project_root`

Algorithm:
1. Walk up from `anchor` looking for `.git` / `pyproject.toml`.
2. Fallback: `subprocess.run(["git", "rev-parse", "--show-toplevel"])`.
3. If neither finds it, raise `RuntimeError`.

```python
import pathlib, subprocess, sys

_PROJECT_ROOT: pathlib.Path | None = None

def resolve_project_root(anchor=".", inject_to_sys_path=True):
    global _PROJECT_ROOT
    if _PROJECT_ROOT is not None:
        return _PROJECT_ROOT

    start = pathlib.Path(anchor).resolve()
    root: pathlib.Path | None = None

    # 1. Walk up looking for .git / pyproject.toml
    for candidate in (start, *start.parents):
        if (candidate / ".git").exists() or (candidate / "pyproject.toml").exists():
            root = candidate.resolve()
            break

    # 2. subprocess fallback
    if root is None:
        try:
            r = subprocess.run(
                ["git", "rev-parse", "--show-toplevel"],
                capture_output=True, text=True, check=True,
                timeout=5,
            )
            root = pathlib.Path(r.stdout.strip()).resolve()
        except (subprocess.CalledProcessError, subprocess.TimeoutExpired, FileNotFoundError):
            raise RuntimeError(
                "Could not find project root. Pass an explicit `anchor` "
                "or run inside a git repository."
            )

    _PROJECT_ROOT = root
    if inject_to_sys_path and str(root) not in sys.path:
        sys.path.insert(0, str(root))
    return root
```

Behavior parity targets with the existing `tests/test_project.py`:
- returns `pathlib.Path` with absolute path,
- injects into `sys.path[0]` when `inject_to_sys_path=True`,
- raises `RuntimeError` on failure,
- uses a single-call cache.

### 6.2 `ext/validation_stdlib.type_checked`

```python
import functools, inspect, typing as t

def _check(value, annotation) -> bool:
    origin = t.get_origin(annotation)
    if origin is None:
        try:
            return isinstance(value, annotation)
        except TypeError:
            return True  # can't introspect — assume ok
    if origin is t.Union:
        return any(_check(value, arg) for arg in t.get_args(annotation))
    if origin in (list, dict, tuple, set, frozenset):
        return isinstance(value, origin)
    return True  # unknown generic — don't fail


def type_checked(func=None, **kwargs):
    def decorator(f):
        sig = inspect.signature(f)

        @functools.wraps(f)
        def wrapper(*args, **kw):
            bound = sig.bind_partial(*args, **kw)
            for name, param in sig.parameters.items():
                if param.annotation is inspect.Parameter.empty:
                    continue
                if name not in bound.arguments:
                    continue
                value = bound.arguments[name]
                if not _check(value, param.annotation):
                    type_name = type(value).__name__
                    ann = param.annotation
                    raise TypeError(
                        f"Validation error in '{f.__name__}':\n"
                        f"Argument '{name}': expected {ann!r} "
                        f"(got type '{type_name}')"
                    )
            return f(*args, **kw)

        return wrapper
    if func is not None:
        return decorator(func)
    return decorator
```

The error shape mirrors the pydantic backend closely enough that the
existing `test_error_message_format` and `test_sensitive_data_leakage`
pass without modification. Edge cases the stdlib backend **does not**
support (custom `Annotated` metadata, generic aliases) raise the
generic message above; downstream tests that exercise those will be
marked as pydantic-only.

### 6.3 `ext/observability_stdlib`

Stdlib shim for `setup_logging`. Same signature; uses `logging.basicConfig`
with a session-ID-aware formatter and a `RotatingFileHandler` for file
output.

---

## 7. `pyproject.toml`

```toml
[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[project]
name = "gunz-utils"
version = "1.3.0"
description = "General purpose utilities for the Gunz ecosystem"
authors = [
    { name = "Yeremia Gunawan Adhisantoso", email = "adhisant@tnt.uni-hannover.de" },
]
readme = "README.md"
requires-python = ">=3.11"
classifiers = [
    "Programming Language :: Python :: 3",
    "License :: OSI Approved :: BSD License",
    "Operating System :: OS Independent",
]
# All runtime deps stay declared in core for backwards-compat.
# Users who want a smaller install opt into per-feature extras below.
dependencies = [
    "pydantic>=2.0.0",
    "cryptography>=42.0.0",
    "gitpython>=3.1.0",
    "loguru>=0.7.0",
]

[project.optional-dependencies]
# Each named group fully covers one module / bundle.
validation     = ["pydantic>=2.0.0"]
project        = ["gitpython>=3.1.0", "loguru>=0.7.0"]
observability  = ["loguru>=0.7.0"]
secure         = ["cryptography>=42.0.0"]
all            = [
    "pydantic>=2.0.0",
    "cryptography>=42.0.0",
    "gitpython>=3.1.0",
    "loguru>=0.7.0",
]
docs           = ["sphinx", "furo", "myst-parser", "sphinx-autodoc-typehints"]

[dependency-groups]                # PEP 735 — dev only
dev  = [{include-group = "test"}, {include-group = "lint"}]
test = ["pytest>=8.0"]
lint = ["ruff>=0.6.0"]

[project.urls]
"Homepage" = "https://github.com/sXperfect/gunz-utils"
"Bug Tracker" = "https://github.com/sXperfect/gunz-utils/issues"

[tool.hatch.build.targets.wheel]
packages = ["src/gunz_utils"]

[tool.hatch.build.targets.sdist]
include = ["src/"]
```

---

## 8. CI matrix (`.github/workflows/ci.yml`)

```yaml
name: CI

on:
  push:
    branches: ["main"]
  pull_request:
    branches: ["main"]

jobs:
  core:
    runs-on: ubuntu-latest
    strategy:
      matrix: { python-version: ["3.11", "3.12"] }
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with: { python-version: ${{ matrix.python-version }} }
      - run: python -m pip install --upgrade pip
      - run: pip install .
      - run: python -m unittest discover tests/test_core -v

  validation_extras:
    runs-on: ubuntu-latest
    strategy:
      matrix: { python-version: ["3.11", "3.12"] }
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with: { python-version: ${{ matrix.python-version }} }
      - run: pip install .
      - run: python -m unittest discover tests/test_validation -v

  project_extras:
    runs-on: ubuntu-latest
    strategy:
      matrix: { python-version: ["3.11", "3.12"] }
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with: { python-version: ${{ matrix.python-version }} }
      - run: pip install .
      - run: python -m unittest discover tests/test_project -v

  observability_extras:
    runs-on: ubuntu-latest
    strategy:
      matrix: { python-version: ["3.11", "3.12"] }
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with: { python-version: ${{ matrix.python-version }} }
      - run: pip install .
      - run: python -m unittest discover tests/test_observability -v

  secure_extras:
    runs-on: ubuntu-latest
    strategy:
      matrix: { python-version: ["3.11", "3.12"] }
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with: { python-version: ${{ matrix.python-version }} }
      - run: pip install .[secure]
      - run: python -m unittest discover tests/test_secure -v

  ruff:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with: { python-version: "3.11" }
      - run: pip install ruff
      - run: ruff check src tests
```

Tests reorganized by feature: `tests/test_core/`, `test_validation/`,
`test_project/`, `test_observability/`, `test_secure/`. Each test
file uses `unittest.skipUnless(find_spec("...") is not None, ...)`
guards where appropriate; stdlib-path tests have no skip guard.

`deploy_docs.yml` install line updated: `pip install '.[all]'`.

---

## 9. Docs updates (Phase P0)

- `docs/source/installation.md` — replace stale `pydantic, rich,
  GitPython` claim with the real installed deps and the optional-extras
  matrix.
- New section *"Optional Dependencies"* under
  `docs/source/concepts.md` covering the choice matrix and the
  `gunz_utils.ext.*` entrypoints.
- `docs/source/conf.py` — `autodoc_mock_imports = ["cryptography",
  "gitpython", "loguru", "pydantic"]` (drop obsolete `rich`,
  `typing_extensions`).
- `.github/workflows/deploy_docs.yml` — `pip install '.[all]'` plus
  `docs` extra; remove obsolete ad-hoc install list.

---

## 10. CHANGELOG.md (v1.3.0 entry)

```markdown
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
```

---

## 11. Execution plan (phases)

| Phase | Scope | Files | Commit |
|---|---|---|---|
| P0 | Doc/install drift + `__init__.py` sync (no library split yet) | `docs/source/installation.md`, `docs/source/conf.py`, `.github/workflows/deploy_docs.yml`, `src/gunz_utils/__init__.py` | `docs(install): accurate extras matrix + __init__ v1.1.0 sync` |
| P1 | Library split: `ext.*` directory + lazy `__init__` + stdlib fallbacks | `src/gunz_utils/__init__.py`, `src/gunz_utils/ext/**` (new), `src/gunz_utils/validation.py` (move/delete), `src/gunz_utils/project.py` (move/delete), `src/gunz_utils/logging.py` (move/delete), `src/gunz_utils/crypto.py` (move/delete), `src/gunz_utils/secure_store.py` (move/delete) | `feat(deps): split into ext.* with stdlib fallbacks and lazy __init__` |
| P2 | Test split | `tests/test_*/` reorganization, skip guards, new stdlib-fallback tests | `test(deps): split test suite by feature; new ext.* tests` |
| P3 | CI matrix split | `.github/workflows/ci.yml` | `ci(deps): split into core/validation/project/observability/secure/ruff jobs` |
| P4 | CHANGELOG + version bump | `CHANGELOG.md` (new), `pyproject.toml` `version` to 1.3.0 | `docs: CHANGELOG for v1.3.0` |
| P5 | Tag + push | (operations only) | (no commit) |

Phases execute sequentially. Final merge is `git merge --no-ff
feat/deps-split` into `main`, push, tag `v1.3.0`, push tag.

---

## 12. Risk register

- **Stdlib `type_checked` error format drift.** The existing
  `test_sensitive_data_leakage` and `test_error_message_format` tests
  pin the error message shape. Verify by running the tests during
  implementation; iterate until green.
- **Stdlib `resolve_project_root` correctness.** Test that the new
  path returns the same root as `git rev-parse --show-toplevel` in
  a fresh worktree.
- **Lazy `__getattr__` overhead** is negligible (~100 ns/call) but
  must not break module-level introspection (`dir(gunz_utils)`,
  `gunz_utils.__all__`). Verify by running `import gunz_utils;
  "type_checked" in dir(gunz_utils)` and `gunz_utils.__all__` checks.
- **`gunz_utils.models.HealthStatus` reads from `os.uname()`** in the
  default_factory; tests must mock `os.uname` if any are added.
- **Backward compat for top-level imports.** Existing
  `from gunz_utils import resolve_project_root` must keep working
  via the new PEP 562 indirection.

---

## 13. Out of scope

- No default-API behavior change.
- No new features beyond what is required for the split.
- No public-API renames.
- No change to `enums.py`, `security.py`, `upstream_protocol.py`
  beyond what `__init__` imports.
- No `dependencies = []` simplification — that's a v2.x decision.
