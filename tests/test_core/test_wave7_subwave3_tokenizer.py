"""Tests for Wave 7 Sub-Wave 3: Lexical Tokenization, Text Scanning & Pattern Matching."""

import pytest

from gunz_utils.tokenizer import (
    RegexTokenizer,
    StringScanner,
    TokenizerError,
    glob_to_regex,
    match_glob,
)


def test_regex_tokenizer():
    lexer = RegexTokenizer()
    lexer.add_rule("NUMBER", r"\d+")
    lexer.add_rule("IDENT", r"[a-zA-Z_]\w*")
    lexer.add_rule("PLUS", r"\+")
    lexer.add_rule("ASSIGN", r"=")

    text = "x = 42 + y"
    tokens = list(lexer.tokenize(text, skip_whitespace=True))
    assert len(tokens) == 5
    assert [t.type for t in tokens] == ["IDENT", "ASSIGN", "NUMBER", "PLUS", "IDENT"]
    assert [t.value for t in tokens] == ["x", "=", "42", "+", "y"]

    with pytest.raises(TokenizerError):
        list(lexer.tokenize("x = @ + y", skip_whitespace=True))


def test_string_scanner():
    s = StringScanner("foo 123 bar")
    assert not s.is_eos()
    assert s.peek(3) == "foo"
    assert s.scan(r"[a-z]+") == "foo"
    assert s.skip_whitespace() == 1
    assert s.scan(r"\d+") == "123"
    assert s.skip_whitespace() == 1
    assert s.scan(r"[a-z]+") == "bar"
    assert s.is_eos()


def test_glob_to_regex_and_match():
    assert match_glob("file.py", "*.py")
    assert not match_glob("file.txt", "*.py")
    assert match_glob("src/core/test.py", "**/*.py")
    assert not match_glob("src/core/test.txt", "**/*.py")
    assert match_glob("a/b/c", "a/**")
    assert match_glob("log1.txt", "log[0-9].txt")
    assert not match_glob("logA.txt", "log[0-9].txt")
