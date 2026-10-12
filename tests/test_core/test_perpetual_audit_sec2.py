"""Perpetual security & concurrency audit - PHASE 2 regression tests.

Each test exposes a concrete security, subprocess-isolation, or path-containment
defect in the audited modules (subprocess, fs, network, redaction, io). Tests are
written to FAIL ("red") against the current source and must pass only after the
corresponding production fix lands. Production code is intentionally not modified.
"""

# =============================================================================
# STANDARD LIBRARY IMPORTS
# =============================================================================

from __future__ import annotations

import asyncio
import os
from pathlib import Path

# isort: split
# =============================================================================
# THIRD-PARTY IMPORTS
# =============================================================================

import pytest

# isort: split
# =============================================================================
# LOCAL APPLICATION IMPORTS
# =============================================================================

from gunz_utils.fs import lexical_contained_path
from gunz_utils.subprocess import run_command, run_command_async

# Arbitrary secret name unlikely to collide with the host environment.
_SECRET_VAR = "GUNZ_PHASE2_AUDIT_SECRET"
_SECRET_VALUE = "phase2-super-secret-token-9f8e7d"


@pytest.fixture(autouse=True)
def _guard_secret_environment() -> None:
    """Ensure the probe secret exists in the parent environment for every test."""
    previous = os.environ.get(_SECRET_VAR)
    os.environ[_SECRET_VAR] = _SECRET_VALUE
    yield
    if previous is None:
        os.environ.pop(_SECRET_VAR, None)
    else:
        os.environ[_SECRET_VAR] = previous


def _print_secret_args() -> list[str]:
    """Return args that print the probe secret from the child environment."""
    return ["sh", "-c", f'printf %s "${{{_SECRET_VAR}}}"']


# -----------------------------------------------------------------------------
# subprocess.py - env=... must not leak the parent environment to the child
# -----------------------------------------------------------------------------


def test_run_command_env_empty_does_not_leak_parent_secrets() -> None:
    """Passing ``env={}`` must give the child an empty (clean) environment.

    ``run_command`` builds the child environment with
    ``{**os.environ, **env}`` (subprocess.py:286). As a result ``env={}`` does
    NOT isolate the child: the full parent environment - including secrets such
    as the probe token - is inherited. This deviates from the stdlib
    ``subprocess.run(..., env=...)`` contract, where supplying ``env`` replaces
    the environment entirely. A caller using ``env={}`` to sandbox an untrusted
    subprocess against credential disclosure is silently given no isolation.
    """
    result = run_command(_print_secret_args(), env={})
    assert _SECRET_VALUE not in result.stdout


def test_run_command_async_env_empty_does_not_leak_parent_secrets() -> None:
    """The async variant has the same env-merge defect (subprocess.py:723)."""
    async def run() -> str:
        result = await run_command_async(_print_secret_args(), env={})
        return result.stdout

    stdout = asyncio.run(run())
    assert _SECRET_VALUE not in stdout


def test_run_command_env_explicit_minimal_does_not_include_other_secrets() -> None:
    """A caller that supplies an explicit environment must not inherit unrelated
    parent secrets that were not part of that environment mapping."""
    clean: dict[str, str] = {"PATH": os.environ.get("PATH", "/usr/bin:/bin")}
    result = run_command(_print_secret_args(), env=clean)
    assert _SECRET_VALUE not in result.stdout


# -----------------------------------------------------------------------------
# fs.py - lexical_contained_path must not defeat containment via symlinks
# -----------------------------------------------------------------------------


def test_lexical_contained_path_prevents_symlink_escape(tmp_path: Path) -> None:
    """A path that passes through a symlink must not resolve outside root.

    ``contained_path`` (fs.py:24) resolves symlinks and rejects escapes, but
    ``lexical_contained_path`` (fs.py:55) only rejects ``..`` parts and absolute
    paths, returning ``root / supplied`` without resolving. When ``root``
    contains a symlink pointing outside (an attacker-controlled or poisoned
    cache directory), a caller that obtains ``lexical_contained_path(root,
    "link/passwd")`` and then opens it reads a file outside the configured
    root - defeating the containment guarantee its name implies.
    """
    outside = tmp_path / "outside"
    outside.mkdir()
    secret = outside / "secret.txt"
    secret.write_text("outside-root-data", encoding="utf-8")

    root = tmp_path / "root"
    root.mkdir()
    try:
        (root / "link").symlink_to(outside)
    except (OSError, NotImplementedError):
        pytest.skip("symlink creation is unavailable")

    # A path that traverses an outside-pointing symlink cannot resolve inside
    # root, so the containment guarantee is enforced by rejecting it outright.
    with pytest.raises(ValueError):
        lexical_contained_path(root, "link/secret.txt")


def test_lexical_contained_path_still_rejects_dotdot(tmp_path: Path) -> None:
    """Sanity: classic ``..`` traversal remains rejected (guard against an
    over-broad fix that disables the existing check)."""
    with pytest.raises(ValueError):
        lexical_contained_path(tmp_path, "../escape")


# -----------------------------------------------------------------------------
# (resource-bounds note) subprocess default output capture is unbounded; the
# bounded path below confirms the explicit bound is enforced (sanity, green).
# -----------------------------------------------------------------------------


def test_run_command_bounded_capture_enforces_limit() -> None:
    """With ``max_output_bytes`` set, excessive child output is rejected."""
    from gunz_utils.subprocess import CommandOutputLimitError

    args = ["sh", "-c", "yes xxxxxxxxxx | head -c 200000"]
    with pytest.raises(CommandOutputLimitError):
        run_command(args, max_output_bytes=1024)
