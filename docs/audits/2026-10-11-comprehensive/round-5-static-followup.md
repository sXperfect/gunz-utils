# Round 5 — remote static follow-up (2026-10-11)

Branch: `fix/audit-bugs-20261011`. Source inspection only: **no local execution** and no source modifications in this round. Previous Linux verification covers the earlier snapshot, not automatically any new repairs.

## New finding R5-001 — synchronous TTL cache can resurrect an invalidated value (medium)

File: `src/gunz_utils/cache.py`, `_TTLCache.__call__` and `cache_clear`.

Observation: `__call__` checks misses under `_lock`, releases the lock to run `func(*args, **kwargs)`, then acquires the lock and always stores the computed result. `cache_clear` clears entries and counters under the same lock, but does not invalidate a running computation. If a call is between its initial miss and its final store when another thread calls `cache_clear()`, the old call inserts an obsolete value after clearing. This mirrors the previously fixed async-cache generation defect.

Reproduction proposal (local): use threading Events to block a producer following a cache miss; call `cache_clear()` while it is paused, then update backing state and release it. Assert subsequent calls do not receive the invalidated result. Check API/documentation to decide whether an old caller may still receive its own result.

Proposed fix: add a generation counter guarded by `_lock`; capture generation on miss, insert only when unchanged, and keep current caller return semantics. Test simultaneous calls and LRU accounting; do not hold the lock while executing arbitrary user functions.

## R5-002 — synchronous cache misses are not single-flight (design review)

Same module. Parallel callers for the same uncached key can run the underlying function independently. This may be intentional for a synchronous TTL cache and is **not classified as a bug** without a single-flight contract. Verify docs and benchmark intended contention behavior before changing it.

## R5-003 — resource budget is not synchronized (documented-contract check)

File: `src/gunz_utils/limits.py`, `ResourceBudget.consume_bytes/consume_items/consume_steps`. Read/modify/write counters are unguarded. If a single `ResourceBudget` is shared across threads, concurrent consumers may exceed the requested limit. Determine whether thread safety is promised; if not, document single-owner usage. If promised, guard consumption atomically and reproduce with multiple concurrent threads. **Potential issue, not established misuse of the API.**

## R5-004 — time-budget expiration does not interrupt body execution (contract check)

`ResourceBudget.step()` checks deadline before and after a body, but is cooperative rather than preemptive. A blocked body can exceed the configured deadline until it returns. This is not necessarily a defect; document cooperative semantics and test exception propagation when the body itself raises.

## Suggested local-agent priority
1. Reproduce and fix R5-001 using deterministic thread barriers.
2. Confirm R5-002/R5-003/R5-004 contracts; only change behavior if an actual guarantee is violated.
3. Run focused cache/limits regressions on Python 3.11 and 3.12 and the aggregate local-only gates.
4. Preserve no-hosted-CI/no-main-merge policy and append actual logs, commit and results to `local-verification.md`.
