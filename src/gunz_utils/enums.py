"""
Base Enum Utilities.

This module provides custom base classes for StrEnum and IntEnum to handle
common case-insensitive, separator-insensitive matching, and alias support
for creating enum members. It leverages modern Python 3.11+ features.
"""

# =============================================================================
# METADATA
# =============================================================================
__author__ = "Yeremia Gunawan Adhisantoso"
__email__ = "adhisant@tnt.uni-hannover.de"
__license__ = "Clear BSD"

# =============================================================================
# STANDARD LIBRARY IMPORTS
# =============================================================================
import enum
from typing import Any, ClassVar, Self, TypeVar, cast

# =============================================================================
# TYPE VARIABLES
# =============================================================================
T = TypeVar("T", bound="BaseStrEnum")

# =============================================================================
# CONSTANTS
# =============================================================================
# ? Default security limit on input string length. Subclasses may override
# ? this class attribute (e.g. for long-context models that need larger
# ? lookup keys) via `__init_subclass__` or direct attribute override.
DEFAULT_MAX_INPUT_LENGTH = 1024  # Security: Prevent DoS via long strings

# ? Backward-compat alias for the module-level constant. New code should
# ? reference `cls.DEFAULT_MAX_INPUT_LENGTH` (the class attribute).
_MAX_INPUT_LENGTH = DEFAULT_MAX_INPUT_LENGTH

# ? mypy cannot see StrEnum ``ClassVar`` attributes as their declared type
# ? (it resolves ``cls.<attr>`` to the enum member type instead), and ruff's
# ? B009 rejects ``getattr`` with a constant name. These private, per-class
# ? lookup maps are therefore stored at module level, keyed by the enum class.
_FUZZY_LOOKUP_MAPS: dict[type, dict[str, Any]] = {}
_NAME_LOOKUP_MAPS: dict[type, dict[str, Any]] = {}


def _max_input_length(cls: type) -> int:
    """Return the effective input-length limit for ``cls``, honoring overrides.

    Reads the resolved ``DEFAULT_MAX_INPUT_LENGTH`` from the class ``__dict__``
    across the MRO because direct ``cls.<attr>`` access on StrEnum resolves to
    the enum member type in mypy (see note above). Falls back to the module
    default when no class in the MRO declares an integer limit.
    """
    for klass in cls.__mro__:
        value = klass.__dict__.get("DEFAULT_MAX_INPUT_LENGTH")
        if isinstance(value, int):
            return value
    return DEFAULT_MAX_INPUT_LENGTH


# =============================================================================
# BASE ENUM IMPLEMENTATION
# =============================================================================
@enum.verify(enum.UNIQUE)
class BaseStrEnum(enum.StrEnum):
    """
    A base class for StrEnum that provides robust matching and alias support.

    Features:
    - Case-insensitive matching.
    - Separator-insensitive matching (treats spaces, dashes, underscores as same).
    - Alias support via the `__ALIASES__` class attribute.
    - Introspection helpers (names, values, items).
    - Safe lookup (get_or_none).

    Examples
    --------
    >>> class Color(BaseStrEnum):
    ...     __ALIASES__ = {"dark": "dark_blue"}
    ...     DARK_BLUE = "dark_blue"
    ...     LIGHT_GREEN = "light green"
    ...
    >>> Color.from_fuzzy_string("DARK_BLUE") is Color.DARK_BLUE
    True
    >>> Color.from_fuzzy_string("dark-blue") is Color.DARK_BLUE
    True
    >>> Color.from_fuzzy_string("dark") is Color.DARK_BLUE
    True
    """

    # ? Dictionary mapping lowercase aliases to actual enum values
    # ? Using dunder name to avoid it being treated as an Enum member
    __ALIASES__: ClassVar[dict[str, str]] = {}

    #? Declared as ClassVar so mypy sees it on `type[Self]`. The actual
    #? assignment happens after the class body because StrEnum rejects
    #? non-string attributes inside the body (see note at line 216).
    DEFAULT_MAX_INPUT_LENGTH: ClassVar[int]

    @classmethod
    def _get_fuzzy_map(cls) -> dict[str, Self]:
        """
        Lazily builds and returns a mapping for fuzzy lookups.
        Key is the normalized string or lowercase name.
        Value is the enum member.
        """
        existing = _FUZZY_LOOKUP_MAPS.get(cls)
        if existing is not None:
            return existing
        lookup_map: dict[str, Self] = {}
        for member in cls:
            # Add normalized value
            val_lower = member.value.lower()
            val_norm = val_lower.replace("-", "_").replace(" ", "_")
            if val_norm not in lookup_map:
                lookup_map[val_norm] = member

            # Add raw lowercase value
            # (optimization for inputs matching value but with separators)
            if val_lower not in lookup_map:
                lookup_map[val_lower] = member

            # Add lowercase name
            name_lower = member.name.lower()
            if name_lower not in lookup_map:
                lookup_map[name_lower] = member

        _FUZZY_LOOKUP_MAPS[cls] = lookup_map
        return lookup_map

    @classmethod
    def from_fuzzy_string(cls, value_str: str) -> Self:
        """
        Attempts to find a member by alias, normalized value, or case-insensitive name.
        Raises ValueError if no match is found.
        """
        # Security check to prevent DoS via excessive string processing.
        # Uses the class attribute so subclasses can override the limit.
        max_len = _max_input_length(cls)
        if len(value_str) > max_len:
            raise ValueError(f"Input string too long (max {max_len} chars)")

        value_lower = value_str.lower()
        _aliases = cls.__ALIASES__

        # 1. Check for defined aliases (string -> target_string_value)
        if value_lower in _aliases:
            alias_target_value = _aliases[value_lower]

            # Check internal map first
            if alias_target_value in cls._value2member_map_:
                #? mypy's enum stubs type _value2member_map_ as dict[Any, Any];
                #? the runtime value is Self, so cast at the boundary.
                return cast(Self, cls._value2member_map_[alias_target_value])

            # Fallback to instantiation (should work if valid member)
            try:
                return cls(alias_target_value)
            except ValueError as exc:
                raise ValueError(
                    f"Alias target '{alias_target_value}' is not a valid "
                    f"member value for {cls.__name__}"
                ) from exc

        # 2. Check for matches in the fuzzy map
        # Optimization: Use cached lookup map instead of iterating
        fuzzy_map = cls._get_fuzzy_map()

        # Check raw lowercase input first (avoids normalization if unnecessary)
        # This catches direct name matches or values that are already normalized
        if value_lower in fuzzy_map:
            return fuzzy_map[value_lower]

        # 3. Normalize separators and case for fuzzy matching
        normalized_value_input = value_lower.replace("-", "_").replace(" ", "_")

        if normalized_value_input in fuzzy_map:
            return fuzzy_map[normalized_value_input]

        valid_options = ", ".join(f"'{m.value}'" for m in cls)
        raise ValueError(
            f"'{value_str}' is not a valid {cls.__name__}. "
            f"Please use one of: {valid_options}"
        )

    @classmethod
    def names(cls) -> list[str]:
        """Returns a list of all member names."""
        return [member.name for member in cls]

    @classmethod
    def values(cls) -> list[str]:
        """Returns a list of all member values."""
        return [member.value for member in cls]

    @classmethod
    def items(cls) -> list[tuple[str, str]]:
        """Returns a list of (name, value) tuples."""
        return [(member.name, member.value) for member in cls]

    @classmethod
    def get_or_none(cls, value: object) -> Self | None:
        """
        Safely attempts to get an enum member. Returns None if invalid.
        """
        if isinstance(value, cls):
            return value

        try:
            #? `value: object` requires a runtime narrowing before cls()
            #? will accept it; we already guard ValueError/TypeError.
            return cls(cast("str", value))
        except (ValueError, TypeError):
            pass

        if isinstance(value, str):
            try:
                return cls.from_fuzzy_string(value)
            except ValueError:
                pass

        return None

    @classmethod
    def choices(cls) -> list[str]:
        return cls.values()


# ? Default security limit on input string length. Subclasses may override
# ? this class attribute (e.g. for long-context models that need larger
# ? lookup keys) via `MyEnum.DEFAULT_MAX_INPUT_LENGTH = 4096`.
# ?
# ? Set via setattr after class body (StrEnum rejects non-string class
# ? attributes like int = 1024 inside the class body, even when annotated
# ? as ClassVar[int]). The class-body `__ALIASES__` field works because
# ? `{}` is a falsy/empty value that StrEnum's machinery silently skips.
# ?
# ? Security rationale: 1k chars is safe; 100k chars can take seconds
# ? on slow hardware (regex backtracking is O(n) on `val_norm.replace`).
BaseStrEnum.DEFAULT_MAX_INPUT_LENGTH = 1024


@enum.verify(enum.UNIQUE)
class OptionalBaseStrEnum(BaseStrEnum):
    """
    A base class for StrEnum that treats None as the NONE enum member.
    """

    __ALIASES__: ClassVar[dict[str, str]] = {}

    #? Subclasses must define a NONE member (enforced in __init_subclass__).
    #? Declared so mypy recognises `cls.NONE` in `_missing_`.
    NONE: ClassVar[Self]

    def __init_subclass__(cls, **kwargs: Any) -> None:
        super().__init_subclass__(**kwargs)
        if "NONE" not in cls.__members__:
            raise TypeError(
                f"Class {cls.__name__} must define a NONE member when inheriting "
                f"from {OptionalBaseStrEnum.__name__}. Example: NONE = 'none'"
            )

    @classmethod
    def _missing_(cls, value: object) -> Self:
        if value is None:
            return cls.__members__["NONE"]

        # Try fuzzy match via helper, but do NOT retry cls(value) to avoid recursion
        if isinstance(value, str):
            try:
                return cls.from_fuzzy_string(value)
            except ValueError:
                pass  # let super raise

        #? Enum._missing_ returns Self | None in stubs but the protocol
        #? guarantees a member on success or raises. Cast to Self since
        #? this branch only runs after the string-fuzzy path has failed.
        return cast(Self, super()._missing_(value))


@enum.verify(enum.UNIQUE)
class BaseIntEnum(enum.IntEnum):
    """
    A base class for IntEnum that provides string-based lookup and alias support.

    Examples
    --------
    >>> class ErrorCode(BaseIntEnum):
    ...     __ALIASES__ = {"missing": 404}
    ...     NOT_FOUND = 404
    ...
    >>> ErrorCode.from_fuzzy_int_string("missing") is ErrorCode.NOT_FOUND
    True
    """

    __ALIASES__: ClassVar[dict[str, int]] = {}

    #? Declared as ClassVar so mypy sees it on `type[Self]`. The actual
    #? assignment happens after the class body because IntEnum rejects
    #? non-int attributes inside the body.
    DEFAULT_MAX_INPUT_LENGTH: ClassVar[int]

    @classmethod
    def _get_name_lookup_map(cls) -> dict[str, Self]:
        """
        Lazily builds and returns a mapping from lowercase name to enum member.
        """
        existing = _NAME_LOOKUP_MAPS.get(cls)
        if existing is not None:
            return existing
        lookup_map: dict[str, Self] = {}
        for member in cls:
            name_lower = member.name.lower()
            if name_lower not in lookup_map:
                lookup_map[name_lower] = member
        _NAME_LOOKUP_MAPS[cls] = lookup_map
        return lookup_map

    @classmethod
    def from_fuzzy_int_string(cls, value_str: str) -> Self:
        """
        Attempts to find a member by alias (string->int), case-insensitive name, or
        string-to-int conversion.
        """
        # Security check to prevent DoS via excessive string processing.
        # Uses the class attribute so subclasses can override the limit.
        max_len = _max_input_length(cls)
        if len(value_str) > max_len:
            raise ValueError(f"Input string too long (max {max_len} chars)")

        value_lower = value_str.lower()
        _aliases = cls.__ALIASES__

        # 1. Check for aliases (string -> int_value)
        if value_lower in _aliases:
            int_target_value = _aliases[value_lower]

            if int_target_value in cls._value2member_map_:
                #? mypy's enum stubs type _value2member_map_ as dict[Any, Any];
                #? the runtime value is Self, so cast at the boundary.
                return cast(Self, cls._value2member_map_[int_target_value])

            try:
                return cls(int_target_value)
            except ValueError as exc:
                raise ValueError(
                    f"Alias target '{int_target_value}' is not a valid "
                    f"member value for {cls.__name__}"
                ) from exc

        # 2. Check for member name matches (case-insensitive)
        # Optimization: Use cached lookup map instead of iterating
        name_map = cls._get_name_lookup_map()
        if value_lower in name_map:
            return name_map[value_lower]

        # 3. Try to convert to int if it's a string representation of a number
        try:
            int_value = int(value_str)
            if int_value in cls._value2member_map_:
                #? mypy's enum stubs type _value2member_map_ as dict[Any, Any];
                #? the runtime value is Self, so cast at the boundary.
                return cast(Self, cls._value2member_map_[int_value])
            return cls(int_value)
        except (ValueError, TypeError):
            #? Conversion failure is expected for symbolic names, which are
            #? reported uniformly with the valid integer choices below.
            pass

        valid_options = ", ".join(f"'{m.value}'" for m in cls)
        raise ValueError(
            f"'{value_str}' is not a valid {cls.__name__}. "
            f"Please use one of: {valid_options}"
        )

    @classmethod
    def names(cls) -> list[str]:
        return [member.name for member in cls]

    @classmethod
    def values(cls) -> list[int]:
        return [member.value for member in cls]

    @classmethod
    def items(cls) -> list[tuple[str, int]]:
        return [(member.name, member.value) for member in cls]

    @classmethod
    def get_or_none(cls, value: object) -> Self | None:
        if isinstance(value, cls):
            return value

        if value is None:
            return None

        try:
            #? `value: object` requires narrowing before cls() will accept it.
            return cls(cast("int", value))
        except (ValueError, TypeError):
            pass

        if isinstance(value, str):
            try:
                return cls.from_fuzzy_int_string(value)
            except ValueError:
                pass

        return None

    @classmethod
    def choices(cls) -> list[Any]:
        return cls.values()


BaseIntEnum.DEFAULT_MAX_INPUT_LENGTH = 1024
