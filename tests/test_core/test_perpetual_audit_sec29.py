"""Perpetual security audit phase 29 (round 4, deepest).

Re-audit of ``partitions``, ``pipeline``, ``plugins``, ``identifiers``, and
``versioning``.

Findings:

1. ``versioning.SchemaMigrator.migrate`` raises plain ``ValueError`` (not the
   migration-domain ``SchemaMigrationError``) for an invalid ``target_version``.

   migrate() calls ``_validate_version(target_version, ...)``
   (versioning.py:179) which raises ``ValueError`` for a non-positive integer
   (versioning.py:39-41).  The same method raises ``SchemaMigrationError`` for
   the downgrade case (``target_version < envelope.version``,
   versioning.py:181-182) and ``SchemaMigrationError`` is the documented error
   type for migration-domain failures (a subclass of ``ValueError``).  A caller
   that catches ``SchemaMigrationError`` to handle migration failures
   (as the API suggests) silently misses an invalid ``target_version`` such as
   ``0``, which leaks out as an untyped ``ValueError`` instead.  ``migrate``
   should surface the invalid-target case as ``SchemaMigrationError`` for
   consistency with the downgrade path and ``VersionedEnvelope.from_dict``
   (which raises ``SchemaMigrationError`` for ``version < 1``).

2. ``partitions.PartitionManifest.fingerprint`` is order-dependent over the
   item identifiers within each partition, so semantically-identical partition
   assignments (same item *sets* per partition, different iteration order)
   produce different fingerprints.

   fingerprint() (partitions.py:95-104) hashes ``{name: list(identifiers)}``
   with the identifiers kept in their original (unsorted) order, so
   ``{'a': ['x', 'y'], 'b': ['z']}`` and ``{'a': ['y', 'x'], 'b': ['z']}`` --
   which validate as the *same* disjoint assignment -- hash differently.  For
   a "stable manifest" whose fingerprint is documented as a "deterministic
   fingerprint of partition assignments", this means reordering items (with no
   semantic change) changes the identity used for cache keys / change
   detection.  The fingerprint should be canonical over the assignment
   (identifiers sorted within each partition) so the same assignment always
   hashes identically.
"""

import pytest

from gunz_utils.partitions import PartitionManifest
from gunz_utils.versioning import (
    SchemaMigrationError,
    SchemaMigrator,
    VersionedEnvelope,
)

# ---------------------------------------------------------------------------
# Finding 1: SchemaMigrator.migrate raises the wrong error type for target<1
# ---------------------------------------------------------------------------


def test_migrate_invalid_target_version_raises_schema_migration_error():
    """RED: ``migrate(target_version=0)`` currently leaks a plain ``ValueError``
    from ``_validate_version`` instead of the migration-domain
    ``SchemaMigrationError``, so a caller handling migration failures via
    ``SchemaMigrationError`` misses the invalid-target case.
    """
    migrator = SchemaMigrator()
    migrator.register("s", 1, lambda payload: {**payload, "v2": True})
    envelope = VersionedEnvelope("s", 1, {"a": 1})
    with pytest.raises(SchemaMigrationError):
        migrator.migrate(envelope, target_version=0)


def test_migrate_downgrade_raises_schema_migration_error():
    """GREEN: a downgrade (``target_version < envelope.version``) already raises
    ``SchemaMigrationError``; this pins the consistent error type the
    invalid-target case should also use.
    """
    migrator = SchemaMigrator()
    envelope = VersionedEnvelope("s", 2, {})
    with pytest.raises(SchemaMigrationError):
        migrator.migrate(envelope, target_version=1)


def test_migrate_to_same_version_is_noop():
    """GREEN: migrating to the current version returns an unchanged envelope
    (no migration is applied and the payload/version are preserved).
    """
    migrator = SchemaMigrator()
    envelope = VersionedEnvelope("s", 1, {"a": 1})
    result = migrator.migrate(envelope, target_version=1)
    assert result.version == 1
    assert result.payload == {"a": 1}


# ---------------------------------------------------------------------------
# Finding 2: PartitionManifest.fingerprint is order-dependent
# ---------------------------------------------------------------------------


def test_fingerprint_is_order_independent_over_assignment():
    """RED: two manifests representing the *same* partition assignment (same
    item sets per partition, different item order) currently produce different
    fingerprints (partitions.py:95-104 hashes unsorted identifiers).  The
    fingerprint is documented as a "deterministic fingerprint of partition
    assignments" and must be canonical over the assignment.
    """
    first = PartitionManifest({"a": ["x", "y"], "b": ["z"]})
    second = PartitionManifest({"a": ["y", "x"], "b": ["z"]})
    assert first.fingerprint == second.fingerprint


def test_fingerprint_is_deterministic_for_identical_manifest():
    """GREEN: identical manifests yield identical fingerprints, and a manifest
    is validated as the same disjoint assignment regardless of the item order
    in its partitions.
    """
    first = PartitionManifest({"a": ["x", "y"], "b": ["z"]})
    second = PartitionManifest({"a": ["x", "y"], "b": ["z"]})
    assert first.fingerprint == second.fingerprint
    # Both orderings validate as the same valid disjoint assignment; only the
    # fingerprint (not the validation) should be order-insensitive.
    first.validate()
    second.validate()
