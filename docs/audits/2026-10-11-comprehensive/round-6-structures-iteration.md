# Round 6 — structures, iteration, env and retry static audit

Scope: `fix/audit-bugs-20261011@2cc858033c61863f7ead5d1de477669412f3b160`.
This audit does not invalidate the locally recorded Round 5 verification, which reports 1716 passing tests per Python interpreter. No commands were executed locally for Round 6.

## R6-001: deep_diff unbounded recursive depth (medium; source-grounded, runtime reproduction required)

`src/gunz_utils/structures.py:deep_diff` recursively calls `walk` for nested mapping and sequence children. The visited-ID-pair set detects cycles, but each new acyclic nested level consumes Python call stack. There is no `max_depth` or `ResourceBudget` check. Deeply nested external metadata may raise `RecursionError` instead of producing a structured difference.

**Reproduce:** create two 1500-level nested lists with distinct leaf values, run `deep_diff(left,right)`, and record whether a RecursionError escapes. Test a cycle separately to ensure any repair retains safe termination. Evaluate iterative traversal with explicit stack or enforce a documented maximum depth and explicit exception, and test deterministic output order.

## R6-002: freeze_structure unbounded recursive depth (medium; source-grounded, runtime reproduction required)

`structures.freeze_structure` detects active-container cycles but recursively freezes deeply nested acyclic mappings/lists. It likewise has no depth budget; at sufficient depth a `RecursionError` can escape. Create a 1500-level nested list and test failure type, then compare desired contract: explicit depth limit vs iterative conversion. Include a cycle and shared-subtree reference test.

## R6-003: flatten configurable container types change string handling (low; contract review)

`iteration.flatten(types=...)` allows caller-specified container types. If `str` is included, one-character strings are iterable and produce themselves forever under naive recursion until `max_nesting` rejects. This is bounded but surprising. Test `types=(list,tuple,str)` and document an explicit exclusion or guard for length-one self-similar containers. Do not alter defaults.

## R6-004: deep_diff structural equality for cyclic/aliased graphs (low; semantic contract review)

The visited pair short-circuit avoids cycles but does not assert equal alias topology. Compare `left=[shared, shared]` against separately allocated equal values; and different cyclic topology. Decide whether the function compares values only (current apparent intent) or reference graph structure. Do not classify as a bug unless graph topology is in scope.

## Audit disposition and next steps
- R5 review was completed by local agents; do not reopen without fresh evidence.
- R6-001/002: prioritize finite deterministic local reproduction and depth-limit policy.
- R6-003/004: resolve intended semantics before implementing anything.
- Inspect related use sites for untrusted nested data, then benchmark any iterative replacement against ordinary nesting.
- Record Python 3.11/3.12 outputs and rerun local-only pytest, Ruff, mypy, native checks and complete audit gate if implementation changes are made.
- Keep main, hosted CI and release untouched until explicit authorization.
