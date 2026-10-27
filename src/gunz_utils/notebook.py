"""
Jupyter notebook bootstrap helpers.

Provides a single-call setup for notebooks that need to import local project
source: it resolves the project root, injects the root (and optionally
``src/`` plus additional subpaths) into ``sys.path``, and can enable IPython
autoreload so local edits are picked up automatically.
"""

# =============================================================================
# METADATA
# =============================================================================
__author__ = "Yeremia Gunawan Adhisantoso"
__email__ = "yeremiag@gmail.com"
__license__ = "Clear BSD"

# =============================================================================
# STANDARD LIBRARY IMPORTS
# =============================================================================
import pathlib
import typing as t

# =============================================================================
# LOCAL APPLICATION IMPORTS
# =============================================================================
from .ext.project_gitpython import resolve_project_root

try:
    from IPython import get_ipython
except Exception:
    get_ipython = None

__all__ = ["setup_notebook"]


def setup_notebook(
    anchor: str = ".",
    src: bool = True,
    subpaths: t.Sequence[str | pathlib.Path] = (),
    autoreload: bool = True,
) -> pathlib.Path:
    """Bootstrap a notebook to import project source.

    Resolves the project root, injects the root (and optionally ``src/`` and
    additional subpaths) into ``sys.path``, and optionally enables IPython
    ``%autoreload`` so edits to local source are picked up automatically.

    Parameters
    ----------
    anchor : str, optional
        Path to start searching for the project root from, by default the
        current working directory.
    src : bool, optional
        If True, injects ``<root>/src`` into ``sys.path``, by default True.
    subpaths : t.Sequence[str | pathlib.Path], optional
        Additional subdirectories of the root to inject into ``sys.path``.
    autoreload : bool, optional
        If True and running under IPython, enables ``%load_ext autoreload``
        and ``%autoreload 2``, by default True.

    Returns
    -------
    pathlib.Path
        The resolved project root.

    Notes
    -----
    Requires ``gunz_utils`` to be importable in the kernel. For kernels where
    the package is not installed, first run a small self-contained bootstrap
    snippet (see the README) that adds the root and ``src`` to ``sys.path``,
    then import this helper.
    """
    root = resolve_project_root(
        anchor=anchor,
        inject_to_sys_path=True,
        src=src,
        subpaths=subpaths,
    )
    if autoreload:
        _enable_autoreload()
    return root


def _enable_autoreload() -> None:
    """Enable IPython autoreload when running inside a Jupyter/IPython kernel."""
    if get_ipython is None:
        return

    ipython = get_ipython()
    if ipython is None:
        return

    try:
        ipython.run_line_magic("load_ext", "autoreload")
        ipython.run_line_magic("autoreload", "2")
    except Exception:
        return
