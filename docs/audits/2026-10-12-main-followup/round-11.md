# Round 11 — DAG, parsing and security boundary review

Base: main@af4bcbfef7f57629511b26513084caed5803bb52. Static review only. No local test claims.

## R11-001 — safe_float does not safely handle numeric overflow (medium; source-confirmed)
`src/gunz_utils/parsing.py:safe_float` catches `ValueError` and `TypeError` around `float(_stripped(value))` but not `OverflowError`. A huge Python integer can raise `OverflowError: int too large to convert to float` rather than returning the caller's `default`, contrary to its safe/nonthrowing contract. Reproduce with `safe_float(10**10000, default=7.0)`. Fix by catching OverflowError, then add numeric-class and very large string boundary tests. Float NaN/Inf policy must stay unchanged.

## R11-002 — recursive DAG construction and fingerprinting have no depth budget (medium; source-grounded)
`src/gunz_utils/dag.py:WorkflowDAG._topological_order.visit` and `effective_fingerprint.resolve` recursively walk dependency chains. A valid chain of more than ~1000 stages may raise Python `RecursionError`; cycle detection does not protect deep acyclic graphs. Reproduce with 1500 stage nodes and separately a cycle; expected behavior should support valid long chains via iterative traversal or an explicit bounded API contract. Ensure deterministic dependency order and fingerprint stability for shallow inputs.

## R11-003 — lease preflight remains open from Round 10 (not duplicated)
Do not treat this as closed until a local event-synchronized reproduction verifies whether `renew_immediately=True` gates operation startup. See `round-10.md`.

## R11-004 — path security policy on non-POSIX requires supported-host verification (contract)
`security.open_path_under_base` falls back to opening a resolved path directly when POSIX `O_NOFOLLOW` is unavailable. This is not race-safe against concurrent parent-directory replacement. The module documents descriptor-relative protection only on POSIX. Do not claim a new confirmed vulnerability absent a supported threat model; ensure non-POSIX callers do not assume equivalent malicious-race protection.

## Handoff priority
1. Reproduce R11-001 and patch narrowly with parameterized tests.
2. Reproduce R11-002 and evaluate an iterative implementation (including stable topological ordering).
3. Verify Round 10 R10-001 in same local batch.
4. Record exact snapshot/commands, run Python 3.11/3.12 local canonical gates, avoid hosted CI.
