"""Fail-closed native activation and source-distribution artifact checks."""

from __future__ import annotations

import importlib.util
import io
import os
import subprocess
import sys
import tarfile
import zipfile
from pathlib import Path
from types import ModuleType

import pytest

ROOT = Path(__file__).resolve().parents[2]


def _script(name: str) -> ModuleType:
    spec = importlib.util.spec_from_file_location(name, ROOT / "scripts" / f"{name}.py")
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


ci = _script("ci")
native = _script("verify_native")


def _archives(
    tmp_path: Path, *, missing: str = "", compiled: bool = False
) -> tuple[Path, Path]:
    wheel = tmp_path / "package.whl"
    with zipfile.ZipFile(wheel, "w") as archive:
        archive.writestr("gunz_utils/py.typed", "")
        archive.writestr("gunz_utils.dist-info/WHEEL", "Root-Is-Purelib: true\n")
        if compiled:
            archive.writestr("gunz_utils/_accel.so", b"synthetic binary")
    sdist = tmp_path / "package.tar.gz"
    with tarfile.open(sdist, "w:gz") as archive:
        for name in (
            "src/gunz_utils/py.typed",
            "native/src/_accel.c",
            "native/include/gunz_utils_native.h",
            "scripts/build_native.py",
            "pyproject.toml",
        ):
            if name == missing:
                continue
            member = tarfile.TarInfo(f"package/{name}")
            member.size = 1
            archive.addfile(member, io.BytesIO(b"x"))
    return wheel, sdist


def test_distribution_inventory_requires_optional_native_support(
    tmp_path: Path,
) -> None:
    wheel, sdist = _archives(tmp_path)
    ci._check_distribution_contents(wheel, sdist)
    extracted = ci._extract_sdist(sdist, tmp_path / "extracted")
    assert (extracted / "native/src/_accel.c").read_bytes() == b"x"


@pytest.mark.parametrize("missing", ["native/src/_accel.c", "scripts/build_native.py"])
def test_sdist_inventory_rejects_missing_native_support(
    tmp_path: Path, missing: str
) -> None:
    wheel, sdist = _archives(tmp_path, missing=missing)
    with pytest.raises(ValueError, match="sdist missing"):
        ci._check_distribution_contents(wheel, sdist)


def test_pure_wheel_rejects_accidental_compiled_checkout_artifact(
    tmp_path: Path,
) -> None:
    wheel, sdist = _archives(tmp_path, compiled=True)
    with pytest.raises(ValueError, match="compiled native artifact"):
        ci._check_distribution_contents(wheel, sdist)


@pytest.mark.parametrize("name,symlink", [("../victim", False), ("package/link", True)])
def test_sdist_extract_rejects_escaping_or_redirecting_members(
    tmp_path: Path, name: str, symlink: bool
) -> None:
    sdist = tmp_path / "unsafe.tar.gz"
    with tarfile.open(sdist, "w:gz") as archive:
        member = tarfile.TarInfo(name)
        if symlink:
            member.type = tarfile.SYMTYPE
            member.linkname = "../../victim"
        archive.addfile(member)
    with pytest.raises(ValueError):
        ci._extract_sdist(sdist, tmp_path / "extracted")
    assert not (tmp_path / "victim").exists()


def test_native_activation_cannot_report_fallback_as_native(tmp_path: Path) -> None:
    package = tmp_path / "gunz_utils"
    package.mkdir()
    (package / "__init__.py").write_text("")
    (package / "binary.py").write_text("_accel_encode = None\n_accel_decode = None\n")
    (package / "serialization.py").write_text("_accel_is_json_clean = None\n")
    env = dict(os.environ, PYTHONPATH=str(tmp_path))
    result = subprocess.run(
        [sys.executable, "-c", native.activation_code(tmp_path, native=True)],
        cwd=tmp_path,
        env=env,
        capture_output=True,
        text=True,
        timeout=10,
    )
    assert result.returncode != 0
    assert "fallback is not proof" in result.stderr
    fallback = subprocess.run(
        [sys.executable, "-c", native.activation_code(tmp_path, native=False)],
        cwd=tmp_path,
        env=env,
        capture_output=True,
        text=True,
        timeout=10,
    )
    assert fallback.returncode == 0
