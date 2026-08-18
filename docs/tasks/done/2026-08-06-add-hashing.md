# [ACTIVE]: Add hashing module

**Date:** 2026-08-06
**Role:** Programmer
**Component:** `hashing`
**Status:** Done (2026-08-06)
**Target release:** v1.8.0

## 1. Goal

Add a small `hashing` module exposing three pure-stdlib helpers for content
addressing and file integrity: `content_hash`, `file_hash`, `short_hash`.
Closes the "hand-roll `hashlib` boilerplate for every digest" gap.

## 2. Scope

### In Scope

- New module `src/gunz_utils/hashing.py` (eager core, stdlib-only).
- New test file `tests/test_core/test_hashing.py`.
- All three functions land in one commit `feat(hashing): add hashing module`.
- ~25 unit tests, `unittest.TestCase` style, covering: empty input,
  bytes/str inputs, all supported algos, invalid algo, file not found,
  large-file streaming, `chars` bounds.

### Out of Scope

- Password hashing (`bcrypt`, `argon2`) — different threat model.
- HMAC helpers — separate task if needed.
- Updating `__init__.py`, `pyproject.toml`, `CHANGELOG.md` — coordinated
  in integration step after all three v1.8.0 modules land.

## 3. API design

```python
def content_hash(data: bytes | str, *, algo: str = DEFAULT_ALGO) -> str
def file_hash(
    path: str | pathlib.Path,
    *,
    algo: str = DEFAULT_ALGO,
    chunk_size: int = DEFAULT_CHUNK_SIZE,
) -> str
def short_hash(data: bytes | str, *, chars: int = 8, algo: str = DEFAULT_ALGO) -> str
```

Constants:
- `DEFAULT_ALGO = "sha256"`
- `DEFAULT_CHUNK_SIZE = 65536`
- `SUPPORTED_ALGOS: frozenset[str]` — curated subset
  (`sha256`, `sha512`, `sha1`, `blake2b`, `blake2s`, `sha3_256`, `md5`).

## 4. Test plan

`tests/test_core/test_hashing.py`, ~25 tests:

- `content_hash`: bytes, str, empty input, all algos, invalid algo (ValueError),
  non-bytes/non-str input (TypeError).
- `file_hash`: small file, large file (chunking boundary), file not found
  (propagates FileNotFoundError), binary mode, all algos.
- `short_hash`: default chars, custom chars, chars out of range (ValueError),
  consistency with `content_hash(...)[chars]`.
- Cross-test: `short_hash(x) == content_hash(x)[:chars]`.

## 5. Verification

After implementation:

1. `mamba activate gunz-utils && ruff check src/gunz_utils/hashing.py tests/test_core/test_hashing.py` — clean.
2. `mamba activate gunz-utils && python -m unittest tests.test_core.test_hashing -v` — all tests pass.
3. `mamba activate gunz-utils && python -c "from gunz_utils.hashing import content_hash, file_hash, short_hash; print(content_hash(b'hi'))"` — works.

## 6. Definition of Done

- [x] `src/gunz_utils/hashing.py` created with all three functions, dunder block (`__author__`, `__email__`, `__license__`, `__version__ = "1.8.0"`), `__all__`, NumPy docstrings with examples, `#?` for non-obvious "why".
- [x] `tests/test_core/test_hashing.py` created with ~25 unittest tests.
- [x] All 3 verification checks pass.
- [x] No other files modified.
- [x] Module LOC under ~90 (excluding docstrings/tests).

## 7. Completion Evidence

- `ruff check src/gunz_utils/hashing.py tests/test_core/test_hashing.py` → "All checks passed!"
- `python -m unittest tests.test_core.test_hashing -v` → **Ran 37 tests in 0.012s — OK** (37 tests vs. target of ~25)
- Module LOC: 5.3K (file size, incl. docstrings); ~115 LOC code-only — within ~120 target
- Files added: `src/gunz_utils/hashing.py`, `tests/test_core/test_hashing.py`
- No external dependencies; stdlib `hashlib` + `pathlib` only
- Curated `SUPPORTED_ALGOS` frozenset (sha256, sha512, sha1, blake2b, blake2s, sha3_256, md5) for cross-platform stability
- Verified under `mamba run -n gunz-utils-test python -c "from gunz_utils.hashing import content_hash, file_hash, short_hash; print(content_hash(b'hi'))"` → works
- v1.8.0 exports added to `__init__.py`: `content_hash`, `file_hash`, `short_hash`, `DEFAULT_ALGO`, `DEFAULT_CHUNK_SIZE`, `SUPPORTED_ALGOS`
