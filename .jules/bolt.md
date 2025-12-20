## 2024-05-22 - [Optimizing Enum Lookups]
**Learning:** Linear scans in `Enum` classes (e.g., iterating `for member in cls`) can be surprisingly slow (1ms/op for 1000 members). For frequent lookups, especially with fuzzy matching logic, always pre-compute a lookup map.
**Action:** When implementing fuzzy matching on Enums, cache a `normalized_key -> member` map lazily on the class to achieve O(1) performance.
