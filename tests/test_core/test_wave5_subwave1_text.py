"""Tests for Wave 5 Sub-Wave 1: Text Analysis, String Metrics & Wrapping (#1–#13)."""
from __future__ import annotations

import pytest
from gunz_utils.text import (
    camel_to_snake,
    damerau_levenshtein_distance,
    dedent_block,
    hamming_distance,
    indent_block,
    jaro_winkler_similarity,
    levenshtein_distance,
    slugify,
    snake_to_camel,
    title_case,
    truncate,
    truncate_text,
    word_wrap,
)


def test_levenshtein_distance():
    assert levenshtein_distance("kitten", "sitting") == 3
    assert levenshtein_distance("flaw", "lawn") == 2
    assert levenshtein_distance("same", "same") == 0
    assert levenshtein_distance("", "hello") == 5
    assert levenshtein_distance("hello", "") == 5

    # max_distance early exit
    assert levenshtein_distance("kitten", "sitting", max_distance=1) == 2
    assert levenshtein_distance("kitten", "sitting", max_distance=5) == 3

    with pytest.raises(TypeError):
        levenshtein_distance(123, "sitting")  # type: ignore[arg-type]
    with pytest.raises(ValueError):
        levenshtein_distance("a", "b", max_distance=-1)


def test_damerau_levenshtein_distance():
    # Adjacent transposition is distance 1 in Damerau, but 2 in Levenshtein
    assert damerau_levenshtein_distance("ab", "ba") == 1
    assert levenshtein_distance("ab", "ba") == 2

    assert damerau_levenshtein_distance("ca", "abc") == 2
    assert damerau_levenshtein_distance("hello", "hlelo") == 1
    assert damerau_levenshtein_distance("", "world") == 5


def test_jaro_winkler_similarity():
    assert jaro_winkler_similarity("same", "same") == 1.0
    assert jaro_winkler_similarity("", "test") == 0.0

    # High similarity with common prefix
    sim = jaro_winkler_similarity("martha", "marhta")
    assert 0.9 < sim < 1.0

    # Completely different
    assert jaro_winkler_similarity("abc", "xyz") == 0.0

    with pytest.raises(ValueError, match="prefix_weight"):
        jaro_winkler_similarity("a", "b", prefix_weight=0.5)


def test_hamming_distance():
    assert hamming_distance("karolin", "kathrin") == 3
    assert hamming_distance("1011101", "1001001") == 2
    assert hamming_distance(b"abc", b"axc") == 1

    with pytest.raises(ValueError, match="equal length"):
        hamming_distance("short", "longer_string")

    with pytest.raises(TypeError):
        hamming_distance("str", b"byt")  # type: ignore[arg-type]


def test_slugify():
    assert slugify("Hello, World!") == "hello-world"
    assert slugify("Python 3.11 & Utilities", separator="_") == "python_311_utilities"
    assert slugify("Keep UPPERCASE", lowercase=False) == "Keep-UPPERCASE"


def test_truncate_and_word_boundary():
    text = "The quick brown fox jumps over the lazy dog"
    assert truncate(text, 16) == "The quick bro..."
    assert truncate_text(text, 16) == "The quick bro..."

    # Word boundary
    assert truncate(text, 16, word_boundary=True) == "The quick..."
    assert truncate(text, 100) == text
    assert truncate(text, 3) == "..."


def test_word_wrap():
    text = "This is a test of the emergency broadcasting network for text wrapping."
    wrapped = word_wrap(text, width=25)
    lines = wrapped.split("\n")
    assert all(len(line) <= 25 for line in lines)
    assert len(lines) >= 3


def test_indent_and_dedent_block():
    text = "line1\n\nline2\n"
    indented = indent_block(text, prefix=">> ")
    assert indented == ">> line1\n\n>> line2\n"

    code = "    def hello():\n        return 42\n"
    dedented = dedent_block(code)
    assert dedented == "def hello():\n    return 42\n"


def test_camel_to_snake():
    assert camel_to_snake("camelCase") == "camel_case"
    assert camel_to_snake("PascalCase") == "pascal_case"
    assert camel_to_snake("getHTTPResponse") == "get_http_response"
    assert camel_to_snake("already_snake") == "already_snake"


def test_snake_to_camel():
    assert snake_to_camel("snake_case") == "snakeCase"
    assert snake_to_camel("snake_case", capitalize_first=True) == "SnakeCase"
    assert snake_to_camel("single") == "single"
    assert snake_to_camel("single", capitalize_first=True) == "Single"


def test_title_case():
    assert title_case("the lord of the rings") == "The Lord of the Rings"
    assert title_case("war and peace") == "War and Peace"
    assert title_case("a tale of two cities") == "A Tale of Two Cities"
