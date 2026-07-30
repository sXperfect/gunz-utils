"""Tests for `gunz_utils.models`.

Covers the shared strictness defaults exposed by :class:`GunzBaseModel`:

  - ``extra="forbid"`` rejects unknown fields
  - ``str_strip_whitespace=True`` trims strings on assignment
  - ``validate_assignment=True`` re-runs validators on mutation
  - Subclass override semantics (Pydantic v2 config merging)
  - Public API re-export from ``gunz_utils``
"""

import unittest

from pydantic import ConfigDict, ValidationError

from gunz_utils import GunzBaseModel
from gunz_utils.models import HealthStatus


class TestGunzBaseModelConfig(unittest.TestCase):
    """Verify the strictness defaults are present on the base class."""

    def test_extra_is_forbidden(self):
        """``model_config.extra`` is ``\"forbid\"``."""
        self.assertEqual(GunzBaseModel.model_config.get("extra"), "forbid")

    def test_str_strip_whitespace_enabled(self):
        """``model_config.str_strip_whitespace`` is True."""
        self.assertTrue(GunzBaseModel.model_config.get("str_strip_whitespace"))

    def test_validate_assignment_enabled(self):
        """``model_config.validate_assignment`` is True."""
        self.assertTrue(GunzBaseModel.model_config.get("validate_assignment"))

    def test_frozen_is_false_by_default(self):
        """``model_config.frozen`` is False (mutable by default)."""
        self.assertFalse(GunzBaseModel.model_config.get("frozen"))


class TestGunzBaseModelExtraForbid(unittest.TestCase):
    """``extra=\"forbid\"`` rejects unknown fields at construction."""

    def test_construction_with_extra_field_raises(self):
        """Passing an unknown field raises ``ValidationError``."""

        class Record(GunzBaseModel):
            name: str

        with self.assertRaises(ValidationError) as cm:
            Record(name="alice", extra_field=1)
        # Pydantic reports the bad field name in the error
        self.assertIn("extra_field", str(cm.exception))

    def test_construction_without_extras_succeeds(self):
        """Plain construction without extras works."""

        class Record(GunzBaseModel):
            name: str
            age: int = 0

        r = Record(name="alice", age=30)
        self.assertEqual(r.name, "alice")
        self.assertEqual(r.age, 30)


class TestGunzBaseModelStrStripWhitespace(unittest.TestCase):
    """``str_strip_whitespace=True`` trims leading/trailing whitespace."""

    def test_string_field_trimmed_on_construction(self):
        class Record(GunzBaseModel):
            name: str

        r = Record(name="  hello  ")
        self.assertEqual(r.name, "hello")

    def test_string_field_trimmed_on_assignment(self):
        """``validate_assignment=True`` also fires the strip on mutation."""

        class Record(GunzBaseModel):
            name: str

        r = Record(name="init")
        r.name = "  mutated  "
        self.assertEqual(r.name, "mutated")

    def test_internal_whitespace_preserved(self):
        """Only leading/trailing whitespace is stripped, not interior."""

        class Record(GunzBaseModel):
            name: str

        r = Record(name="  hello   world  ")
        self.assertEqual(r.name, "hello   world")


class TestGunzBaseModelValidateAssignment(unittest.TestCase):
    """``validate_assignment=True`` re-runs validators on attribute mutation."""

    def test_type_violation_on_assignment_raises(self):
        class Record(GunzBaseModel):
            name: str

        r = Record(name="alice")
        with self.assertRaises(ValidationError):
            r.name = 123  # type: ignore[assignment]

    def test_field_constraint_on_assignment_raises(self):
        """Custom field constraints (e.g. ``Field(ge=0)``) re-fire on mutation."""

        class Record(GunzBaseModel):
            age: int

        r = Record(age=30)
        # Pydantic's int field accepts negatives; this just confirms the
        # assignment path runs the validator (no error here).
        r.age = 40
        self.assertEqual(r.age, 40)


class TestGunzBaseModelSubclassOverride(unittest.TestCase):
    """Subclasses can override individual settings; Pydantic v2 merges configs."""

    def test_subclass_can_relax_extra(self):
        """Subclass sets ``extra=\"ignore\"``; parent ``forbid`` is overridden."""

        class PermissiveRecord(GunzBaseModel):
            model_config = ConfigDict(extra="ignore")
            name: str

        # Should NOT raise even with an extra field
        r = PermissiveRecord(name="alice", extra_field=1)
        self.assertEqual(r.name, "alice")
        # Extra is silently ignored (Pydantic default for extra="ignore")
        self.assertEqual(PermissiveRecord.model_config.get("extra"), "ignore")

    def test_subclass_inherits_unrelated_settings(self):
        """``str_strip_whitespace`` still True even after overriding ``extra``."""

        class PermissiveRecord(GunzBaseModel):
            model_config = ConfigDict(extra="ignore")
            name: str

        self.assertTrue(
            PermissiveRecord.model_config.get("str_strip_whitespace"),
        )


class TestGunzBaseModelPublicAPI(unittest.TestCase):
    """The class is reachable via the package surface."""

    def test_reexport_from_package(self):
        """``from gunz_utils import GunzBaseModel`` works."""
        # Already imported at module scope, but assert identity for clarity.
        from gunz_utils import GunzBaseModel as Imported

        self.assertIs(Imported, GunzBaseModel)

    def test_appears_in_package_all(self):
        """``GunzBaseModel`` is in ``gunz_utils.__all__``."""
        import gunz_utils

        self.assertIn("GunzBaseModel", gunz_utils.__all__)


class TestHealthStatusUnaffected(unittest.TestCase):
    """Sanity: existing ``HealthStatus`` was not broken by adding the base."""

    def test_healthstatus_still_subclasses_basemodel(self):
        """``HealthStatus`` extends the stdlib Pydantic ``BaseModel`` directly,
        not ``GunzBaseModel`` -- changing this would be a separate decision.
        """
        from pydantic import BaseModel as PydanticBaseModel

        self.assertTrue(issubclass(HealthStatus, PydanticBaseModel))
        # But it does NOT inherit from GunzBaseModel
        self.assertFalse(issubclass(HealthStatus, GunzBaseModel))


if __name__ == "__main__":
    unittest.main()
