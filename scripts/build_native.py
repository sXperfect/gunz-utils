#!/usr/bin/env python3
"""Build script for compiling the gunz-utils optional C extension.

Compiles native/src/_accel.c into src/gunz_utils/_accel<ext_suffix>.
Uses clang/gcc on POSIX and cl.exe on Windows with zero third-party dependencies.
"""

from __future__ import annotations

import os
import subprocess
import sys
import sysconfig
from pathlib import Path


def build() -> int:
    root = Path(__file__).resolve().parent.parent
    c_src = root / "native" / "src" / "_accel.c"
    inc_dir = root / "native" / "include"
    out_dir = root / "src" / "gunz_utils"
    out_dir.mkdir(parents=True, exist_ok=True)

    ext_suffix = sysconfig.get_config_var("EXT_SUFFIX") or ".so"
    out_so = out_dir / f"_accel{ext_suffix}"

    py_inc = sysconfig.get_paths()["include"]

    if sys.platform == "win32":
        cmd = [
            "cl",
            "/O2",
            "/LD",
            f"/I{py_inc}",
            f"/I{inc_dir}",
            str(c_src),
            f"/Fe{out_so}",
        ]
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

    print(f"Compiling native extension: {' '.join(cmd)}")
    try:
        res = subprocess.run(cmd, check=False)
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
        print(f"Successfully compiled native extension: {out_so}")
        return 0
    else:
        print(f"Compilation failed with exit code: {res.returncode}")
        return res.returncode


if __name__ == "__main__":
    sys.exit(build())
