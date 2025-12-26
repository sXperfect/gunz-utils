# Task: Optimize Enum Attribute Access

## Description
Optimized `BaseStrEnum` and `BaseIntEnum` in `src/gunz_utils/enums.py` by replacing `getattr(cls, "attr")` with direct attribute access (`cls.attr`) for accessing `__ALIASES__` and lazily initialized lookup maps.

## Key Learnings
- **Performance:** Direct attribute access is faster than `getattr`, especially in hot paths like enum lookups. Benchmarks showed ~24% improvement for `__ALIASES__` access and ~8% for lazy map access.
- **Safety:** Direct access requires the attribute to exist or be handled via `try-except AttributeError`. For `__ALIASES__`, it is defined in the base class. For lazy maps, the `try-except` block correctly handles initialization.
- **Type Safety:** Using direct access for dynamically added attributes (lazy maps) can confuse static type checkers. Explicitly declaring them as `ClassVar` with type hints in the class body resolves this.

## Future Improvements
- Consider using `slots` or other optimizations if memory usage becomes a concern for large numbers of enum members.
