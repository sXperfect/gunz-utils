"""Helpers for working with nested mappings (dotted-path access, recursive merge)."""
from __future__ import annotations

__author__ = "Yeremia Gunawan Adhisantoso"
__email__ = "yeremiag@gmail.com"
__license__ = "Clear BSD"

# =============================================================================
# STANDARD LIBRARY IMPORTS
# =============================================================================
import copy
from collections.abc import Mapping, MutableMapping, Sequence
from typing import Any, Literal, cast

# =============================================================================
# THIRD-PARTY IMPORTS
# =============================================================================
# isort: split
# =============================================================================
# LOCAL APPLICATION IMPORTS
# =============================================================================
from ._version import __version__ as __version__
from .sentinels import UNSET

__all__ = ["deep_get", "deep_set", "deep_merge", "deep_pop"]

#? Sentinel used to tag boolean values in keys so True/False do not collide
#? with 1/0 during grouping and unique-hashing.
_BOOL_SENTINEL: Any = object()


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
    default: Any = UNSET,
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
            if default is UNSET:
                raise KeyError(dotted)
            return default
        try:
            cursor = cursor[key]
        except (KeyError, IndexError, TypeError):
            if default is UNSET:
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


def deep_pop(
    d: MutableMapping[str, Any],
    path: str | Sequence[str],
    default: Any = UNSET,
    *,
    separator: str = ".",
) -> Any:
    """Pop and return a value from a nested mapping using a dotted-path key.

    Removes the final key in the path from the innermost mapping. Intermediate
    mappings are preserved. If any intermediate key or the final key is missing,
    returns ``default`` (or raises ``KeyError`` if ``default`` was not provided).

    Parameters
    ----------
    d : MutableMapping[str, Any]
        Target mapping (mutated in place).
    path : str | Sequence[str]
        Path to the value to remove.
    default : Any, optional
        Fallback returned if the path does not exist. Raises KeyError if omitted.
    separator : str, default="."
        Separator for string paths.

    Returns
    -------
    Any
        The removed value, or default if missing.

    Raises
    ------
    KeyError
        If path is not found and default is not provided.
    TypeError
        If d is not a MutableMapping.
    """
    if not isinstance(d, MutableMapping):
        raise TypeError(f"expected MutableMapping, got {type(d).__name__}")
    parts = _normalize_path(path, separator)
    current: Any = d
    for part in parts[:-1]:
        if not isinstance(current, MutableMapping) or part not in current:
            if default is not UNSET:
                return default
            raise KeyError(f"path {path!r} not found at segment {part!r}")
        current = current[part]

    last = parts[-1]
    if not isinstance(current, MutableMapping) or last not in current:
        if default is not UNSET:
            return default
        raise KeyError(f"path {path!r} not found at leaf {last!r}")
    return current.pop(last)


def deep_merge(
    base: Mapping[str, Any],
    override: Mapping[str, Any],
    *,
    list_strategy: Literal["replace", "concat", "dedup"] = "replace",
    max_depth: int | None = 100,
) -> dict[str, Any]:
    """Recursively merge two mappings, returning a new dict (no mutation).

    Behavior by case:

    - Both values are dicts → recurse, merging their keys.
    - Both values are lists → apply ``list_strategy``.
    - Otherwise → ``override`` wins.

    Mappings, lists and sets are copied. Other leaves follow their ``deepcopy``
    protocol; a protocol may return the original object, and copying failures
    retain its original identity. Such shared leaves retain any mutable state.
    Mutating a shared leaf in the result also mutates that original leaf; callers
    requiring full isolation must ensure their leaves support independent copies.

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
    max_depth : int | None, optional
        Maximum recursion depth allowed when traversing nested structures.
        Defaults to 100 to protect against call-stack exhaustion. Pass ``None``
        to disable depth checking.

    Returns
    -------
    dict[str, Any]
        A new dict containing the merged result. The merge does not mutate
        inputs; non-copyable leaf objects retain their original identity.

    Raises
    ------
    TypeError
        If ``base`` or ``override`` is not a mapping.
    ValueError
        If ``list_strategy`` is not one of the allowed values, if ``max_depth``
        is invalid, or if nesting exceeds ``max_depth``.

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
    if not isinstance(base, Mapping) or not isinstance(override, Mapping):
        raise TypeError("base and override must be mappings")
    if list_strategy not in ("replace", "concat", "dedup"):
        raise ValueError(
            f"list_strategy must be one of 'replace', 'concat', 'dedup'; "
            f"got {list_strategy!r}"
        )
    if max_depth is not None and (
        isinstance(max_depth, bool)
        or not isinstance(max_depth, int)
        or max_depth < 0
    ):
        raise ValueError(
            f"max_depth must be a non-negative integer or None, got {max_depth!r}"
        )

    memo: dict[int, Any] = {}
    merge_memo: dict[tuple[int, int], Any] = {}

    def _isolate(
        val: Any,
        depth: int,
    ) -> Any:
        """Return a deep, cycle-safe copy of ``val`` preserving shared references.

        Parameters
        ----------
        val : Any
            Value to isolate from the source mapping.
        depth : int
            Current recursion depth.

        Returns
        -------
        Any
            A cycle-safe copy of containers. Leaf identity follows its copy
            protocol; failed copies retain the original object and mutable state.
        """
        if max_depth is not None and depth > max_depth:
            raise ValueError(
                f"maximum mapping merge depth exceeded ({max_depth})"
            )
        val_id = id(val)
        if val_id in memo:
            return memo[val_id]

        if isinstance(val, Mapping):
            res_dict: dict[Any, Any] = {}
            memo[val_id] = res_dict
            for k, v in val.items():
                res_dict[k] = _isolate(v, depth + 1)
            return res_dict
        if isinstance(val, list):
            res_list: list[Any] = []
            memo[val_id] = res_list
            for v in val:
                res_list.append(_isolate(v, depth + 1))
            return res_list
        if isinstance(val, set):
            res_set: set[Any] = set()
            memo[val_id] = res_set
            for v in val:
                res_set.add(_isolate(v, depth + 1))
            return res_set
        if isinstance(val, frozenset):
            res_frozenset = frozenset(_isolate(v, depth + 1) for v in val)
            memo[val_id] = res_frozenset
            return res_frozenset
        if isinstance(val, tuple):
            y = [_isolate(v, depth + 1) for v in val]
            if val_id in memo:
                return memo[val_id]
            for k, j in zip(val, y, strict=True):
                if k is not j:
                    res_tuple = tuple(y)
                    break
            else:
                res_tuple = val
            memo[val_id] = res_tuple
            return res_tuple
        try:
            copied = copy.deepcopy(val, memo)
            memo[val_id] = copied
            return copied
        except Exception:
            memo[val_id] = val
            return val

    def _merge(
        a: Any,
        b: Any,
        depth: int,
    ) -> Any:
        """Merge two values recursively without mutating either input.

        Parameters
        ----------
        a : Any
            Base value; takes precedence for non-list/non-mapping pairs.
        b : Any
            Override value; wins over ``a`` for scalars and mixed pairs.
        depth : int
            Current recursion depth.

        Returns
        -------
        Any
            The merged value as a fresh, isolated structure.
        """
        if max_depth is not None and depth > max_depth:
            raise ValueError(
                f"maximum mapping merge depth exceeded ({max_depth})"
            )
        if isinstance(a, Mapping) and isinstance(b, Mapping):
            pair_key = (id(a), id(b))
            if pair_key in merge_memo:
                return merge_memo[pair_key]
            #? Build a new dict so neither input is mutated; recurse on each key.
            out: dict[str, Any] = {}
            merge_memo[pair_key] = out
            for key in a:
                out[key] = (
                    _merge(a[key], b[key], depth + 1)
                    if key in b
                    else _isolate(a[key], depth + 1)
                )
            for key in b:
                if key not in a:
                    out[key] = _isolate(b[key], depth + 1)
            return out
        if isinstance(a, list) and isinstance(b, list):
            if list_strategy == "replace":
                return _isolate(b, depth + 1)
            if list_strategy == "concat":
                return _isolate(a, depth + 1) + _isolate(b, depth + 1)
            #? dedup: first occurrence wins, order = base then override.
            #? Unhashable items (e.g. dicts) fall through without being
            #? tracked; that mirrors common stdlib semantics and avoids
            #? forcing the caller to pre-normalize their data.
            seen_hashable: set[Any] = set()
            seen_unhashable: list[Any] = []
            result: list[Any] = []
            for item in (*a, *b):
                marker = (_BOOL_SENTINEL, item) if isinstance(item, bool) else item
                try:
                    if marker in seen_hashable:
                        continue
                    seen_hashable.add(marker)
                except TypeError:
                    if any(item == previous for previous in seen_unhashable):
                        continue
                    seen_unhashable.append(item)
                result.append(_isolate(item, depth + 1))
            return result
        #? Non-dict / non-list: override wins. Plain scalars and mixed
        #? type pairs all fall through here.
        return _isolate(b, depth + 1)

    return cast(dict[str, Any], _merge(base, override, 0))
