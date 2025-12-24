## 2025-12-24 - [Avoid Unnecessary Normalization]
**Learning:** In fuzzy matching logic where normalization (e.g., `replace()` calls) is used as a fallback, checking the raw input against the lookup map *first* can yield significant performance gains (~13-20%) for inputs that are already clean or match direct names, as it avoids the overhead of string allocation and scanning.
**Action:** When implementing "fuzzy" or "fallback" logic, always prioritize the "happy path" (direct match) before performing expensive transformations.
