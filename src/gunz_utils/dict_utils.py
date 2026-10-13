"""Helpers for working with nested mappings (dotted-path access, recursive merge)."""
from __future__ import annotations

__author__ = "Yeremia Gunawan Adhisantoso"
__email__ = "yeremiag@gmail.com"
__license__ = "Clear BSD"

# =============================================================================
# STANDARD LIBRARY IMPORTS
# =============================================================================
import copy
from collections.abc import Hashable, Mapping, MutableMapping, Sequence
from typing import Any, Literal, cast

# =============================================================================
# THIRD-PARTY IMPORTS
# =============================================================================
# isort: split
# =============================================================================
# LOCAL APPLICATION IMPORTS
# =============================================================================
from ._version import __version__ as __version__

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

    def _dotted() -> str:
        #? Built lazily and only for error messages: segments may be
        #? non-string (e.g. an int key written by ``deep_set``), which
        #? ``str.join`` would reject.
        return separator.join(str(part) for part in parts)

    cursor: Any = d
    for key in parts:
        if not isinstance(cursor, Mapping):
            #? A list, int, or str in the middle of a path means the user
            #? asked for something that doesn't structurally exist. Treat it
            #? as "not found" rather than raising TypeError so callers can
            #? probe config trees safely.
            if default is _MISSING:
                raise KeyError(_dotted())
            return default
        try:
            cursor = cursor[key]
        except (KeyError, IndexError, TypeError):
            if default is _MISSING:
                raise KeyError(_dotted()) from None
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

    Returns
    -------
    dict[str, Any]
        A new dict containing the merged result. The merge does not mutate
        inputs; non-copyable leaf objects retain their original identity.

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
    merge_memo: dict[tuple[int, int], Any] = {}

    def _isolate(
        val: Any,
    ) -> Any:
        """Return a deep, cycle-safe copy of ``val`` preserving shared references.

        Parameters
        ----------
        val : Any
            Value to isolate from the source mapping.

        Returns
        -------
        Any
            A cycle-safe copy of containers. Leaf identity follows its copy
            protocol; failed copies retain the original object and mutable state.

        Notes
        -----
        This is an iterative, post-order traversal (unlike a recursive deep
        copy) so that deeply nested or untrusted config trees cannot overflow
        the interpreter stack with a ``RecursionError``. Mapping/list/set
        shells are registered in ``memo`` before their children are filled,
        which preserves cycle and shared-reference semantics exactly.
        """
        val_id = id(val)
        if val_id in memo:
            return memo[val_id]
        if not isinstance(val, Mapping | list | set | tuple):
            try:
                copied = copy.deepcopy(val, memo)
                memo[val_id] = copied
            except Exception:
                memo[val_id] = val
            return memo[val_id]

        def _key_sink(
            shell: dict[Any, Any],
            key: Any,
        ) -> Any:
            def sink(
                value: Any,
            ) -> None:
                shell[key] = value

            return sink

        def _append_sink(
            container: list[Any],
        ) -> Any:
            def sink(
                value: Any,
            ) -> None:
                container.append(value)

            return sink

        def _add_sink(
            container: set[Any],
        ) -> Any:
            def sink(
                value: Any,
            ) -> None:
                container.add(value)

            return sink

        root_box: list[Any] = []
        #? Each frame: (action, node, slot, payload). ``slot`` is a sink that
        #? receives the isolated child result (``None`` for the root); for a
        #? tuple, ``payload`` accumulates its isolated children in order.
        stack: list[tuple[str, Any, Any, Any]] = [("expand", val, None, None)]
        while stack:
            action, node, slot, payload = stack.pop()
            node_id = id(node)
            if action == "expand":
                if node_id in memo:
                    result = memo[node_id]
                    if slot is None:
                        root_box.append(result)
                    else:
                        slot(result)
                    continue
                if not isinstance(node, Mapping | list | set | tuple):
                    try:
                        copied = copy.deepcopy(node, memo)
                        memo[node_id] = copied
                    except Exception:
                        memo[node_id] = node
                    result = memo[node_id]
                    if slot is None:
                        root_box.append(result)
                    else:
                        slot(result)
                    continue
                if isinstance(node, Mapping):
                    shell: dict[Any, Any] = {}
                    memo[node_id] = shell
                    if slot is None:
                        root_box.append(shell)
                    else:
                        slot(shell)
                    #? Push in reverse so LIFO pop order preserves key order.
                    for key, child in reversed(list(node.items())):
                        stack.append(("expand", child, _key_sink(shell, key), None))
                elif isinstance(node, list):
                    shell_list: list[Any] = []
                    memo[node_id] = shell_list
                    if slot is None:
                        root_box.append(shell_list)
                    else:
                        slot(shell_list)
                    #? Push in reverse so LIFO pop order preserves list order.
                    for child in reversed(node):
                        stack.append(("expand", child, _append_sink(shell_list), None))
                elif isinstance(node, set):
                    shell_set: set[Any] = set()
                    memo[node_id] = shell_set
                    if slot is None:
                        root_box.append(shell_set)
                    else:
                        slot(shell_set)
                    for child in node:
                        stack.append(("expand", child, _add_sink(shell_set), None))
                else:
                    children: list[Any] = []
                    stack.append(("tuple_finalize", node, slot, children))
                    #? Push in reverse so LIFO pop order preserves tuple order.
                    for child in reversed(node):
                        stack.append(("expand", child, _append_sink(children), None))
            else:  #? tuple_finalize
                if node_id in memo:
                    result = memo[node_id]
                else:
                    #? Reuse the original tuple when no child changed identity;
                    #? otherwise materialize a new tuple from isolated children.
                    for k, j in zip(node, payload, strict=True):
                        if k is not j:
                            result = tuple(payload)
                            break
                    else:
                        result = node
                    memo[node_id] = result
                if slot is None:
                    root_box.append(result)
                else:
                    slot(result)

        return root_box[0]

    def _merge_lists(
        a: list[Any],
        b: list[Any],
    ) -> list[Any]:
        """Merge two lists under the configured ``list_strategy``."""
        if list_strategy == "replace":
            return cast(list[Any], _isolate(b))
        if list_strategy == "concat":
            return cast(list[Any], _isolate(a)) + cast(list[Any], _isolate(b))
        #? dedup: first occurrence wins, order = base then override.
        #? Unhashable items (e.g. dicts) fall through without being tracked;
        #? that mirrors common stdlib semantics and avoids forcing the caller
        #? to pre-normalize their data.
        #? ``bool`` is a strict subtype of ``int`` in the package's numeric
        #? contract, so boolean leaves must stay distinct from equal-valued
        #? integers: ``True`` is not deduplicated against ``1``, ``False``
        #? against ``0``. Keying booleans as ``(bool, value)`` keeps them out
        #? of the integer keys while leaving every other hashable type
        #? unchanged.
        seen_hashable: set[Any] = set()
        seen_unhashable: list[Any] = []
        result: list[Any] = []
        for item in (*a, *b):
            #? Duplicate detection must be symmetric: two equal values that
            #? differ only in hashability (e.g. ``{1, 2}`` vs
            #? ``frozenset({1, 2})``) must collapse to one kept item regardless
            #? of base/override order. Checking equality against BOTH the
            #? hashable set and the unhashable list, in either branch, removes
            #? the order-dependence of the old set-membership test (CPython's
            #? ``in`` on an equal-but-unhashable needle is order-dependent).
            marker: Any = (bool, item) if isinstance(item, bool) else item
            if any(marker == previous for previous in seen_unhashable):
                continue
            if isinstance(marker, Hashable):
                if marker in seen_hashable:
                    continue
                seen_hashable.add(marker)
            else:
                if any(marker == previous for previous in seen_hashable):
                    continue
                seen_unhashable.append(marker)
            result.append(_isolate(item))
        return result

    def _merge(
        a: Any,
        b: Any,
    ) -> Any:
        """Merge two values iteratively without mutating either input.

        Parameters
        ----------
        a : Any
            Base value; takes precedence for non-list/non-mapping pairs.
        b : Any
            Override value; wins over ``a`` for scalars and mixed pairs.

        Returns
        -------
        Any
            The merged value as a fresh, isolated structure.
        """
        #? An explicit work stack (rather than recursion) keeps the merge
        #? bounded on deeply nested mappings: pairs are registered in
        #? ``merge_memo`` before their children are scheduled, preserving
        #? cycle and shared-reference semantics.
        root_box: list[Any] = []
        #? Frames: ("merge", a, b, target) or ("isolate", _, value, target),
        #? where target is ``None`` (root) or ``(out_dict, key)``.
        stack: list[tuple[str, Any, Any, Any]] = [("merge", a, b, None)]
        while stack:
            action, aa, bb, target = stack.pop()
            if action == "isolate":
                result = _isolate(bb)
                if target is None:
                    root_box.append(result)
                else:
                    parent, key = target
                    parent[key] = result
                continue
            if isinstance(aa, Mapping) and isinstance(bb, Mapping):
                pair_key = (id(aa), id(bb))
                if pair_key in merge_memo:
                    result = merge_memo[pair_key]
                else:
                    #? Build a new dict so neither input is mutated; fill
                    #? children in place so the pair resolves to ``out`` on
                    #? any back-reference (cycle safety).
                    out: dict[Any, Any] = {}
                    merge_memo[pair_key] = out
                    result = out
                    tasks: list[tuple[str, Any, Any, Any]] = []
                    for key in aa:
                        if key in bb:
                            tasks.append(("merge", aa[key], bb[key], (out, key)))
                        else:
                            tasks.append(("isolate", None, aa[key], (out, key)))
                    for key in bb:
                        if key not in aa:
                            tasks.append(("isolate", None, bb[key], (out, key)))
                    #? Push reversed so LIFO pop order preserves key order.
                    for task in reversed(tasks):
                        stack.append(task)
                if target is None:
                    root_box.append(result)
                else:
                    parent, key = target
                    parent[key] = result
            elif isinstance(aa, list) and isinstance(bb, list):
                result = _merge_lists(aa, bb)
                if target is None:
                    root_box.append(result)
                else:
                    parent, key = target
                    parent[key] = result
            else:
                #? Non-dict / non-list: override wins. Plain scalars and
                #? mixed type pairs all fall through here.
                result = _isolate(bb)
                if target is None:
                    root_box.append(result)
                else:
                    parent, key = target
                    parent[key] = result

        return root_box[0]

    return cast(dict[str, Any], _merge(base, override))
