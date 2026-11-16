"""Layered typed configuration values with provenance."""

# =============================================================================
# STANDARD LIBRARY IMPORTS
# =============================================================================

from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from typing import Any, Generic, TypeVar

# =============================================================================
# LOCAL APPLICATION IMPORTS
# =============================================================================
from .dict_utils import deep_get, deep_merge

T = TypeVar("T")


@dataclass(frozen=True, slots=True)
class ConfigValue(Generic[T]):
    value: T
    source: str

    def __post_init__(self) -> None:
        if not isinstance(self.source, str) or not self.source.strip():
            raise ValueError("source must be a non-empty string")

    def __hash__(self) -> int:
        try:
            return hash((self.value, self.source))
        except TypeError:
            return hash(self.source)


class LayeredConfig:
    """Multi-layer hierarchical configuration combining defaults, config files, and
    overrides.
    """

    def __init__(self,
        layers: Sequence[tuple[str, Mapping[str, Any]]] | None = None,
    ) -> None:
        self._layers: list[tuple[str, dict[str, Any]]] = []
        if layers:
            for name, mapping in layers:
                self.add_layer(name, mapping)

    def add_layer(self,
        name: str,
        mapping: Mapping[str, Any],
    ) -> None:
        """Add a configuration layer with highest precedence (applied on top)."""
        if not isinstance(name, str) or not name.strip():
            raise ValueError("layer name must be a non-empty string")
        if not isinstance(mapping, Mapping):
            raise TypeError(
                f"layer mapping must be a Mapping, got {type(mapping).__name__}")
        self._layers.append((name, dict(mapping)))

    @property
    def layers(self) -> list[str]:
        """Return layer names from lowest precedence to highest precedence."""
        return [name for name, _ in self._layers]

    def get(self,
        path: str | Sequence[str | int],
        default: Any = None,
    ) -> Any:
        """Retrieve a value by dotted-path from the highest-precedence layer that
        defines it.
        """
        try:
            return self[path]
        except KeyError:
            return default

    def __getitem__(self,
        path: str | Sequence[str | int],
    ) -> Any:
        for _, mapping in reversed(self._layers):
            try:
                return deep_get(mapping, path)
            except KeyError:
                continue
        raise KeyError(
    path if isinstance(
        path,
        str) else ".".join(
            str(p) for p in path))

    def __contains__(self,
        path: str | Sequence[str | int],
    ) -> bool:
        for _, mapping in reversed(self._layers):
            try:
                deep_get(mapping, path)
                return True
            except KeyError:
                continue
        return False

    def get_provenance(self,
        path: str | Sequence[str | int],
    ) -> ConfigValue[Any] | None:
        """Return a ConfigValue containing the value and source layer name that supplied
        it.
        """
        for name, mapping in reversed(self._layers):
            try:
                val = deep_get(mapping, path)
                return ConfigValue(value=val, source=name)
            except KeyError:
                continue
        return None

    def to_dict(self) -> dict[str, Any]:
        """Merge all layers from lowest to highest precedence into a single dictionary.
        """
        result: dict[str, Any] = {}
        for _, mapping in self._layers:
            result = deep_merge(result, mapping)
        return result


def parse_bool(
    value: str,
) -> bool:
    """parse_bool() function.

    Parameters
    ----------
    value : str
        value parameter.

    Returns
    -------
    bool
        The result of the operation.
    """
    normalized = value.strip().lower()
    if normalized in {"1", "true", "yes", "on"}:
        return True
    if normalized in {"0", "false", "no", "off"}:
        return False
    raise ValueError(f"invalid boolean: {value!r}")


def convert(
    value: str,
    parser: Callable[[str], T],
    *,
    source: str = "environment",
) -> ConfigValue[T]:
    """convert() function.

    Parameters
    ----------
    value : str
        value parameter.
    parser : Callable[[str], T]
        parser parameter.
    source : str
        source parameter.

    Returns
    -------
    ConfigValue[T]
        The result of the operation.
    """
    if not callable(parser):
        raise TypeError("parser must be callable")
    return ConfigValue(parser(value), source)


__all__ = ["ConfigValue", "LayeredConfig", "convert", "parse_bool"]
