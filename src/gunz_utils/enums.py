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
__version__ = "1.0.0"

# =============================================================================
# STANDARD LIBRARY IMPORTS
# =============================================================================
import enum
from typing import Self, TypeVar, ClassVar, Any

# =============================================================================
# TYPE VARIABLES
# =============================================================================
T = TypeVar("T", bound="BaseStrEnum")

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
    
    #? Dictionary mapping lowercase aliases to actual enum values
    #? Using dunder name to avoid it being treated as an Enum member
    __ALIASES__: ClassVar[dict[str, str]] = {}

    @classmethod
    def _get_fuzzy_map(cls) -> dict[str, Self]:
        """
        Lazily builds and returns a mapping for fuzzy lookups.
        Key is the normalized string or lowercase name.
        Value is the enum member.
        """
        # Use a private attribute on the class itself to store the map
        # We use getattr/setattr to avoid static type checker issues with
        # dynamically added attributes on Enum classes.
        try:
            return getattr(cls, "_fuzzy_lookup_map")
        except AttributeError:
            lookup_map = {}
            for member in cls:
                # Add normalized value
                val_norm = member.value.lower().replace("-", "_").replace(" ", "_")
                if val_norm not in lookup_map:
                    lookup_map[val_norm] = member

                # Add lowercase name
                name_lower = member.name.lower()
                if name_lower not in lookup_map:
                    lookup_map[name_lower] = member

            setattr(cls, "_fuzzy_lookup_map", lookup_map)
            return lookup_map

    @classmethod
    def from_fuzzy_string(cls, value_str: str) -> Self:
        """
        Attempts to find a member by alias, normalized value, or case-insensitive name.
        Raises ValueError if no match is found.
        """
        value_lower = value_str.lower()
        _aliases = getattr(cls, "__ALIASES__", {})

        # 1. Check for defined aliases (string -> target_string_value)
        if value_lower in _aliases:
            alias_target_value = _aliases[value_lower]
            
            # Check internal map first
            if alias_target_value in cls._value2member_map_:
                return cls._value2member_map_[alias_target_value]

            # Fallback to instantiation (should work if valid member)
            try:
                return cls(alias_target_value)
            except ValueError:
                raise ValueError(f"Alias target '{alias_target_value}' is not a valid member value for {cls.__name__}")

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
            return cls(value)
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


@enum.verify(enum.UNIQUE)
class OptionalBaseStrEnum(BaseStrEnum):
    """
    A base class for StrEnum that treats None as the NONE enum member.
    """
    
    __ALIASES__: ClassVar[dict[str, str]] = {}

    def __init_subclass__(cls, **kwargs) -> None:
        super().__init_subclass__(**kwargs)
        if "NONE" not in cls.__members__:
            raise TypeError(
                f"Class {cls.__name__} must define a NONE member when inheriting "
                f"from {OptionalBaseStrEnum.__name__}. Example: NONE = 'none'"
            )

    @classmethod
    def _missing_(cls, value: object) -> Self:
        if value is None:
            return cls.NONE
        
        # Try fuzzy match via helper, but do NOT retry cls(value) to avoid recursion
        if isinstance(value, str):
            try:
                return cls.from_fuzzy_string(value)
            except ValueError:
                pass # let super raise
        
        return super()._missing_(value)


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

    @classmethod
    def _get_name_lookup_map(cls) -> dict[str, Self]:
        """
        Lazily builds and returns a mapping from lowercase name to enum member.
        """
        try:
            return getattr(cls, "_name_lookup_map")
        except AttributeError:
            lookup_map = {}
            for member in cls:
                name_lower = member.name.lower()
                if name_lower not in lookup_map:
                    lookup_map[name_lower] = member
            setattr(cls, "_name_lookup_map", lookup_map)
            return lookup_map

    @classmethod
    def from_fuzzy_int_string(cls, value_str: str) -> Self:
        """
        Attempts to find a member by alias (string->int), case-insensitive name, or
        string-to-int conversion.
        """
        value_lower = value_str.lower()
        _aliases = getattr(cls, "__ALIASES__", {})

        # 1. Check for aliases (string -> int_value)
        if value_lower in _aliases:
            int_target_value = _aliases[value_lower]
            
            if int_target_value in cls._value2member_map_:
                return cls._value2member_map_[int_target_value]

            try:
                return cls(int_target_value)
            except ValueError:
                raise ValueError(f"Alias target '{int_target_value}' is not a valid member value for {cls.__name__}")

        # 2. Check for member name matches (case-insensitive)
        # Optimization: Use cached lookup map instead of iterating
        name_map = cls._get_name_lookup_map()
        if value_lower in name_map:
            return name_map[value_lower]

        # 3. Try to convert to int if it's a string representation of a number
        try:
            int_value = int(value_str)
            if int_value in cls._value2member_map_:
                return cls._value2member_map_[int_value]
            return cls(int_value)
        except (ValueError, TypeError):
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
            return cls(value)
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
