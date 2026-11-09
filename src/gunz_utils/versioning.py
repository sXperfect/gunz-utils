"""Small versioned-envelope and schema-migration primitives."""

# =============================================================================
# STANDARD LIBRARY IMPORTS
# =============================================================================

from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass, field
from types import MappingProxyType
from typing import Any


class SchemaMigrationError(ValueError):
    """Raised when a versioned payload cannot be validated or migrated."""


def _validate_version(
    value: object,
    *,
    name: str,
) -> int:
    """_validate_version() function.

    Parameters
    ----------
    value : object
        value parameter.
    name : str
        name parameter.

    Returns
    -------
    int
        The result of the operation.
    """
    if not isinstance(value, int) or isinstance(value, bool):
        raise ValueError(f"{name} must be an integer")
    if value < 1:
        raise ValueError(f"{name} must be at least 1")
    return value


@dataclass(frozen=True, slots=True)
class VersionedEnvelope:
    """Wrap a payload with a stable schema name and positive integer version."""

    schema: str
    version: int
    payload: Any
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not isinstance(self.schema, str):
            raise TypeError("schema must be a string")
        if not self.schema.strip():
            raise ValueError("schema must not be empty")
        _validate_version(self.version, name="version")
        if not isinstance(self.metadata, Mapping):
            raise TypeError("metadata must be a mapping")
        object.__setattr__(self, "metadata", MappingProxyType(dict(self.metadata)))

    def to_dict(self) -> dict[str, Any]:
        """Return an envelope mapping suitable for JSON normalization.

        Returns
        -------
        dict[str, Any]
            The result of the operation.
        """
        return {
            "schema": self.schema,
            "version": self.version,
            "payload": self.payload,
            "metadata": dict(self.metadata),
        }

    @classmethod
    def from_dict(cls,
        value: Mapping[str, Any],
    ) -> VersionedEnvelope:
        """Validate and reconstruct an envelope from a mapping.

        Parameters
        ----------
        value : Mapping[str, Any]
            value parameter.

        Returns
        -------
        VersionedEnvelope
            The result of the operation.
        """
        if not isinstance(value, Mapping):
            raise SchemaMigrationError("envelope must be a mapping")
        try:
            schema = value["schema"]
            version = value["version"]
            payload = value["payload"]
        except KeyError as exc:
            raise SchemaMigrationError(
                f"missing envelope field: {exc.args[0]}"
            ) from None
        metadata = value.get("metadata", {})
        if not isinstance(schema, str):
            raise SchemaMigrationError("schema must be a string")
        if not schema.strip():
            raise SchemaMigrationError("schema must not be empty")
        if not isinstance(version, int) or isinstance(version, bool):
            raise SchemaMigrationError("version must be an integer")
        if version < 1:
            raise SchemaMigrationError("version must be at least 1")
        if not isinstance(metadata, Mapping):
            raise SchemaMigrationError("metadata must be a mapping")
        return cls(schema, version, payload, dict(metadata))


Migration = Callable[[Any], Any]


class SchemaMigrator:
    """Register deterministic one-version-at-a-time payload migrations."""

    def __init__(self) -> None:
        self._migrations: dict[tuple[str, int], Migration] = {}

    def register(self,
        schema: str,
        from_version: int,
        migration: Migration,
    ) -> None:
        """Register a migration from version N to N+1.

        Parameters
        ----------
        schema : str
            schema parameter.
        from_version : int
            from_version parameter.
        migration : Migration
            migration parameter.
        """
        if not isinstance(schema, str):
            raise TypeError("schema must be a string")
        if not schema.strip():
            raise ValueError("schema must not be empty")
        _validate_version(from_version, name="from_version")
        if not callable(migration):
            raise TypeError("migration must be callable")
        key = (schema, from_version)
        if key in self._migrations:
            raise ValueError(
                f"migration already registered for {schema!r} "
                f"v{from_version}"
            )
        self._migrations[key] = migration

    def can_migrate(
        self,
        schema_or_envelope: str | VersionedEnvelope,
        from_version: int | None = None,
        *,
        target_version: int,
    ) -> bool:
        """Check whether a full migration path exists to target_version.

        Parameters
        ----------
        schema_or_envelope : str | VersionedEnvelope
            Schema name string or VersionedEnvelope instance.
        from_version : int | None
            Starting version (required if schema is a string).
        target_version : int
            Target schema version.

        Returns
        -------
        bool
            True if all intermediate migration steps are registered.
        """
        if isinstance(schema_or_envelope, VersionedEnvelope):
            schema = schema_or_envelope.schema
            from_v = schema_or_envelope.version
        elif isinstance(schema_or_envelope, str):
            schema = schema_or_envelope
            if from_version is None:
                raise ValueError("from_version must be provided when schema is a string")
            from_v = from_version
        else:
            raise TypeError("first argument must be a schema string or VersionedEnvelope")
        if target_version < from_v:
            return False
        v = from_v
        while v < target_version:
            if (schema, v) not in self._migrations:
                return False
            v += 1
        return True

    def latest_version(
        self,
        schema: str,
    ) -> int | None:
        """Return the highest reachable version registered for a schema.

        Parameters
        ----------
        schema : str
            Schema name.

        Returns
        -------
        int | None
            Highest version number, or None if no migrations exist.
        """
        versions = [from_v + 1 for (s, from_v) in self._migrations if s == schema]
        return max(versions) if versions else None

    def migrate(self,
        envelope: VersionedEnvelope,
        *,
        target_version: int,
    ) -> VersionedEnvelope:
        """Migrate an envelope forward to target_version.

        Parameters
        ----------
        envelope : VersionedEnvelope
            envelope parameter.
        target_version : int
            target_version parameter.

        Returns
        -------
        VersionedEnvelope
            The result of the operation.
        """
        if not isinstance(envelope, VersionedEnvelope):
            raise TypeError("envelope must be a VersionedEnvelope")
        _validate_version(target_version, name="target_version")
        if target_version < envelope.version:
            raise SchemaMigrationError("schema downgrades are not supported")
        payload = envelope.payload
        version = envelope.version
        while version < target_version:
            migration = self._migrations.get((envelope.schema, version))
            if migration is None:
                raise SchemaMigrationError(
                    f"missing migration for {envelope.schema!r} "
                    f"v{version} -> v{version + 1}"
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
