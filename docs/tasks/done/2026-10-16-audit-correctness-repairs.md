# Task: Audit Correctness Repairs (Rounds 10–12 Follow-up)

**Date:** 2026-10-16
**Role:** Programmer
**Component:** `gunz_utils.parsing`, `gunz_utils.leases`, `gunz_utils.dag`, `gunz_utils.provenance_graph`, `gunz_utils.rate_limit`, `gunz_utils.redaction`
**Status:** Done

## 1. Goal
Remediate audited correctness bugs and edge-case crash vulnerabilities identified in the codebase traversal and audit records (rounds 10–12 follow-up), ensuring bulletproof behavior under extreme inputs, deep graphs, concurrent lease renewals, and parameter validation.

## 2. Scope
### In Scope
1. **`parsing.safe_float`**:
   - Handled `OverflowError` (e.g. `10**10000` or strings with enormous exponents) gracefully by returning `default`.
   - Strictly rejected `bool` inputs (`safe_float(True)` -> `default`), aligning with `safe_int` semantics.
2. **`dag.WorkflowDAG` & `provenance_graph.ProvenanceGraph`**:
   - Refactored `_topological_order` and `effective_fingerprint` in `WorkflowDAG` to iterative stack algorithms.
   - Refactored `ancestors` and `_validate_acyclic` in `ProvenanceGraph` to iterative stack algorithms.
   - Verified that both handle 1500-stage deep graphs without hitting Python's `RecursionError`.
3. **`rate_limit.AsyncRateLimiter`**:
   - Hardened `acquire` and `available_tokens` and `_refill` against subnormal positive rates (e.g. `5e-324`) and arithmetic overflow to infinity.
   - Raises `TimeoutError` when timeout is specified and calculated wait exceeds budget or is infinite; raises `OverflowError` when wait is infinite with no timeout.
4. **`redaction.redact_dict`**:
   - Enforced `_validate_show_chars` up front on dict input to reject invalid non-integer/negative `show_chars` arguments even if dictionary entries do not trigger string secret masking.
5. **Platform Safety**:
   - Handled `setrlimit(RLIMIT_STACK, ...)` safely on macOS/Darwin where custom stack limits are clamped.
6. **Regression Tests**:
   - Added unit test regressions across `test_parsing.py`, `test_dag.py`, `test_provenance_graph.py`, `test_deadline_regressions.py`, and `test_redaction.py`.
7. **CI & Changelog**:
   - Passed Ruff, Mypy, full test suite (1774 passed, 0 failed), and native verification.
   - Added SemVer changelog fragment in `changes/correctness-audit-repairs.fixed.md`.

### Out of Scope / Contract Retained
- `leases.run_with_lease_heartbeat`: Existing concurrent scheduling contract and test suite assertions (which expect cancelled in-flight operations) are retained per ALG-022 A4 proof.

## 3. Verification
- [x] Ruff check: `ruff check src tests benchmarks scripts` (0 errors)
- [x] Mypy check: `mypy src/gunz_utils` (0 errors)
- [x] Full Pytest suite: `pytest` (1774 passed, 0 failed, 12 skipped)
- [x] Native & fallback verification: `python scripts/verify_native.py` (both passed)
- [x] Release metadata check: `python scripts/release.py check` (OK)
- [x] Changelog fragment added: `changes/correctness-audit-repairs.fixed.md`

## 4. Status
- **Started:** 2026-10-16
- **Completed:** 2026-10-16
