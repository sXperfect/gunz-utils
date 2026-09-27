"""Package version resolution for gunz-utils.

`pyproject.toml` remains the only static source of the distribution version.
This module exposes the installed distribution version so package and historical
module-level `__version__` attributes stay synchronized without duplicated
literals.
"""

from __future__ import annotations

from importlib.metadata import PackageNotFoundError, version as package_version

try:
    __version__ = package_version("gunz-utils")
except PackageNotFoundError:
    __version__ = "0+unknown"

__all__ = ["__version__"]
