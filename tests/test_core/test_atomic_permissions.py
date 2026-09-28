"""Explicit permission semantics for atomic file publication."""

from __future__ import annotations

import json
import os
import stat
from pathlib import Path

import pytest

from gunz_utils.io import atomic_json_write, atomic_write

pytestmark = pytest.mark.skipif(
    not hasattr(os, "fchmod"),
    reason="explicit descriptor permissions require os.fchmod",
)


def test_atomic_write_applies_permissions_before_publication(
    tmp_path: Path,
) -> None:
    target = tmp_path / "secret.txt"

    atomic_write(
        target,
        "secret",
        permissions=0o600,
    )

    assert target.read_text(encoding="utf-8") == "secret"
    assert stat.S_IMODE(target.stat().st_mode) == 0o600


def test_atomic_json_write_forwards_permissions(tmp_path: Path) -> None:
    target = tmp_path / "config.json"

    atomic_json_write(
        target,
        {"token": "redacted-test-value"},
        permissions=0o600,
    )

    assert json.loads(target.read_text(encoding="utf-8")) == {
        "token": "redacted-test-value"
    }
    assert stat.S_IMODE(target.stat().st_mode) == 0o600


@pytest.mark.parametrize(
    "permissions",
    [
        -1,
        0o10000,
        True,
        0.5,
    ],
)
def test_atomic_write_rejects_invalid_permissions(
    tmp_path: Path,
    permissions: object,
) -> None:
    with pytest.raises(ValueError, match="permissions"):
        atomic_write(
            tmp_path / "value.txt",
            "value",
            permissions=permissions,
        )


@pytest.mark.skipif(os.name != "posix", reason="POSIX mode semantics required")
def test_atomic_write_private_target_uses_private_parent_mode(
    tmp_path: Path,
) -> None:
    target = tmp_path / "private" / "secret.txt"

    atomic_write(
        target,
        "secret",
        mkdir=True,
        permissions=0o600,
    )

    parent_mode = stat.S_IMODE(target.parent.stat().st_mode)
    assert parent_mode & 0o077 == 0
