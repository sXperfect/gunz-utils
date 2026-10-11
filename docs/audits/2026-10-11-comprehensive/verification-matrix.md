# Offline verification matrix

| ID | Test / experiment | Acceptance |
|---|---|---|
| BUG-001 | User function raises after side effects; worker process fails after partial completion; iterator yields one item then fails | No automatic replay or duplicated output |
| BUG-002 | Block old producer, clear cache, perform new request, unblock old producer | Old producer does not repopulate cache; existing awaiters have defined outcome |
| BUG-003 | APP_DB and APP_DB__HOST in both insertion orders | Explicit ValueError, not TypeError/AttributeError |
| BUG-004 | bool, float, negative, 2**64, boundaries; accelerated and pure Python modes | Same defined failures and round-trips |
| BUG-005 | Invalid workers/chunksize on empty list and generator | Validation always occurs |
| BUG-006 | Huge generator, early break/close, exception during iteration, slow worker, chunksize and threshold extremes | Ordered output, bounded memory, no task replay; document close latency |
| BUG-007 | Sequential and concurrently running event loops in distinct threads; in-flight calls and cache_clear | Defined no deadlock/cross-loop Future failures; choose explicitly single-loop support if needed |
| BUG-008 | Symlink, race between listing and opening, missing file, rejected secure-open | No incomplete success manifest; symlink exclusion retained |
| AUD-009 | set/frozenset of nested values, distinct values with same repr, native fallback parity | Same canonical serialized output for semantically equivalent values |
| AUD-010 | custom mutable object whose __deepcopy__ raises; deep_merge and mutate output | Isolation contract either upheld or explicitly narrowed |
| AUD-011 | close iterator after first result while remaining workers are slow | Shutdown policy intentional, documented and tested |
| AUD-012 | threshold/chunksize large, infinite generator, memory profiling | Bounded behavior or documented/user-configurable cap |
| AUD-013 | rsync interrupted before marker, concurrent readers, concurrent writers, locked/unlocked mode | Markers never signal incomplete transfer |
| AUD-014 | Python 3.11/3.12 and supported native OSes; install minimal/extras and wheel/sdist | Import and feature parity; reproducible packaging |

## Initial local commands
```bash
git status --short
git rev-parse HEAD
python -m pytest tests/test_core/test_audit_regressions_20261011.py -q
python -m pytest tests/test_core/test_concurrency.py tests/test_core/test_cache.py tests/test_core/test_hashing_structured.py -q
python -m pytest -q
python -m ruff check .
python -m mypy src/gunz_utils
```

Check repository-specific `scripts/ci.py` gate options and run the canonical local gates as defined there. Native build/parity and OS-specific checks should be performed on supported local runners. Do not assume commands succeeded without logs.
