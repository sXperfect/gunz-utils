"""Perpetual security & concurrency audit - PHASE 9 regression tests.

Audits the optional-backend modules (ext/__init__, ext/project_stdlib,
ext/project_gitpython) plus the lazy optional-dependency isolation wired up in
the package ``__init__``. Tests are written to FAIL ("red") against the current
source and must pass only after the corresponding production fix lands.
Production code is intentionally not modified.

Findings covered here:
1. ``gunz_utils.__getattr__`` (__init__.py:109-120) leaks ``ModuleNotFoundError``
   when a lazily exposed optional attribute's third-party dependency is missing,
   instead of raising ``AttributeError``. ``hasattr(gunz_utils, name)`` therefore
   raises instead of returning False, and ``getattr(gunz_utils, name, default)``
   raises instead of returning the default - breaking the standard attribute
   introspection contract for unavailable optional features.
2. ``ext/project_gitpython.py:83-123`` wraps the whole resolution in a broad
   ``except Exception`` that also catches the specific ``RuntimeError`` raised
   inside the ``try`` (bare repository at :90, not-a-directory at :96), replacing
   their precise diagnostics with a generic "Unexpected RuntimeError while
   resolving project root" message.
"""

# =============================================================================
# STANDARD LIBRARY IMPORTS
# =============================================================================

from __future__ import annotations

import importlib
import sys
import tempfile
import types

# isort: split
# =============================================================================
# THIRD-PARTY IMPORTS
# =============================================================================

import pytest

# isort: split
# =============================================================================
# LOCAL APPLICATION IMPORTS
# =============================================================================

import gunz_utils

# -----------------------------------------------------------------------------
# __init__.py - lazy __getattr__ leaks ImportError for missing optional deps
# -----------------------------------------------------------------------------


def test_lazy_getattr_hasattr_returns_false_on_missing_dependency(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """``hasattr`` must not raise when a lazy optional dependency is missing.

    ``__getattr__`` (__init__.py:109-120) imports the backing module and
    propagates its ``ModuleNotFoundError`` (an ``ImportError``) when the optional
    dependency is absent, but ``hasattr`` only treats ``AttributeError`` as
    "attribute absent". A missing optional feature must surface as
    ``AttributeError`` so ``hasattr`` returns False.
    """
    real_import_module = importlib.import_module

    def _simulate_missing(name: str, package: str | None = None) -> object:
        raise ModuleNotFoundError(f"No module named {name!r}")

    monkeypatch.setattr(importlib, "import_module", _simulate_missing)
    try:
        assert hasattr(gunz_utils, "SecureStore") is False
    finally:
        monkeypatch.setattr(importlib, "import_module", real_import_module)


def test_lazy_getattr_getattr_default_returns_default_on_missing_dependency(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """``getattr(obj, name, default)`` must return the default, not raise.

    Same defect: a missing optional dependency propagates ``ModuleNotFoundError``
    from ``__getattr__`` instead of ``AttributeError``, so ``getattr(..., default)``
    raises rather than returning the fallback value.
    """
    monkeypatch.setattr(
        importlib,
        "import_module",
        lambda name, package=None: (_ for _ in ()).throw(
            ModuleNotFoundError("No module named 'git'")
        ),
    )
    assert getattr(gunz_utils, "resolve_project_root", "FALLBACK") == "FALLBACK"


# -----------------------------------------------------------------------------
# ext/project_gitpython.py - broad except masks specific RuntimeErrors
# -----------------------------------------------------------------------------


def test_project_gitpython_preserves_bare_repo_error_message(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A bare repository must raise the specific "bare repository" message.

    ``resolve_project_root`` raises ``RuntimeError("Resolved repo has no working
    tree (bare repository).")`` inside the ``try``, but the surrounding broad
    ``except Exception`` (project_gitpython.py:120) catches it and re-raises a
    generic "Unexpected RuntimeError while resolving project root", discarding
    the diagnostic. The precise message must be preserved.
    """
    git_stub = types.ModuleType("git")

    class InvalidGitRepositoryError(Exception):
        pass

    class BareRepo:
        working_tree_dir = None

    git_stub.InvalidGitRepositoryError = InvalidGitRepositoryError
    git_stub.Repo = lambda *args, **kwargs: BareRepo()
    monkeypatch.setitem(sys.modules, "git", git_stub)

    from gunz_utils.ext import project_gitpython

    monkeypatch.setattr(project_gitpython, "Repo", git_stub.Repo)
    monkeypatch.setattr(project_gitpython, "_PROJECT_ROOT", None)
    monkeypatch.setattr(project_gitpython, "_PROJECT_ANCHOR", None)

    anchor = tempfile.mkdtemp()
    with pytest.raises(RuntimeError, match="bare repository"):
        project_gitpython.resolve_project_root(anchor, inject_to_sys_path=False)


# -----------------------------------------------------------------------------
# Sanity green - lazy optional loading still works when the dep is present
# -----------------------------------------------------------------------------


def test_lazy_getattr_unknown_name_raises_attribute_error() -> None:
    """Sanity green: a genuinely unknown attribute still raises AttributeError."""
    with pytest.raises(AttributeError):
        gunz_utils.definitely_not_a_real_attribute  # noqa: B018
