#!/usr/bin/env python3
"""Build script for compiling the gunz-utils optional C extension.

Compiles native/src/_accel.c into src/gunz_utils/_accel<ext_suffix>.
Uses clang/gcc on POSIX and cl.exe on Windows with zero third-party dependencies.
"""

# =============================================================================
# STANDARD LIBRARY IMPORTS
# =============================================================================

from __future__ import annotations

import argparse
import os
import subprocess
import sys
import sysconfig
import tempfile
from pathlib import Path


def _windows_command(
    source: Path,
    include: Path,
    python_include: str,
    output: Path,
    intermediate: Path,
    *,
    python_base: Path,
    debug: bool,
) -> list[str]:
    """Use the running CPython import library and a matching dynamic CRT."""
    suffix = "_d" if debug else ""
    library_dir = python_base / "libs"
    library = library_dir / (
        f"python{sys.version_info.major}{sys.version_info.minor}{suffix}.lib"
    )
    if not library.is_file():
        raise FileNotFoundError(f"CPython import library is missing: {library}")
    return [
        "cl",
        "/O2",
        "/LD",
        "/MDd" if debug else "/MD",
        f"/I{python_include}",
        f"/I{include}",
        str(source),
        f"/Fo{intermediate / '_accel.obj'}",
        f"/Fe{output}",
        "/link",
        f"/LIBPATH:{library_dir}",
        str(library),
        f"/IMPLIB:{intermediate / '_accel.lib'}",
    ]


def _run_build(
    cmd: list[str],
    output: Path,
    *,
    cwd: Path | None = None,
) -> int:
    print(f"Compiling native extension: {' '.join(cmd)}")
    try:
        res = subprocess.run(cmd, check=False, cwd=cwd)
    except FileNotFoundError as err:
        print(
            f"Compilation failed: compiler executable not found: {cmd[0]} ({err})",
            file=sys.stderr,
        )
        return 1
    except OSError as err:
        print(f"Compilation failed: launch error: {err}", file=sys.stderr)
        return 1
    if res.returncode == 0:
        print(f"Successfully compiled native extension: {output}")
    else:
        print(f"Compilation failed with exit code: {res.returncode}")
    return res.returncode


def build(
    output_dir: Path | None = None,
) -> int:
    """Compile optional acceleration, optionally into an isolated package copy."""
    root = Path(__file__).resolve().parent.parent
    c_src = root / "native" / "src" / "_accel.c"
    inc_dir = root / "native" / "include"
    out_dir = output_dir if output_dir is not None else root / "src" / "gunz_utils"
    out_dir.mkdir(parents=True, exist_ok=True)

    ext_suffix = sysconfig.get_config_var("EXT_SUFFIX") or (
        ".pyd" if sys.platform == "win32" else ".so"
    )
    out_so = out_dir / f"_accel{ext_suffix}"

    py_inc = sysconfig.get_paths()["include"]

    if sys.platform == "win32":
        #? A venv uses the base interpreter's import library. Keep every MSVC
        #? intermediate in scratch, including defaults created in its cwd.
        debug = bool(sysconfig.get_config_var("Py_DEBUG")) or hasattr(
            sys, "gettotalrefcount"
        )
        with tempfile.TemporaryDirectory(
            prefix=".native-build-", dir=out_dir
        ) as scratch:
            try:
                cmd = _windows_command(
                    c_src,
                    inc_dir,
                    py_inc,
                    out_so.resolve(),
                    Path(scratch).resolve(),
                    python_base=Path(sys.base_prefix),
                    debug=debug,
                )
            except FileNotFoundError as err:
                print(f"Compilation failed: {err}", file=sys.stderr)
                return 1
            return _run_build(cmd, out_so, cwd=Path(scratch))
    else:
        cc = os.environ.get("CC", "clang" if sys.platform == "darwin" else "gcc")
        cmd = [
            cc,
            "-O3",
            "-shared",
            "-fPIC",
            f"-I{py_inc}",
            f"-I{inc_dir}",
            str(c_src),
            "-o",
            str(out_so),
        ]
        if sys.platform == "darwin":
            cmd.extend(["-undefined", "dynamic_lookup"])

    return _run_build(cmd, out_so)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--output-dir", type=Path, help="compile outside the source checkout"
    )
    sys.exit(build(parser.parse_args().output_dir))
