"""Failure-isolated entry-point plugin discovery."""

from __future__ import annotations

from dataclasses import dataclass
from importlib.metadata import EntryPoint, entry_points
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
        """Return whether the plugin loaded successfully."""
        return self.error is None


def _entry_point_info(entry_point: EntryPoint, group: str) -> PluginInfo:
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


__all__ = ["PluginInfo", "PluginLoadResult", "discover_plugins"]
