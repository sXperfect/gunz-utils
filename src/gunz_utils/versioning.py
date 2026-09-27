"""Small versioned-envelope and schema-migration primitives."""

from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass, field
from typing import Any


class SchemaMigrationError(ValueError):
    """Raised when a versioned payload cannot be validated or migrated."""


@dataclass(frozen=True, slots=True)
class VersionedEnvelope:
    """Wrap a payload with a stable schema name and positive integer version."""

    schema: str
    version: int
    payload: Any
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.schema:
            raise ValueError("schema must not be empty")
        if self.version < 1:
            raise ValueError("version must be at least 1")

    def to_dict(self) -> dict[str, Any]:
        """Return an envelope mapping suitable for JSON normalization."""
        return {
            "schema": self.schema,
            "version": self.version,
            "payload": self.payload,
            "metadata": dict(self.metadata),
        }

    @classmethod
    def from_dict(cls, value: Mapping[str, Any]) -> "VersionedEnvelope":
        """Validate and reconstruct an envelope from a mapping."""
        try:
            schema = value["schema"]
            version = value["version"]
            payload = value["payload"]
        except KeyError as exc:
            raise SchemaMigrationError(f"missing envelope field: {exc.args[0]}") from None
        metadata = value.get("metadata", {})
        if not isinstance(schema, str):
            raise SchemaMigrationError("schema must be a string")
        if not isinstance(version, int) or isinstance(version, bool):
            raise SchemaMigrationError("version must be an integer")
        if not isinstance(metadata, Mapping):
            raise SchemaMigrationError("metadata must be a mapping")
        return cls(schema, version, payload, dict(metadata))


Migration = Callable[[Any], Any]


class SchemaMigrator:
    """Register deterministic one-version-at-a-time payload migrations."""

    def __init__(self) -> None:
        self._migrations: dict[tuple[str, int], Migration] = {}

    def register(self, schema: str, from_version: int, migration: Migration) -> None:
        """Register a migration from version N to N+1."""
        if not schema:
            raise ValueError("schema must not be empty")
        if from_version < 1:
            raise ValueError("from_version must be at least 1")
        key = (schema, from_version)
        if key in self._migrations:
            raise ValueError(f"migration already registered for {schema!r} v{from_version}")
        self._migrations[key] = migration

    def migrate(
        self,
        envelope: VersionedEnvelope,
        *,
        target_version: int,
    ) -> VersionedEnvelope:
        """Migrate an envelope forward to target_version."""
        if target_version < envelope.version:
            raise SchemaMigrationError("schema downgrades are not supported")
        payload = envelope.payload
        version = envelope.version
        while version < target_version:
            migration = self._migrations.get((envelope.schema, version))
            if migration is None:
                raise SchemaMigrationError(
                    f"missing migration for {envelope.schema!r} v{version} -> v{version + 1}"
                )
            payload = migration(payload)
            version += 1
        return VersionedEnvelope(
            schema=envelope.schema,
            version=version,
            payload=payload,
            metadata=dict(envelope.metadata),
        )


__all__ = ["SchemaMigrationError", "SchemaMigrator", "VersionedEnvelope"]
