"""Tests for Wave 7 Sub-Wave 4: Tree Structures & Hierarchy Algorithms."""

# =============================================================================
# LOCAL APPLICATION IMPORTS
# =============================================================================

from gunz_utils.trees import (
    TreeNode,
    lowest_common_ancestor,
    tree_from_dict,
    tree_height,
    tree_level_order,
    tree_postorder,
    tree_preorder,
    tree_size,
    tree_to_dict,
)


def test_tree_construction_and_properties():
    root = TreeNode("root")
    c1 = root.add_child("c1")
    root.add_child("c2")
    c1_1 = c1.add_child("c1_1")

    assert root.is_root
    assert not c1.is_root
    assert c1_1.is_leaf
    assert not c1.is_leaf

    assert c1_1.depth == 2
    assert c1.depth == 1
    assert root.depth == 0

    assert tree_height(root) == 2
    assert tree_height(c1_1) == 0
    assert tree_size(root) == 4


def test_tree_traversals():
    root = TreeNode(1)
    c1 = root.add_child(2)
    root.add_child(3)
    c1.add_child(4)
    c1.add_child(5)

    pre = [n.value for n in tree_preorder(root)]
    assert pre == [1, 2, 4, 5, 3]

    post = [n.value for n in tree_postorder(root)]
    assert post == [4, 5, 2, 3, 1]

    lvl = [n.value for n in tree_level_order(root)]
    assert lvl == [1, 2, 3, 4, 5]


def test_lowest_common_ancestor():
    root = TreeNode("A")
    b = root.add_child("B")
    c = root.add_child("C")
    d = b.add_child("D")
    e = b.add_child("E")

    lca_de = lowest_common_ancestor(root, d, e)
    assert lca_de == b

    lca_dc = lowest_common_ancestor(root, d, c)
    assert lca_dc == root


def test_tree_serialization():
    root = TreeNode("root")
    c1 = root.add_child("sub")
    c1.add_child("leaf")

    d = tree_to_dict(root)
    assert d["value"] == "root"
    assert len(d["children"]) == 1

    restored = tree_from_dict(d)
    assert restored.value == "root"
    assert restored.children[0].children[0].value == "leaf"
