#!/usr/bin/env python3
"""Local CI runner mirroring the intended hosted gates.

Each subcommand corresponds to one intended hosted gate and runs the same
check the CI workflow would run, **without** mutating the active environment:

    python scripts/ci.py release     # release/version/changelog metadata
    python scripts/ci.py lint        # ruff (src tests benchmarks scripts) + mypy
    python scripts/ci.py test        # full pytest (unittest cases + pytest functions)
    python scripts/ci.py docs        # Sphinx docs build (scripts/build_docs.sh)
    python scripts/ci.py packaging   # dependency-isolation matrix in fresh venvs
    python scripts/ci.py all         # every gate sequentially, stop on first failure

Ordinary checking never reinstalls or upgrades the environment and never touches
the shared ``gunz_utils`` editable install. The package-import origin is always
verified to resolve inside this worktree's ``src/`` before any check runs.
``packaging`` is the one gate that intentionally creates fresh throwaway venvs
under ``tmp/c05-venvs/`` (and builds artifacts under ``tmp/c05-dist/``) so each
dependency boundary is proven in genuine isolation without ever mutating the
active or shared environment.

Why these commands exist: the previous runner (see git history) ran only a
subset of ``unittest discover`` groups and silently omitted pytest functions,
typing, the import-origin guard, and documentation. This dispatcher makes the
local surface match the intended hosted gates so a passing local run is
truthful evidence for the CI checks.
"""

from __future__ import annotations

import argparse
import os
import shutil
import subprocess
import sys
from collections.abc import Callable, Mapping, Sequence
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
SRC_DIR = PROJECT_ROOT / "src"
DOCS_SOURCE = PROJECT_ROOT / "docs" / "source"
BUILD_DOCS_SCRIPT = PROJECT_ROOT / "scripts" / "build_docs.sh"
RELEASE_SCRIPT = PROJECT_ROOT / "scripts" / "release.py"

# The packaging isolation gate forbids these optional packages from being
# imported by the zero-dependency core package.
FORBIDDEN_OPTIONAL_MODULES = {"pydantic", "cryptography", "git", "loguru"}

# Scratch locations for the packaging isolation matrix. These live inside the
# worktree's ``tmp/`` (fresh venvs) so the shared environment is never touched;
# the outside-checkout CWD used by the source-shadowing guard is a dedicated
# empty dir in the system temp space.
VENV_BASE = PROJECT_ROOT / "tmp" / "c05-venvs"
DIST_DIR = PROJECT_ROOT / "tmp" / "c05-dist"
OUTSIDE_CWD = Path("/tmp/gunz-c05-outside")


def _env() -> dict[str, str]:
    """Return a subprocess env whose ``PYTHONPATH`` points into this worktree.

    The shared environment may hold an editable install of ``gunz_utils``; we
    deliberately place this worktree's ``src/`` first so imports are local and
    reproducible, independent of the active interpreter's site-packages.
    """
    env = dict(os.environ)
    env["PYTHONPATH"] = str(SRC_DIR)
    return env


def _origin_ok(path: str) -> bool:
    """Return True when ``gunz_utils`` resolves inside this worktree's ``src``.

    This is the deliberate-import-origin guard: a local check that imports a
    copy of the package from the original/shared checkout (or an installed
    wheel from elsewhere) is not evidence for the code under test.
    """
    return str(path).startswith(str(SRC_DIR))


def _verify_import_origin() -> None:
    """Verify ``gunz_utils`` resolves into this worktree and print its origin.

    Fails loudly (exit code 3) when the package resolves to the shared/original
    checkout or any installed location outside ``SRC_DIR`` instead.
    """
    code = (
        "import gunz_utils\n"
        "import sys\n"
        "path = gunz_utils.__file__\n"
        "print(path)\n"
        f"expected = {str(SRC_DIR)!r}\n"
        "if not str(path).startswith(expected):\n"
        "    sys.stderr.write('gunz_utils resolved outside worktree: '\n"
        "                     + path + '\\n')\n"
        "    sys.exit(3)\n"
    )
    result = subprocess.run(
        [sys.executable, "-c", code],
        cwd=PROJECT_ROOT,
        env=_env(),
        text=True,
        capture_output=True,
    )
    if result.stdout:
        print(result.stdout, end="", flush=True)
    if result.returncode != 0:
        print(
            "!! package import did not resolve into the worktree "
            f"({SRC_DIR})",
            file=sys.stderr,
        )
        if result.stderr:
            sys.stderr.write(result.stderr)
        sys.exit(result.returncode or 3)


def _run(cmd: Sequence[str], *, env: Mapping[str, str] | None = None) -> int:
    """Run ``cmd`` from the project root and return its exit code.

    Returns (rather than raising) so callers can aggregate gate statuses; the
    nonzero return is printed to stderr for visibility.
    """
    print(f"$ {' '.join(cmd)}", flush=True)
    result = subprocess.run(
        list(cmd),
        cwd=PROJECT_ROOT,
        env=_env() if env is None else env,
    )
    if result.returncode != 0:
        print(f"!! command failed with exit code {result.returncode}", file=sys.stderr)
    return result.returncode


def run_release() -> int:
    """Validate package version, changelog fragments, and release metadata."""
    if not RELEASE_SCRIPT.is_file():
        print(f"!! missing release script: {RELEASE_SCRIPT}", file=sys.stderr)
        return 2
    return _run([sys.executable, str(RELEASE_SCRIPT), "check"])


def run_test() -> int:
    """Run the complete pytest collection."""
    _verify_import_origin()
    return _run([sys.executable, "-m", "pytest"])


def _clean_env() -> dict[str, str]:
    """Return a subprocess env with ``PYTHONPATH`` cleared (no ``src`` shadowing).

    Fresh-venv cases install the package and must import the *installed* copy
    from the venv's ``site-packages``, never the worktree ``src/``. Clearing
    ``PYTHONPATH`` guarantees the installed artifact is what actually gets
    imported, independent of the active interpreter's site-packages.
    """
    env = dict(os.environ)
    env.pop("PYTHONPATH", None)
    env["PIP_DISABLE_PIP_VERSION_CHECK"] = "1"
    return env


def _run_venv(cmd: Sequence[str], *, cwd: Path | None = None) -> int:
    """Run ``cmd`` in a clean env (no ``PYTHONPATH``) from ``cwd``.

    Unlike ``_run`` this never injects the worktree ``src/`` onto ``sys.path``,
    so a freshly installed package in a venv is what gets imported. Returns the
    exit code; a nonzero return is printed to stderr for visibility.
    """
    print(f"$ {' '.join(cmd)}", flush=True)
    result = subprocess.run(
        list(cmd),
        cwd=str(cwd) if cwd is not None else str(PROJECT_ROOT),
        env=_clean_env(),
    )
    if result.returncode != 0:
        print(f"!! command failed with exit code {result.returncode}", file=sys.stderr)
    return result.returncode


def _fresh_venv_python(name: str) -> tuple[Path, Path]:
    """Create a fresh venv for ``name`` under ``tmp/c05-venvs``; return (py, dir).

    Any previous scratch venv of the same name is removed first so each case
    runs in a genuinely clean, isolated interpreter. Only scratch dirs under
    ``tmp/c05-venvs`` are ever removed.
    """
    venv_dir = VENV_BASE / name
    if venv_dir.exists():
        shutil.rmtree(venv_dir)
    venv_dir.mkdir(parents=True, exist_ok=True)
    result = subprocess.run(
        [sys.executable, "-m", "venv", str(venv_dir)],
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        print(
            f"!! failed to create venv {name}: {result.stderr.strip()}",
            file=sys.stderr,
        )
        raise SystemExit(result.returncode or 3)
    return venv_dir / "bin" / "python", venv_dir


def _pip_install(py: Path, *args: str) -> int:
    """``pip install <args>`` inside a venv (quiet, version-check disabled)."""
    return _run_venv([str(py), "-m", "pip", "install", "--quiet", *args])


def _site_packages(venv_dir: Path) -> Path:
    """Return the ``site-packages`` directory of a freshly created venv."""
    lib = venv_dir / "lib"
    py_dirs = [p for p in lib.iterdir() if p.is_dir() and p.name.startswith("python")]
    if not py_dirs:
        raise SystemExit(f"no python lib dir in venv {venv_dir}")
    return py_dirs[0] / "site-packages"


def _case_zero_dep() -> int:
    """Install ``. --no-deps``; assert optional pkgs are NOT imported by core."""
    py, venv_dir = _fresh_venv_python("zero-dep")
    status = _pip_install(py, "--no-deps", ".")
    if status != 0:
        return status
    sp = _site_packages(venv_dir)
    code = (
        "import sys\n"
        "import gunz_utils\n"
        "from pathlib import Path\n"
        f"sp = {str(sp)!r}\n"
        f"forbidden = {sorted(FORBIDDEN_OPTIONAL_MODULES)!r}\n"
        "if not str(gunz_utils.__file__).startswith(sp):\n"
        "    sys.exit('zero-dep: gunz_utils resolved outside venv site-packages: '\n"
        "             + str(gunz_utils.__file__))\n"
        "loaded = [m for m in forbidden if m in sys.modules]\n"
        "if loaded:\n"
        "    sys.exit('zero-dep: optional modules imported by core: '\n"
        "             + ', '.join(sorted(loaded)))\n"
        "print('zero-dep OK: import origin', gunz_utils.__file__)\n"
    )
    return _run_venv([str(py), "-c", code])


def _case_stdlib() -> int:
    """Install ``.`` (no extras): stdlib fallback works, missing optional raises."""
    py, _ = _fresh_venv_python("stdlib")
    status = _pip_install(py, ".", "pytest==9.0.2")
    if status != 0:
        return status
    status = _run_venv([str(py), "-m", "pytest", "-q", "tests/test_ext_stdlib"])
    if status != 0:
        return status
    code = (
        "import sys\n"
        "try:\n"
        "    import gunz_utils.ext.validation_pydantic\n"
        "except ImportError:\n"
        "    print('stdlib OK: validation_pydantic raises ImportError as expected')\n"
        "else:\n"
        "    sys.exit('stdlib: validation_pydantic imported '\n"
        "             'with no extras installed')\n"
    )
    return _run_venv([str(py), "-c", code])


def _case_extra(extra: str, test_dir: str) -> int:
    """Install ``.[<extra>]`` in a fresh venv and run that extra's test directory."""
    py, _ = _fresh_venv_python(extra)
    status = _pip_install(py, f".[{extra}]", "pytest==9.0.2")
    if status != 0:
        return status
    return _run_venv([str(py), "-m", "pytest", "-q", f"tests/{test_dir}"])


def _case_plot() -> int:
    """Install ``.[plot]`` and render a real figure via the headless Agg backend."""
    py, _ = _fresh_venv_python("plot")
    status = _pip_install(py, ".[plot]")
    if status != 0:
        return status
    out = PROJECT_ROOT / "tmp" / "c05-plot-smoke.png"
    code = (
        "import matplotlib\n"
        "matplotlib.use('Agg')\n"
        "import matplotlib.pyplot as plt\n"
        "import gunz_utils.benchmark.plot as p\n"
        f"out = {str(out)!r}\n"
        "fig, ax = plt.subplots()\n"
        "ax.plot([1, 2, 3], [4, 5, 6])\n"
        "fig.savefig(out)\n"
        "import os\n"
        "if not os.path.isfile(out) or os.path.getsize(out) == 0:\n"
        "    raise SystemExit('plot: figure not written: ' + out)\n"
        "print('plot OK: real headless Agg render ->', out)\n"
    )
    return _run_venv([str(py), "-c", code])


def _case_wheel_sdist() -> int:
    """Build wheel+sdist, install the wheel, import from outside the checkout.

    The import runs from ``OUTSIDE_CWD`` (a dedicated empty dir in system temp,
    i.e. not the worktree and not under ``src/``) with no ``PYTHONPATH``, so if
    ``gunz_utils`` resolved to the checkout's ``src/`` that would be accidental
    source shadowing — the guard asserts it resolves to the venv ``site-packages``.
    """
    build_py, _ = _fresh_venv_python("build-env")
    status = _pip_install(build_py, "build")
    if status != 0:
        return status
    if DIST_DIR.exists():
        shutil.rmtree(DIST_DIR)
    DIST_DIR.mkdir(parents=True, exist_ok=True)
    status = _run_venv(
        [
            str(build_py),
            "-m",
            "build",
            "--wheel",
            "--sdist",
            "--outdir",
            str(DIST_DIR),
        ]
    )
    if status != 0:
        return status
    wheels = list(DIST_DIR.glob("gunz_utils-*.whl"))
    sdists = list(DIST_DIR.glob("gunz_utils-*.tar.gz"))
    if not wheels or not sdists:
        print(f"!! no wheel/sdist produced in {DIST_DIR}", file=sys.stderr)
        return 2
    wheel = wheels[0]
    install_py, install_venv = _fresh_venv_python("wheel-install")
    status = _pip_install(install_py, str(wheel))
    if status != 0:
        return status
    sp = _site_packages(install_venv)
    OUTSIDE_CWD.mkdir(parents=True, exist_ok=True)
    code = (
        "import sys\n"
        "from pathlib import Path\n"
        "import gunz_utils\n"
        f"sp = {str(sp)!r}\n"
        "p = str(gunz_utils.__file__)\n"
        "print('wheel import origin:', p)\n"
        "if not p.startswith(sp):\n"
        "    sys.exit('wheel: source shadowing! gunz_utils '\n"
        "             'resolved outside venv: ' + p)\n"
        "marker = Path(gunz_utils.__file__).parent / 'py.typed'\n"
        "if not marker.is_file():\n"
        "    sys.exit('wheel: missing PEP 561 marker: ' + str(marker))\n"
        "print('wheel/sdist OK: installed artifact + py.typed verified')\n"
    )
    return _run_venv([str(install_py), "-c", code], cwd=OUTSIDE_CWD)


def run_lint() -> int:
    """Ruff (src tests benchmarks) then mypy; propagate the first failure."""
    status = _run(
        [
            sys.executable,
            "-m",
            "ruff",
            "check",
            "src",
            "tests",
            "benchmarks",
            "scripts",
        ]
    )
    mypy_status = _run([sys.executable, "-m", "mypy", "src/gunz_utils"])
    if status == 0:
        status = mypy_status
    return status


def run_docs() -> int:
    """Build documentation with the project's docs script (hosted parity)."""
    if not BUILD_DOCS_SCRIPT.is_file():
        print(f"!! missing docs script: {BUILD_DOCS_SCRIPT}", file=sys.stderr)
        return 2
    return _run(["bash", str(BUILD_DOCS_SCRIPT)])


def run_packaging() -> int:
    """Dependency-isolation + packaging contract matrix in fresh venvs.

    Each case runs in its own brand-new ``python -m venv`` (under
    ``tmp/c05-venvs``) with a clean environment (no ``PYTHONPATH``), so a
    previously installed extra can never leak into a later case and the
    *installed* package (not the worktree ``src/``) is what gets exercised.

    Cases (see each ``_case_*`` for the exact command):
      zero-dep      - install ``. --no-deps``; assert optional pkgs absent after
                      ``import gunz_utils`` (import origin in venv site-packages).
      stdlib        - install ``.`` (no extras); run ``tests/test_ext_stdlib`` and
                      assert importing a pydantic-backed backend raises ImportError.
      validation    - install ``.[validation]``; run ``tests/test_validation``.
      project       - install ``.[project]``;     run ``tests/test_project``.
      observability - install ``.[observability]``; run ``tests/test_observability``.
      secure        - install ``.[secure]``;      run ``tests/test_secure``.
      plot          - install ``.[plot]``; headless ``Agg`` render of a real figure.
      wheel/sdist   - build wheel+sdist; install the wheel in a fresh venv; import
                      from a CWD outside the checkout and assert it resolves to the
                      venv ``site-packages`` (source-shadowing guard).

    Returns 0 only when every locally-runnable case passes; otherwise returns
    nonzero after printing the name of the first failing case.
    """
    cases: list[tuple[str, Callable[[], int]]] = [
        ("zero-dep", _case_zero_dep),
        ("stdlib", _case_stdlib),
        ("validation", lambda: _case_extra("validation", "test_validation")),
        ("project", lambda: _case_extra("project", "test_project")),
        ("observability", lambda: _case_extra("observability", "test_observability")),
        ("secure", lambda: _case_extra("secure", "test_secure")),
        ("plot", _case_plot),
        ("wheel/sdist", _case_wheel_sdist),
    ]
    for name, fn in cases:
        print()
        print("=" * 72)
        print(f"  packaging case: {name}")
        print("=" * 72)
        status = fn()
        if status != 0:
            print(f"!! packaging case failed: {name}", file=sys.stderr)
            return status
    return 0


GATES: dict[str, tuple[str, str]] = {
    "release": ("Validate release/version/changelog metadata", "release metadata"),
    "lint": ("Run ruff (src tests benchmarks scripts) then mypy", "ruff + mypy"),
    "test": ("Run full pytest (unittest cases + pytest functions)", "full pytest"),
    "docs": ("Build documentation via scripts/build_docs.sh", "sphinx docs"),
    "packaging": (
        "Run the packaging / dependency-isolation gate",
        "packaging/isolation",
    ),
}


def run_all() -> int:
    """Run every gate in order and stop at the first failure."""
    for name, (help_text, _label) in GATES.items():
        print()
        print("=" * 72)
        print(f"  gate: {name}  --  {help_text}")
        print("=" * 72)
        runner = {
            "release": run_release,
            "lint": run_lint,
            "test": run_test,
            "docs": run_docs,
            "packaging": run_packaging,
        }[name]
        status = runner()
        if status != 0:
            return status
    return 0


def build_parser() -> argparse.ArgumentParser:
    if not (PROJECT_ROOT / "pyproject.toml").is_file():
        print(f"pyproject.toml not found at {PROJECT_ROOT}", file=sys.stderr)
        sys.exit(2)
    parser = argparse.ArgumentParser(
        prog="scripts/ci.py",
        description=(
            "Local CI runner mirroring the intended hosted gates. "
            "Never reinstalls or mutates the active environment."
        ),
    )
    subparsers = parser.add_subparsers(dest="command", required=True)
    for name, (help_text, _label) in GATES.items():
        subparsers.add_parser(name, help=help_text)
    subparsers.add_parser(
        "all",
        help="Run every gate in order; stop on the first failure.",
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    if args.command == "all":
        return run_all()

    runner = {
        "release": run_release,
        "lint": run_lint,
        "test": run_test,
        "docs": run_docs,
        "packaging": run_packaging,
    }.get(args.command)
    if runner is None:  # pragma: no cover - argparse already rejects unknowns
        parser.error(f"unknown command: {args.command}")
    return runner()


if __name__ == "__main__":
    raise SystemExit(main())
