"""Tests for Wave 6 Sub-Wave 4: Trie & Prefix Matching Data Structures."""

from gunz_utils.trie import Trie, longest_common_prefix


def test_trie_insert_search_delete():
    trie = Trie()
    assert len(trie) == 0
    trie.insert("apple", 10)
    trie.insert("app", 5)
    trie.insert("banana", 20)

    assert len(trie) == 3
    assert "apple" in trie
    assert "app" in trie
    assert "orange" not in trie

    assert trie.search("apple") == 10
    assert trie.search("app") == 5
    assert trie.search("ap") is None

    assert trie.starts_with("app")
    assert trie.starts_with("ban")
    assert not trie.starts_with("cat")

    # Delete
    assert trie.delete("app")
    assert "app" not in trie
    assert "apple" in trie
    assert len(trie) == 2


def test_trie_autocomplete_and_find_with_prefix():
    trie = Trie()
    trie.insert("car", 1)
    trie.insert("cart", 2)
    trie.insert("carpet", 3)
    trie.insert("dog", 4)

    matches = trie.autocomplete("car")
    assert matches == ["car", "carpet", "cart"]

    limited = trie.autocomplete("car", limit=2)
    assert len(limited) == 2

    prefix_dict = trie.find_with_prefix("car")
    assert prefix_dict == {"car": 1, "carpet": 3, "cart": 2}


def test_longest_common_prefix():
    assert longest_common_prefix(["flower", "flow", "flight"]) == "fl"
    assert longest_common_prefix(["dog", "racecar", "car"]) == ""
    assert longest_common_prefix(["single"]) == "single"
    assert longest_common_prefix([]) == ""
