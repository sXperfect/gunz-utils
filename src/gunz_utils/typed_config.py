"""Layered typed configuration values with provenance."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Generic, TypeVar, Callable

T = TypeVar("T")


@dataclass(frozen=True)
class ConfigValue(Generic[T]):
    value: T
    source: str


def parse_bool(value: str) -> bool:
    normalized = value.strip().lower()
    if normalized in {"1", "true", "yes", "on"}:
        return True
    if normalized in {"0", "false", "no", "off"}:
        return False
    raise ValueError(f"invalid boolean: {value!r}")


def convert(value: str, parser: Callable[[str], T], *, source: str = "environment") -> ConfigValue[T]:
    return ConfigValue(parser(value), source)


__all__ = ["ConfigValue", "convert", "parse_bool"]
