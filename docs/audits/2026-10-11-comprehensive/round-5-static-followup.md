# Round 5 — remote static follow-up (2026-10-11)

Branch: `fix/audit-bugs-20261011`. The initial remote phase was source inspection
without local execution. Subsequent local fetch, debugging and verification are
recorded below. Earlier Linux results do not automatically certify new repairs.

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

## Follow-up implementation (unverified locally)

- Commit `8d8b1054`: added lock-guarded generation tracking to synchronous TTL cache. Computations started before `cache_clear()` retain their own return value but cannot insert it into the new cache generation. Hit/miss counters retain the existing clear semantics.
- Commit `42509fa3`: added deterministic two-thread regression using events in `tests/test_core/test_cache.py`.
- Local execution and aggregate static gates **have not been run for these commits**. The prior 1710-pass result belongs to the preceding snapshot.
- Next local checks: `python -m pytest tests/test_core/test_cache.py -q`, `python -m ruff check .`, `python -m mypy src/gunz_utils`, then the repository's canonical local audit gate on Python 3.11/3.12.
- R5-002 through R5-004 remain explicit contract-review items, not newly fixed defects.


## Local fetch and debugging

Fetched `origin/fix/audit-bugs-20261011@d94adfec6b94f242d339bfdcc5d0914f511742da`
and fast-forwarded the clean isolated feature checkout from `2c04aa6`. Main
remains at `a375ed7`. Four remote commits added the synchronous invalidation
fix, its thread regression, and the original static handoff above.

An independent bounded before/after probe reads the trusted cache module from
`2c04aa6` into a scratch-only source file: after clear and a fresh value 2, the
old producer returns 1 and the old implementation incorrectly makes the next
caller receive 1. The fetched fix still returns 1 to its old caller while the
next caller receives 2. Evidence: `/tmp/gunz-utils-round5-before-after.json`.

Local gunz-style initially failed the new test's one-line `work(value)`
signature. It is corrected without changing test behavior. A required patch
fragment now records the user-visible synchronous invalidation fix.

| Item | Reviewed disposition |
|---|---|
| R5-001 | Fetched fix verified; repeated clears, old-producer failure, result identity and counter/capacity accounting are covered. |
| R5-002 | Independent concurrent misses are the synchronous cache contract. A two-worker barrier proves both compute outside the cache lock; no single-flight behavior was added. |
| R5-003 | No thread-safety promise exists. Public ResourceBudget documentation now states single ownership or external synchronization; counter code remains unchanged. |
| R5-004 | Deadline checks are cooperative, before entry and after success. Injected-clock proofs establish that a completed body can overrun and that its own exception propagates unchanged. |

Focused pytest on cache, shared foundation, numeric contracts, earlier process
proofs, and the five new round-five cases: **80 passed plus 65 subtests** on
Python 3.11 and Python 3.12. Local Ruff and mypy pass; private gunz-style has zero
violations and three advisory warnings in these four files. Full frozen-source
canonical verification passes all six gates as recorded below. No worker or thread leaks were observed
in these finite schedules; this is not a whole-package memory-leak certificate.


## Final local acceptance

```bash
PYTHONPATH=/tmp/gunz-utils-fix-audit-20261011-672bfb1/src \
PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 /tmp/gunz-utils-audit-20261008/bin/python \
  scripts/audit_ci.py \
  --compat-python /tmp/gunz-utils-audit-20261008-py312/bin/python \
  --summary-json /tmp/gunz-utils-round5-final-summary.json
```

All six gates return zero: release, lint, test, strict docs, isolated packaging,
and Python compatibility. Both interpreters have **1716 passed, 38 justified
skips** (3.11: 80.61s; 3.12: 79.01s). Each additional asserted compiled-native
leg has **91 passed**; each forced fallback has **60 passed, 31 native-only skips**.
The ordinary skips comprise native-only cases exercised separately plus seven
actual Windows/macOS cases still awaiting native hosts. Ruff and mypy pass;
local private gunz-style reports zero violations and 99 advisory warnings.
Minimal/extras imports, wheel/sdist installed origins and py.typed all pass.

No source/test/configuration/fragment input changed during verification. Input
SHA256 (304 files): `f7615473b8c32f494e89fc1f28ede57f138d1cf9c56f2a224d8d41c095a68f80`. Full log:
`/tmp/gunz-utils-round5-final-gates.log`. Before/after and final JSON evidence
remain under the documented /tmp paths. The source now documents each reviewed
contract; no single-flight or multi-threaded budget promise was introduced, and
no test was weakened. Main and hosted workflow configuration are unchanged.
