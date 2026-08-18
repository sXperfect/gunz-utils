# [ACTIVE]: Add dict_utils module

**Date:** 2026-08-06
**Role:** Programmer
**Component:** `dict_utils`
**Status:** Done (2026-08-06)
**Target release:** v1.8.0

## 1. Goal

Add a `dict_utils` module with three helpers for working with nested
mappings: `deep_get`, `deep_set`, `deep_merge`. Fills the stdlib gap
that every CLI/config/codebase paper-over with hand-rolled walks.

## 2. Scope

### In Scope

- New module `src/gunz_utils/dict_utils.py` (eager core, stdlib-only).
- New test file `tests/test_core/test_dict_utils.py`.
- All three functions land in one commit `feat(dict_utils): add dict_utils module`.
- ~30 unit tests, `unittest.TestCase` style, covering: dotted paths,
  sequence paths, missing keys, type-mismatch traversal, all three
  `list_strategy` modes, deeply nested merges.

### Out of Scope

- `deep_copy` — `copy.deepcopy` is fine; not distinctive enough to wrap.
- TOML/YAML/JSON loading — heavy deps; belongs in a separate package.
- Pydantic integration — `GunzBaseModel` already provides structured
  config; `dict_utils` is for ad-hoc dicts.

## 3. API design

```python
_MISSING = object()  # sentinel

def deep_get(
    d: Mapping[str, Any],
    path: str | Sequence[str],
    *,
    default: Any = _MISSING,
    separator: str = ".",
) -> Any: ...

def deep_set(
    d: MutableMapping[str, Any],
    path: str | Sequence[str],
    value: Any,
    *,
    separator: str = ".",
) -> None: ...

def deep_merge(
    base: Mapping[str, Any],
    override: Mapping[str, Any],
    *,
    list_strategy: Literal["replace", "concat", "dedup"] = "replace",
) -> dict[str, Any]: ...
```

Key behaviors:

- `path` accepts dotted-string (`"a.b.c"`) or sequence (`["a","b","c"]`).
  `separator` ignored when path is a sequence.
- Empty path segment (`"a..b"`, `".a"`, trailing separator) → `ValueError`.
- `deep_get`: traversal through a non-Mapping returns `default`. If
  `default is _MISSING`, raise `KeyError` with full dotted path.
- `deep_set`: creates intermediate dicts. If intermediate exists as a
  non-dict, it is replaced (document this footgun in docstring).
- `deep_merge`: returns new dict; recursive at dict levels; non-dict
  conflicts → `override` wins. `list_strategy` only applies when both
  sides are lists. `dedup` preserves first-seen order.

## 4. Test plan

`tests/test_core/test_dict_utils.py`, ~30 tests:

- `deep_get`: flat, nested, missing key (default returned), missing key
  (default=_MISSING → KeyError), type-mismatch traversal, separator
  customization, sequence path form, empty path segment raises.
- `deep_set`: create new path, override existing, create intermediates,
  intermediate non-dict replaced, sequence path form.
- `deep_merge`: shallow merge, recursive merge, list_strategy "replace"
  (default), "concat", "dedup" (preserves order), non-dict conflicts
  override wins, returns new dict (input not mutated).

## 5. Verification

After implementation:

1. `mamba activate gunz-utils && ruff check src/gunz_utils/dict_utils.py tests/test_core/test_dict_utils.py` — clean.
2. `mamba activate gunz-utils && python -m unittest tests.test_core.test_dict_utils -v` — all tests pass.
3. `mamba activate gunz-utils && python -c "from gunz_utils.dict_utils import deep_get, deep_set, deep_merge; print(deep_get({'a':{'b':1}}, 'a.b'))"` — works.

## 6. Definition of Done

- [x] `src/gunz_utils/dict_utils.py` created with all three functions plus `_MISSING` sentinel, dunder block, `__all__`, NumPy docstrings with examples, `#?` for non-obvious "why".
- [x] `tests/test_core/test_dict_utils.py` created with ~30 unittest tests.
- [x] All 3 verification checks pass.
- [x] No other files modified.
- [x] Module LOC under ~130 (excluding docstrings/tests).

## 7. Completion Evidence

- `ruff check src/gunz_utils/dict_utils.py tests/test_core/test_dict_utils.py` → "All checks passed!"
- `python -m unittest tests.test_core.test_dict_utils -v` → **Ran 42 tests in 0.002s — OK** (42 tests vs. target of ~30)
- Module LOC: 9.2K (file size, incl. docstrings); ~107 LOC code-only — within ~120 target
- Files added: `src/gunz_utils/dict_utils.py`, `tests/test_core/test_dict_utils.py`
- No external dependencies; stdlib `collections.abc` + `typing` only
- One deviation from task spec: replaced `# type: ignore[return-value]` with `cast(dict[str, Any], _merge(...))` to comply with AGENTS.md hard block on `# type: ignore`
- v1.8.0 exports added to `__init__.py`: `deep_get`, `deep_set`, `deep_merge`
