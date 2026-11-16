"""Prefix tree (Trie) for fast prefix searching, autocompletion, and key-value indexing.
"""

# =============================================================================
# STANDARD LIBRARY IMPORTS
# =============================================================================

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass, field
from typing import Generic, TypeVar

T = TypeVar("T")


@dataclass(slots=True)
class TrieNode(Generic[T]):
    """Individual node within a prefix tree."""

    children: dict[str, TrieNode[T]] = field(default_factory=dict)
    is_terminal: bool = False
    value: T | None = None


class Trie(Generic[T]):
    """Memory-efficient prefix tree for string indexing and autocomplete."""

    def __init__(self) -> None:
        self.root: TrieNode[T] = TrieNode()
        self._size: int = 0

    def __len__(self) -> int:
        """Return the number of stored keys in the trie."""
        return self._size

    def __contains__(self,
        key: str,
    ) -> bool:
        """Return True if key exists in trie."""
        return self.search(key) is not None or (self._find_node(
            key) is not None and self._find_node(key).is_terminal)  # type: ignore[union-attr]

    def clear(self) -> None:
        """Reset the trie to empty."""
        self.root = TrieNode()
        self._size = 0

    def insert(self,
        key: str,
        value: T | None = None,
    ) -> None:
        """Insert a string key and optional associated value."""
        if not isinstance(key, str):
            raise TypeError(f"key must be a string, got {type(key).__name__}")
        curr = self.root
        for char in key:
            if char not in curr.children:
                curr.children[char] = TrieNode()
            curr = curr.children[char]
        if not curr.is_terminal:
            self._size += 1
            curr.is_terminal = True
        curr.value = value

    def _find_node(self,
        prefix: str,
    ) -> TrieNode[T] | None:
        curr = self.root
        for char in prefix:
            if char not in curr.children:
                return None
            curr = curr.children[char]
        return curr

    def search(self,
        key: str,
    ) -> T | None:
        """Look up the value associated with key. Returns None if missing."""
        node = self._find_node(key)
        if node is not None and node.is_terminal:
            return node.value
        return None

    def starts_with(self,
        prefix: str,
    ) -> bool:
        """Check if any key in the trie starts with prefix."""
        return self._find_node(prefix) is not None

    def autocomplete(self,
        prefix: str,
        limit: int | None = None,
    ) -> list[str]:
        """Find all keys starting with prefix, optionally limited."""
        if limit is not None and (
    isinstance(
        limit,
        bool) or not isinstance(
            limit,
             int) or limit < 0):
            raise ValueError("limit must be a non-negative integer or None")
        start_node = self._find_node(prefix)
        if start_node is None:
            return []

        results: list[str] = []

        def dfs(
            node: TrieNode[T],
            path: list[str],
        ) -> None:
            if limit is not None and len(results) >= limit:
                return
            if node.is_terminal:
                results.append("".join(path))
            for char in sorted(node.children.keys()):
                path.append(char)
                dfs(node.children[char], path)
                path.pop()

        dfs(start_node, list(prefix))
        return results

    def find_with_prefix(self,
        prefix: str,
    ) -> dict[str, T | None]:
        """Return a mapping of all keys starting with prefix to their stored values."""
        start_node = self._find_node(prefix)
        if start_node is None:
            return {}

        results: dict[str, T | None] = {}

        def dfs(
            node: TrieNode[T],
            path: list[str],
        ) -> None:
            if node.is_terminal:
                results["".join(path)] = node.value
            for char in sorted(node.children.keys()):
                path.append(char)
                dfs(node.children[char], path)
                path.pop()

        dfs(start_node, list(prefix))
        return results

    def delete(self,
        key: str,
    ) -> bool:
        """Delete a key from the trie and prune dead nodes. Returns True if deleted."""
        stack: list[tuple[TrieNode[T], str]] = []
        curr = self.root
        for char in key:
            if char not in curr.children:
                return False
            stack.append((curr, char))
            curr = curr.children[char]

        if not curr.is_terminal:
            return False

        curr.is_terminal = False
        curr.value = None
        self._size -= 1

        #? Prune bottom-up
        if not curr.children:
            for parent, char in reversed(stack):
                child = parent.children[char]
                if not child.children and not child.is_terminal:
                    del parent.children[char]
                else:
                    break
        return True


def longest_common_prefix(
    words: Sequence[str],
) -> str:
    """Find the longest common prefix among a sequence of strings."""
    if not words:
        return ""
    if len(words) == 1:
        return words[0]
    shortest = min(words, key=len)
    for i, char in enumerate(shortest):
        for other in words:
            if other[i] != char:
                return shortest[:i]
    return shortest


__all__ = [
    "Trie",
    "TrieNode",
    "longest_common_prefix",
]
