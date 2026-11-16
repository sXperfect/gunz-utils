"""Lexical tokenization, cursor-based string scanning, and glob-to-regex compilation."""

# =============================================================================
# STANDARD LIBRARY IMPORTS
# =============================================================================

from __future__ import annotations

import re
from collections.abc import Iterator
from dataclasses import dataclass


class TokenizerError(ValueError):
    """Raised when tokenization encounters an illegal character."""

    def __init__(self,
        message: str,
        line: int,
        column: int,
        pos: int,
    ) -> None:
        super().__init__(f"{message} at line {line}, column {column} (pos {pos})")
        self.line = line
        self.column = column
        self.pos = pos


@dataclass(frozen=True, slots=True)
class Token:
    """Discrete lexical token."""

    type: str
    value: str
    line: int
    column: int
    span: tuple[int, int]


class RegexTokenizer:
    """Rule-based regular expression lexer with precise line/column tracking."""

    def __init__(self) -> None:
        self.rules: list[tuple[str, re.Pattern[str]]] = []

    def add_rule(self,
        token_type: str,
        pattern: str,
    ) -> RegexTokenizer:
        """Register a token type with a regex pattern."""
        if not token_type or not isinstance(token_type, str):
            raise ValueError("token_type must be a non-empty string")
        self.rules.append((token_type, re.compile(pattern)))
        return self

    def tokenize(self,
        text: str,
        skip_whitespace: bool = False,
    ) -> Iterator[Token]:
        """Yield tokens from input text."""
        pos = 0
        line = 1
        column = 1
        n = len(text)

        while pos < n:
            if skip_whitespace and text[pos].isspace():
                if text[pos] == "\n":
                    line += 1
                    column = 1
                else:
                    column += 1
                pos += 1
                continue

            matched = False
            for token_type, pattern in self.rules:
                match = pattern.match(text, pos)
                if match:
                    val = match.group(0)
                    start_pos = pos
                    end_pos = pos + len(val)
                    yield Token(
                        type=token_type,
                        value=val,
                        line=line,
                        column=column,
                        span=(start_pos, end_pos),
                    )
                    #? Advance lines and columns
                    newline_count = val.count("\n")
                    if newline_count > 0:
                        line += newline_count
                        last_nl = val.rfind("\n")
                        column = len(val) - last_nl
                    else:
                        column += len(val)
                    pos = end_pos
                    matched = True
                    break

            if not matched:
                char = repr(text[pos])
                raise TokenizerError(f"unexpected character {char}", line, column, pos)


class StringScanner:
    """Cursor-based string scanner with lookahead and regex matching."""

    def __init__(self,
        text: str,
    ) -> None:
        self.text = text
        self.pos = 0

    def is_eos(self) -> bool:
        """Return True if cursor has reached end of string."""
        return self.pos >= len(self.text)

    def peek(self,
        n: int = 1,
    ) -> str:
        """Preview next n characters without advancing cursor."""
        return self.text[self.pos : self.pos + n]

    def scan(self,
        pattern: str | re.Pattern[str],
    ) -> str | None:
        """Attempt to match regex at current position; advances cursor on match."""
        regex = re.compile(pattern) if isinstance(pattern, str) else pattern
        match = regex.match(self.text, self.pos)
        if match:
            matched_str = match.group(0)
            self.pos += len(matched_str)
            return matched_str
        return None

    def skip_whitespace(self) -> int:
        """Advance cursor past any whitespace characters. Returns count skipped."""
        count = 0
        while self.pos < len(self.text) and self.text[self.pos].isspace():
            self.pos += 1
            count += 1
        return count

    def reset(self,
        pos: int = 0,
    ) -> None:
        """Reset cursor to given position."""
        if not (0 <= pos <= len(self.text)):
            raise IndexError("position out of bounds")
        self.pos = pos


def glob_to_regex(
    pattern: str,
) -> str:
    """Convert Unix glob pattern to equivalent compiled regular expression string."""
    i = 0
    n = len(pattern)
    res: list[str] = ["^"]

    while i < n:
        c = pattern[i]
        if c == "*":
            if i + 1 < n and pattern[i + 1] == "*":
                #? '**' matches across path segments
                i += 2
                if i < n and pattern[i] == "/":
                    i += 1
                    res.append("(?:.*/)?")
                else:
                    res.append(".*")
            else:
                #? '*' matches within path segment
                res.append("[^/]*")
                i += 1
        elif c == "?":
            res.append("[^/]")
            i += 1
        elif c == "[":
            j = i + 1
            if j < n and pattern[j] == "!":
                j += 1
            if j < n and pattern[j] == "]":
                j += 1
            while j < n and pattern[j] != "]":
                j += 1
            if j >= n:
                res.append("\\[")
                i += 1
            else:
                sub = pattern[i + 1 : j]
                i = j + 1
                if sub.startswith("!"):
                    sub = "^" + sub[1:]
                res.append(f"[{sub}]")
        else:
            res.append(re.escape(c))
            i += 1

    res.append("$")
    return "".join(res)


def match_glob(
    text: str,
    pattern: str,
) -> bool:
    """Return True if text matches glob pattern."""
    regex = glob_to_regex(pattern)
    return bool(re.match(regex, text))


__all__ = [
    "RegexTokenizer",
    "StringScanner",
    "Token",
    "TokenizerError",
    "glob_to_regex",
    "match_glob",
]
