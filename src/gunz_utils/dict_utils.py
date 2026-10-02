"""Helpers for working with nested mappings (dotted-path access, recursive merge)."""

from __future__ import annotations

import copy
from collections.abc import Mapping, MutableMapping, Sequence
from typing import Any, Literal, cast

from ._version import __version__ as __version__

__author__ = "Yeremia Gunawan Adhisantoso"
__email__ = "yeremiag@gmail.com"
__license__ = "Clear BSD"
__all__ = ["deep_get", "deep_set", "deep_merge"]

#? Singleton sentinel used to detect "no default supplied" distinctly from
#? "default value is None". A plain object() works because identity comparison
#? (`is _MISSING`) cannot collide with any user-supplied default.
_MISSING: Any = object()


def _normalize_path(
    path: str | Sequence[str],
    separator: str,
) -> tuple[str, ...]:
    """Convert a path (string or sequence) into a tuple of key segments.

    Empty segments raise ``ValueError`` so paths like ``"a..b"`` or ``".a"`` are
    rejected loudly rather than silently treated as a key containing a dot.
    """
    if isinstance(path, str):
        parts = path.split(separator)
    else:
        parts = list(path)
        if separator != ".":
            #? When the user supplies a custom separator alongside a sequence
            #? path, the separator is meaningless; warn by raising rather
            #? than silently ignoring it.
            raise ValueError(
                "separator is only honored when path is a string; "
                "got sequence path with separator != '.'"
            )
    if any(p == "" for p in parts):
        raise ValueError(f"path contains an empty segment: {path!r}")
    if not parts:
        raise ValueError("path must contain at least one segment")
    return tuple(parts)


def deep_get(
    d: Mapping[str, Any],
    path: str | Sequence[str],
    *,
    default: Any = _MISSING,
    separator: str = ".",
) -> Any:
    """Retrieve a value from a nested mapping using a dotted-path key.

    Returns ``default`` when any key in the path is missing OR when traversal
    encounters a non-Mapping intermediate. If ``default`` is not provided,
    :class:`KeyError` is raised with the full dotted path so callers can
    distinguish a missing key from a None-valued one.

    Parameters
    ----------
    d : Mapping[str, Any]
        Source mapping (not mutated).
    path : str | Sequence[str]
        Path to the value. A string like ``"a.b.c"`` is split on
        ``separator``; alternatively a sequence like ``["a", "b", "c"]``.
    default : Any, optional
        Returned when the key is missing or traversal fails. If omitted
        (default), missing keys raise ``KeyError``.
    separator : str, optional
        Separator used to split string paths. Default is ``"."``. Ignored
        when ``path`` is a sequence (a non-``"."`` separator alongside a
        sequence path raises ``ValueError``).

    Returns
    -------
    Any
        The value at ``path``, or ``default``.

    Raises
    ------
    ValueError
        If ``path`` is empty or contains empty segments, or if a custom
        ``separator`` is supplied with a sequence ``path``.
    KeyError
        If ``path`` does not exist and ``default`` was not provided.

    Examples
    --------
    >>> deep_get({"a": {"b": 1}}, "a.b")
    1
    >>> deep_get({"a": {"b": 1}}, ["a", "b"])
    1
    >>> deep_get({"a": {"b": 1}}, "a.c", default=None) is None
    True
    >>> deep_get({"a": 1}, "a.b")  # traversal through scalar returns default
    """
    parts = _normalize_path(path, separator)
    dotted = separator.join(parts)
    cursor: Any = d
    for key in parts:
        if not isinstance(cursor, Mapping):
            #? A list, int, or str in the middle of a path means the user
            #? asked for something that doesn't structurally exist. Treat it
            #? as "not found" rather than raising TypeError so callers can
            #? probe config trees safely.
            if default is _MISSING:
                raise KeyError(dotted)
            return default
        try:
            cursor = cursor[key]
        except (KeyError, IndexError, TypeError):
            if default is _MISSING:
                raise KeyError(dotted) from None
            return default
    return cursor


def deep_set(
    d: MutableMapping[str, Any],
    path: str | Sequence[str],
    value: Any,
    *,
    separator: str = ".",
) -> None:
    """Set a value in a nested mapping, creating intermediate dicts as needed.

    Intermediate mappings are created if they do not exist. If an
    intermediate exists but is not a Mapping, it is REPLACED with a new
    empty dict (silently losing the previous value) — this is a deliberate
    footgun-reduction: callers who need different semantics should normalize
    their data first.

    The input ``d`` is mutated in place; nothing is returned.

    Parameters
    ----------
    d : MutableMapping[str, Any]
        Target mapping (mutated in place).
    path : str | Sequence[str]
        Path where the value will be stored.
    value : Any
        Value to set.
    separator : str, optional
        Separator for string paths. Default is ``"."``. Same sequence-path
        rules as :func:`deep_get`.

    Returns
    -------
    None
        Mutates ``d`` in place.

    Raises
    ------
    ValueError
        If ``path`` is empty or contains empty segments.

    Examples
    --------
    >>> target: dict = {}
    >>> deep_set(target, "a.b.c", 42)
    >>> target
    {'a': {'b': {'c': 42}}}
    """
    parts = _normalize_path(path, separator)
    cursor: MutableMapping[str, Any] = d
    for key in parts[:-1]:
        next_node = cursor.get(key)
        if not isinstance(next_node, MutableMapping):
            #? Replacing a non-dict intermediate with a fresh dict is the
            #? conventional behavior for nested-set helpers (e.g. Lodash's
            #? _.set). Callers needing strict semantics should check first.
            new_node: MutableMapping[str, Any] = {}
            cursor[key] = new_node
            cursor = new_node
        else:
            cursor = next_node
    cursor[parts[-1]] = value


def deep_merge(
    base: Mapping[str, Any],
    override: Mapping[str, Any],
    *,
    list_strategy: Literal["replace", "concat", "dedup"] = "replace",
) -> dict[str, Any]:
    """Recursively merge two mappings, returning a new dict (no mutation).

    Behavior by case:

    - Both values are dicts → recurse, merging their keys.
    - Both values are lists → apply ``list_strategy``.
    - Otherwise → ``override`` wins.

    Parameters
    ----------
    base : Mapping[str, Any]
        Base mapping (not mutated).
    override : Mapping[str, Any]
        Override mapping (not mutated).
    list_strategy : {"replace", "concat", "dedup"}, optional
        How to combine list values:

        - ``"replace"`` (default): the override list fully replaces the base.
        - ``"concat"``: ``override`` is appended to ``base``
          (order: base then override).
        - ``"dedup"``: like ``"concat"`` but with duplicates removed
          (first occurrence wins).

    Returns
    -------
    dict[str, Any]
        A new dict containing the merged result. Inputs are never mutated.

    Raises
    ------
    ValueError
        If ``list_strategy`` is not one of the allowed values.

    Examples
    --------
    >>> deep_merge({"a": 1}, {"b": 2})
    {'a': 1, 'b': 2}
    >>> deep_merge({"a": {"b": 1}}, {"a": {"c": 2}})["a"]
    {'b': 1, 'c': 2}
    >>> deep_merge({"xs": [1, 2]}, {"xs": [3]}, list_strategy="concat")
    {'xs': [1, 2, 3]}
    >>> deep_merge({"xs": [1, 2, 3]}, {"xs": [2, 4]}, list_strategy="dedup")
    {'xs': [1, 2, 3, 4]}
    """
    if list_strategy not in ("replace", "concat", "dedup"):
        raise ValueError(
            f"list_strategy must be one of 'replace', 'concat', 'dedup'; "
            f"got {list_strategy!r}"
        )

    memo: dict[int, Any] = {}

    def _isolate(val: Any) -> Any:
        val_id = id(val)
        if val_id in memo:
            return memo[val_id]

        if isinstance(val, Mapping):
            res_dict: dict[Any, Any] = {}
            memo[val_id] = res_dict
            for k, v in val.items():
                res_dict[k] = _isolate(v)
            return res_dict
        if isinstance(val, list):
            res_list: list[Any] = []
            memo[val_id] = res_list
            for v in val:
                res_list.append(_isolate(v))
            return res_list
        if isinstance(val, set):
            res_set: set[Any] = set()
            memo[val_id] = res_set
            for v in val:
                res_set.add(_isolate(v))
            return res_set
        if isinstance(val, tuple):
            res_tuple = tuple(_isolate(v) for v in val)
            memo[val_id] = res_tuple
            return res_tuple
        try:
            copied = copy.deepcopy(val, memo)
            memo[val_id] = copied
            return copied
        except Exception:
            memo[val_id] = val
            return val

    def _merge(a: Any, b: Any) -> Any:
        if isinstance(a, Mapping) and isinstance(b, Mapping):
            #? Build a new dict so neither input is mutated; recurse on each key.
            out: dict[str, Any] = {}
            for key in a:
                out[key] = _merge(a[key], b[key]) if key in b else _isolate(a[key])
            for key in b:
                if key not in a:
                    out[key] = _isolate(b[key])
            return out
        if isinstance(a, list) and isinstance(b, list):
            if list_strategy == "replace":
                return _isolate(b)
            if list_strategy == "concat":
                return _isolate(a) + _isolate(b)
            #? dedup: first occurrence wins, order = base then override.
            #? Unhashable items (e.g. dicts) fall through without being
            #? tracked; that mirrors common stdlib semantics and avoids
            #? forcing the caller to pre-normalize their data.
            seen_hashable: set[Any] = set()
            seen_unhashable: list[Any] = []
            result: list[Any] = []
            for item in (*a, *b):
                try:
                    if item in seen_hashable:
                        continue
                    seen_hashable.add(item)
                except TypeError:
                    if any(item == previous for previous in seen_unhashable):
                        continue
                    seen_unhashable.append(item)
                result.append(_isolate(item))
            return result
        #? Non-dict / non-list: override wins. Plain scalars and mixed
        #? type pairs all fall through here.
        return _isolate(b)

    return cast(dict[str, Any], _merge(base, override))
