## 2024-05-22 - [Optimizing sanitize_filename]
**Learning:** Python 3.12+ automatically optimizes set literals containing constants (e.g., `{"CON", "PRN"}`) into stored `frozenset` constants. Manually extracting these to global variables (e.g., `_RESERVED = frozenset(...)`) is unnecessary and can be slightly slower due to `LOAD_GLOBAL` vs `LOAD_CONST`.
**Action:** When optimizing constant lookups, check bytecode first. Don't "optimize" constant literals into globals unless readability demands it or the set construction is dynamic.

## 2024-05-22 - [Split vs Partition]
**Learning:** `str.partition(sep)[0]` is significantly faster (~2x) than `str.split(sep)[0]` when you only need the first segment. `split` allocates a list of all segments, whereas `partition` returns a fixed 3-tuple and stops scanning after the first separator.
**Action:** Use `partition` instead of `split` when extracting prefixes or suffixes based on a delimiter.
