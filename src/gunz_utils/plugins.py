"""Failure-isolated entry-point plugin discovery."""

# =============================================================================
# STANDARD LIBRARY IMPORTS
# =============================================================================

from __future__ import annotations

import importlib.abc
import importlib.machinery
import importlib.util
import sys
from collections.abc import Sequence
from dataclasses import dataclass
from importlib.metadata import EntryPoint, entry_points
from pathlib import Path
from types import ModuleType
from typing import Any


@dataclass(frozen=True, slots=True)
class PluginInfo:
    """Stable metadata describing one discovered entry point."""

    name: str
    value: str
    group: str


@dataclass(frozen=True, slots=True)
class PluginLoadResult:
    """Result of loading one plugin without destabilizing sibling plugins."""

    info: PluginInfo
    plugin: Any | None = None
    error: str | None = None

    @property
    def ok(self) -> bool:
        """Return whether the plugin loaded successfully.

        Returns
        -------
        bool
            The result of the operation.
        """
        return self.error is None


def _entry_point_info(
    entry_point: EntryPoint,
    group: str,
) -> PluginInfo:
    """_entry_point_info() function.

    Parameters
    ----------
    entry_point : EntryPoint
        entry_point parameter.
    group : str
        group parameter.

    Returns
    -------
    PluginInfo
        The result of the operation.
    """
    return PluginInfo(entry_point.name, entry_point.value, group)


def discover_plugins(
    group: str,
    *,
    instantiate: bool = False,
) -> tuple[PluginLoadResult, ...]:
    """Discover and safely load plugins from an entry-point group.

    Failures expose only the exception type, not the exception message. This
    keeps plugin discovery diagnostics useful without copying arbitrary
    plugin-provided text that may contain credentials or other secrets.

    Ordinary exceptions become typed failures. BaseException subclasses such
    as cancellation, KeyboardInterrupt and SystemExit propagate.

    Parameters
    ----------
    group : str
        Python entry-point group to discover.
    instantiate : bool, default=False
        Call loaded entry-point objects with no arguments when true.

    Returns
    -------
    tuple[PluginLoadResult, ...]
        Deterministically ordered load results.
    """
    if not isinstance(group, str) or not group.strip():
        raise ValueError("group must be a non-empty string")
    if not isinstance(instantiate, bool):
        raise ValueError("instantiate must be bool")
    candidates = sorted(
        entry_points(group=group),
        key=lambda item: (item.name, item.value),
    )
    results: list[PluginLoadResult] = []
    for entry_point in candidates:
        info = _entry_point_info(entry_point, group)
        try:
            plugin = entry_point.load()
            if instantiate:
                if not callable(plugin):
                    raise TypeError("plugin is not callable")
                plugin = plugin()
        except Exception as exc:
            results.append(
                PluginLoadResult(
                    info=info,
                    error=type(exc).__name__,
                )
            )
        else:
            results.append(PluginLoadResult(info=info, plugin=plugin))
    return tuple(results)


_FILE_MODULE_PREFIX = "_gunz_file_"


class GunzFileFinder(importlib.abc.MetaPathFinder):
    """MetaPathFinder resolving synthetic module names with encoded paths."""

    def find_spec(self,
        fullname: str,
        path: Sequence[str] | None,
        target: ModuleType | None = None,
    ) -> importlib.machinery.ModuleSpec | None:
        if not fullname.startswith(_FILE_MODULE_PREFIX):
            return None
        hex_encoded = fullname[len(_FILE_MODULE_PREFIX) :]
        try:
            raw_path = bytes.fromhex(hex_encoded).decode("utf-8")
        except Exception:
            return None
        file_path = Path(raw_path)
        if not file_path.is_file():
            return None
        return importlib.util.spec_from_file_location(fullname, file_path)


_FINDER_INSTANCE: GunzFileFinder | None = None


def install_file_module_finder() -> GunzFileFinder:
    """Ensure GunzFileFinder is active on sys.meta_path."""
    global _FINDER_INSTANCE
    if _FINDER_INSTANCE is None:
        _FINDER_INSTANCE = GunzFileFinder()
    if _FINDER_INSTANCE not in sys.meta_path:
        sys.meta_path.insert(0, _FINDER_INSTANCE)
    return _FINDER_INSTANCE


def make_file_module_name(
    path: str | Path,
    prefix: str = _FILE_MODULE_PREFIX,
) -> str:
    """Generate a deterministic, reversible synthetic module name for a file path."""
    resolved_posix = Path(path).resolve().as_posix()
    hex_str = resolved_posix.encode("utf-8").hex()
    return f"{prefix}{hex_str}"


def load_module_from_path(
    path: str | Path,
    *,
    prefix: str = _FILE_MODULE_PREFIX,
    reload: bool = False,
) -> ModuleType:
    """Load a Python source file into sys.modules via synthetic module name.

    Parameters
    ----------
    path : str | Path
        Path to the Python source file.
    prefix : str, default="_gunz_file_"
        Synthetic module name prefix.
    reload : bool, default=False
        If True, reload module even if already present in sys.modules.

    Returns
    -------
    ModuleType
        The loaded Python module.

    Raises
    ------
    FileNotFoundError
        If path does not exist.
    ValueError
        If path is a symlink.
    ImportError
        If module spec creation fails.
    """
    target = Path(path).resolve()
    if not target.is_file():
        raise FileNotFoundError(f"Python source file not found: {target}")
    if target.is_symlink():
        raise ValueError("module file must not be a symbolic link")

    install_file_module_finder()
    module_name = make_file_module_name(target, prefix=prefix)

    if not reload and module_name in sys.modules:
        return sys.modules[module_name]

    spec = importlib.util.spec_from_file_location(module_name, target)
    if not spec or not spec.loader:
        raise ImportError(f"Cannot create module spec for {target}")

    mod = importlib.util.module_from_spec(spec)
    old_mod = sys.modules.get(module_name)
    sys.modules[module_name] = mod

    try:
        spec.loader.exec_module(mod)
    except BaseException:
        if old_mod is None:
            sys.modules.pop(module_name, None)
        else:
            sys.modules[module_name] = old_mod
        raise

    return mod


__all__ = [
    "GunzFileFinder",
    "PluginInfo",
    "PluginLoadResult",
    "discover_plugins",
    "install_file_module_finder",
    "load_module_from_path",
    "make_file_module_name",
]
