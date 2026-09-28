"""PerformanceRun schema validation and migration."""

from __future__ import annotations

from typing import Any

PERFORMANCE_SCHEMA_VERSION = 1


class PerformanceSchemaError(ValueError):
    """Raised when serialized performance data violates the schema contract."""


def validate_performance_run(data: dict[str, Any]) -> None:
    """Validate required PerformanceRun fields and supported schema version."""
    version = data.get("schema_version")
    if (
        isinstance(version, bool)
        or not isinstance(version, int)
        or version != PERFORMANCE_SCHEMA_VERSION
    ):
        raise PerformanceSchemaError(
            f"unsupported PerformanceRun schema version: {version!r}"
        )
    if not isinstance(data.get("name"), str) or not data["name"]:
        raise PerformanceSchemaError("PerformanceRun.name must be non-empty")
    if not isinstance(data.get("system"), dict):
        raise PerformanceSchemaError("PerformanceRun.system must be an object")
    if not isinstance(data.get("parameters", {}), dict):
        raise PerformanceSchemaError("PerformanceRun.parameters must be an object")
    if not isinstance(data.get("metrics", {}), dict):
        raise PerformanceSchemaError("PerformanceRun.metrics must be an object")
    if not isinstance(data.get("artifacts", []), list):
        raise PerformanceSchemaError("PerformanceRun.artifacts must be an array")


def migrate_performance_run(data: dict[str, Any]) -> dict[str, Any]:
    """Migrate supported historical PerformanceRun mappings to current schema."""
    version = data.get("schema_version", 1)
    migrated = dict(data)
    if (
        isinstance(version, int)
        and not isinstance(version, bool)
        and version == 1
    ):
        migrated.setdefault("parameters", {})
        migrated.setdefault("metrics", {})
        migrated.setdefault("artifacts", [])
        migrated.setdefault("warnings", [])
        migrated["schema_version"] = PERFORMANCE_SCHEMA_VERSION
        validate_performance_run(migrated)
        return migrated
    raise PerformanceSchemaError(f"cannot migrate schema version {version!r}")


__all__ = [
    "PERFORMANCE_SCHEMA_VERSION",
    "PerformanceSchemaError",
    "migrate_performance_run",
    "validate_performance_run",
]
