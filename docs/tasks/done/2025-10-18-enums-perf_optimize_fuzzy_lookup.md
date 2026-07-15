# Optimize Enum Fuzzy Lookup

## The Task
Optimize `BaseStrEnum` fuzzy matching performance by reducing unnecessary string normalizations for inputs that are already valid (e.g., matching the raw value).

## The Solution
Updated `_get_fuzzy_map` to include the raw lowercase value of the enum member in the lookup map.
This allows `from_fuzzy_string` to find a match immediately after lowercasing the input, skipping the subsequent `.replace()` calls and second lookup for inputs that match the raw value (even if they contain separators).

## Lessons Learned
- Adding keys to a lookup map (memory trade-off) can significantly reduce CPU overhead for "happy path" inputs.
- Profiling inputs with separators confirmed that `str.replace` calls, while fast, add up in tight loops or high-frequency paths.
- Optimizing the lookup map construction (one-time cost) is preferable to optimizing the lookup logic (runtime cost).

## Future Improvements
- Consider using a dedicated cache for frequently looked-up invalid strings if they become a bottleneck (to fail faster), though this risks DoS if not bounded.
