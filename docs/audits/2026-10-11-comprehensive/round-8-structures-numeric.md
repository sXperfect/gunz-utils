# Round 8 — numerical, formatting and structures (remote source audit)

## R8-001 — bootstrap estimates are O(samples × observations) (resource policy)
`stats.bootstrap_mean_ci` builds and sorts all bootstrap results and samples each observation for every resample. This is algorithmically expected; caller-configured samples/number of observations remain unbounded. Benchmark large inputs; only add resource limits if library policy requires them. Not a confirmed bug.

## R8-002 — formatting of fractional byte counts truncates (low, contract)
`formatting.format_bytes` returns `int(n)` for values smaller than a base, discarding fractional bytes by design despite float input. Confirm required rounding/truncation, especially `0.9` or negative fractional values. Do not change without contract decision.

## R8-003 — deep_diff duplicate semantic mapping keys and repr ordering (low, verify)
`structures.deep_diff` traverses sorted union of mapping keys ordered by `repr`. Custom keys can have nonunique or nondeterministic representations. Test deterministic difference ordering for supported mapping key types; classify contract scope before changing.

## R8-004 — freeze_structure copying keys can change key equality/hash (medium, contract-dependent)
`structures.freeze_structure` deep-copies mapping keys and builds new dictionary. A custom hashable key whose equality/hash identity semantics depend on object identity may not be retrievable using the original key after freeze. Reproduce with identity-based keys; decide supported key types before repair.

Carry R6-001/002 deep nesting to offline reproduction. No source modification.
