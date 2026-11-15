"""Generic n-ary tree structures, lowest common ancestors, and hierarchy algorithms."""

from __future__ import annotations

from collections import deque
from collections.abc import Iterator
from dataclasses import dataclass, field
from typing import Any, Generic, TypeVar

T = TypeVar("T")


@dataclass(eq=False)
class TreeNode(Generic[T]):
    """Generic n-ary tree node with parent/children pointers."""

    value: T
    parent: TreeNode[T] | None = None
    children: list[TreeNode[T]] = field(default_factory=list)

    def __hash__(self) -> int:
        return id(self)

    def __eq__(self, other: object) -> bool:
        return self is other

    @property
    def is_leaf(self) -> bool:
        """Return True if node has no children."""
        return len(self.children) == 0

    @property
    def is_root(self) -> bool:
        """Return True if node has no parent."""
        return self.parent is None

    @property
    def depth(self) -> int:
        """Return the distance from the tree root to this node."""
        d = 0
        curr = self.parent
        while curr is not None:
            d += 1
            curr = curr.parent
        return d

    def add_child(self, child: TreeNode[T] | T) -> TreeNode[T]:
        """Add child to this node and set child's parent pointer."""
        if not isinstance(child, TreeNode):
            node = TreeNode(value=child, parent=self)
        else:
            node = child
            node.parent = self
        self.children.append(node)
        return node

    def remove_child(self, child: TreeNode[T]) -> bool:
        """Remove child from this node. Returns True if removed."""
        if child in self.children:
            self.children.remove(child)
            child.parent = None
            return True
        return False


def tree_preorder(root: TreeNode[T]) -> Iterator[TreeNode[T]]:
    """Yield tree nodes in preorder (parent before children)."""
    yield root
    for child in root.children:
        yield from tree_preorder(child)


def tree_postorder(root: TreeNode[T]) -> Iterator[TreeNode[T]]:
    """Yield tree nodes in postorder (children before parent)."""
    for child in root.children:
        yield from tree_postorder(child)
    yield root


def tree_level_order(root: TreeNode[T]) -> Iterator[TreeNode[T]]:
    """Yield tree nodes in breadth-first level order."""
    queue = deque([root])
    while queue:
        curr = queue.popleft()
        yield curr
        queue.extend(curr.children)


def tree_height(node: TreeNode[T]) -> int:
    """Return maximum height of subtree (0 for a leaf)."""
    if node.is_leaf:
        return 0
    return 1 + max(tree_height(child) for child in node.children)


def tree_size(node: TreeNode[T]) -> int:
    """Return the total number of nodes in the subtree rooted at node."""
    return 1 + sum(tree_size(child) for child in node.children)


def lowest_common_ancestor(
    root: TreeNode[T],
    a: TreeNode[T],
    b: TreeNode[T],
) -> TreeNode[T] | None:
    """Find the lowest common ancestor node between a and b."""
    ancestors_a: set[TreeNode[T]] = set()
    curr: TreeNode[T] | None = a
    while curr is not None:
        ancestors_a.add(curr)
        curr = curr.parent

    curr = b
    while curr is not None:
        if curr in ancestors_a:
            return curr
        curr = curr.parent
    return None


def tree_to_dict(root: TreeNode[T]) -> dict[str, Any]:
    """Serialize tree structure into a nested dictionary."""
    return {
        "value": root.value,
        "children": [tree_to_dict(child) for child in root.children],
    }


def tree_from_dict(d: dict[str, Any]) -> TreeNode[Any]:
    """Deserialize a nested dictionary into a TreeNode hierarchy."""
    node = TreeNode(value=d.get("value"))
    for child_dict in d.get("children", []):
        child_node = tree_from_dict(child_dict)
        node.add_child(child_node)
    return node


__all__ = [
    "TreeNode",
    "lowest_common_ancestor",
    "tree_from_dict",
    "tree_height",
    "tree_level_order",
    "tree_postorder",
    "tree_preorder",
    "tree_size",
    "tree_to_dict",
]
