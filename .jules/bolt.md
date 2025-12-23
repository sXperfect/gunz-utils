## 2024-05-22 - [Optimizing sanitize_filename]
**Learning:** Python 3.12+ automatically optimizes set literals containing constants (e.g., `{"CON", "PRN"}`) into stored `frozenset` constants. Manually extracting these to global variables (e.g., `_RESERVED = frozenset(...)`) is unnecessary and can be slightly slower due to `LOAD_GLOBAL` vs `LOAD_CONST`.
**Action:** When optimizing constant lookups, check bytecode first. Don't "optimize" constant literals into globals unless readability demands it or the set construction is dynamic.

## 2024-05-22 - [Split vs Partition]
**Learning:** `str.partition(sep)[0]` is significantly faster (~2x) than `str.split(sep)[0]` when you only need the first segment. `split` allocates a list of all segments, whereas `partition` returns a fixed 3-tuple and stops scanning after the first separator.
**Action:** Use `partition` instead of `split` when extracting prefixes or suffixes based on a delimiter.

## 2024-05-23 - [Hasattr vs Try-Except]
**Learning:** For accessing attributes that are expected to exist (lazy-loaded caches on hot paths), using `try: return obj.attr except AttributeError:` is significantly faster (~30-60%) than `if hasattr(obj, "attr"): return getattr(obj, "attr")`. The `hasattr` approach involves two lookups (one check, one get) and overhead, whereas `try-except` optimizes for the common "hit" case.
**Action:** Use EAFP (try-except) for lazy-loaded caches where the cache hit rate is high.

## 2024-05-23 - [Regex Search vs Sub]
**Learning:** Guarding `re.sub` with `re.search` (`if search: sub`) improves performance for strings that *don't* match, but significantly degrades performance (almost 2x slower) for strings that *do* match because it forces two scans. Since `re.sub` is already optimized, the "optimization" is risky unless you are certain 99% of inputs are clean.
**Action:** Avoid guarding `re.sub` with `re.search` unless profiling proves the specific data distribution warrants it.

## 2024-05-23 - [Translate vs Replace]
**Learning:** For small numbers of replacements (e.g., 2) on short strings, chained `str.replace().replace()` is faster than `str.translate()`. `translate` has a higher setup cost.
**Action:** Don't blindly replace `replace` chains with `translate` without benchmarking.
