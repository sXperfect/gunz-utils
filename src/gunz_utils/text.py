"""Text-matching and sanitization primitives.

Dependency-free helpers for matching prose against word lists and for cleaning
text of problematic characters. They are shared by the language-analysis and
manuscript tooling in the Gunz ecosystem so that a term list, an inflection
rule, or a sanitization policy is defined in one place.

The matchers are *word-boundary* and *inflection-tolerant*: ``word_pattern``
accepts a trailing plural/inflection on a single-word term and tolerates a
space or hyphen within a multi-word term, so one configured term covers
``refactor``/``refactored`` and ``sanity check``/``sanity-check``.
"""

from __future__ import annotations

__author__ = "Yeremia Gunawan Adhisantoso"
__email__ = "yeremiag@gmail.com"
__license__ = "Clear BSD"

# =============================================================================
# STANDARD LIBRARY IMPORTS
# =============================================================================
import re
from collections.abc import Callable, Iterable, Sequence

# =============================================================================
# CONSTANTS
# =============================================================================
#? Tolerated inflection on the final word of a term.
_SUFFIXES: str = r"(?:s|es|ies|ed|ing|d)?"
#? A word separator within a multi-word term (space or any hyphen).
_SEPARATOR: str = r"[-\u2010\u2011 ]"

# =============================================================================
# PUBLIC API
# =============================================================================
def word_pattern(
    term: str,
    flags: int = re.IGNORECASE,
) -> re.Pattern[str]:
    """Build a case-insensitive, inflection-tolerant word pattern for a term.

    A trailing plural or inflection is tolerated on the final word of the term,
    so that ``refactor`` also matches ``refactored`` and ``refactoring`` while
    ``sanity check`` also matches ``sanity checks``. Word boundaries within a
    multi-word term accept a space or a hyphen, so one term covers both
    ``sanity check`` and ``sanity-check``.

    Parameters
    ----------
    term : str
        The phrase to match.
    flags : int, default=re.IGNORECASE
        Regex compilation flags.

    Returns
    -------
    re.Pattern[str]
        A compiled pattern.
    """
    if not isinstance(term, str):
        raise TypeError("term must be a str")
    if not term.strip():
        raise ValueError("term must be a non-empty string")
    if isinstance(flags, bool) or not isinstance(flags, int):
        raise TypeError("flags must be an integer")

    words = [w for w in re.split(r"\s+", term.strip()) if w]
    tail = words[-1]
    head = " ".join(words[:-1])

    if tail.endswith("y") and len(tail) > 1 and tail[-2].lower() not in "aeiou":
        stem = tail[:-1]
        tail_pattern = rf"(?:{re.escape(tail)}(?:s|ed|ing)?|{re.escape(stem)}ies)"
    elif tail.endswith("e") and len(tail) > 1:
        stem = tail[:-1]
        tail_pattern = rf"(?:{re.escape(tail)}(?:s|d)?|{re.escape(stem)}(?:ed|ing|es)?)"
    else:
        tail_pattern = rf"{re.escape(tail)}{_SUFFIXES}"

    if head:
        head_pattern = _SEPARATOR.join(re.escape(word) for word in head.split(" "))
        pattern = (
            rf"(?<!\w){head_pattern}{_SEPARATOR}{tail_pattern}(?!\w)"
        )
    else:
        pattern = rf"(?<!\w){tail_pattern}(?!\w)"

    return re.compile(pattern, flags)


def blank_spans(
    text: str,
    patterns: Sequence[re.Pattern[str]],
) -> str:
    """Return ``text`` with every span matched by any ``patterns`` blanked.

    Blanked characters are replaced with spaces (preserving length and offset)
    so that positions of the remaining text are unchanged. Newlines are kept.

    Parameters
    ----------
    text : str
        Text to blank.
    patterns : Sequence[re.Pattern[str]]
        Compiled patterns whose matches are blanked.

    Returns
    -------
    str
        The masked text.
    """
    if not isinstance(text, str):
        raise TypeError("text must be a str")
    if isinstance(patterns, (str, bytes, bytearray)):
        raise TypeError("patterns must be a sequence of patterns, not string or bytes")
    chars = list(text)
    for pattern in patterns:
        for match in pattern.finditer(text):
            for index in range(match.start(), min(match.end(), len(chars))):
                if chars[index] not in ("\n", "\r"):
                    chars[index] = " "
    return "".join(chars)


def deduplicate_spans(
    candidates: Iterable[tuple[int, int, object]],
) -> list[tuple[int, int, object]]:
    """Select non-overlapping spans, preferring the longest match.

    Overlapping candidates are resolved by keeping the longest span first,
    then spans in position order; any candidate overlapping an already kept
    span is dropped. Useful when several word lists can match the same text.

    Parameters
    ----------
    candidates : Iterable[tuple[int, int, object]]
        ``(start, end, payload)`` spans, where ``payload`` is preserved.

    Returns
    -------
    list[tuple[int, int, object]]
        Non-overlapping spans, ordered by position.
    """
    ordered = []
    for item in candidates:
        if len(item) != 3:
            raise ValueError("each candidate span must be a 3-tuple (start, end, payload)")
        start, end, payload = item
        if isinstance(start, bool) or not isinstance(start, int) or start < 0:
            raise ValueError("span start must be a non-negative integer")
        if isinstance(end, bool) or not isinstance(end, int) or end < start:
            raise ValueError("span end must be an integer >= start")
        ordered.append((start, end, payload))

    ordered.sort(key=lambda item: (-(item[1] - item[0]), item[0], str(item[2])))
    kept: list[tuple[int, int, object]] = []
    occupied: list[tuple[int, int]] = []

    for start, end, payload in ordered:
        if any(
            start < span_end and end > span_start
            for span_start, span_end in occupied
        ):
            continue
        occupied.append((start, end))
        kept.append((start, end, payload))

    kept.sort(key=lambda item: (item[0], item[1]))
    return kept


def truncate(
    text: str,
    max_length: int,
    *,
    suffix: str = "...",
    word_boundary: bool = False,
) -> str:
    """Truncate text to max_length, optionally respecting word boundaries.

    Parameters
    ----------
    text : str
        Input string.
    max_length : int
        Maximum allowed string length.
    suffix : str, default="..."
        Suffix to append when truncating.
    word_boundary : bool, default=False
        Whether to break only on word boundaries.

    Returns
    -------
    str
        Truncated or unmodified string.
    """
    if not isinstance(text, str):
        raise TypeError("text must be a str")
    if isinstance(max_length, bool) or not isinstance(max_length, int) or max_length < 0:
        raise ValueError("max_length must be a non-negative integer")
    if not isinstance(suffix, str):
        raise TypeError("suffix must be a str")
    if len(text) <= max_length:
        return text
    if max_length <= len(suffix):
        return suffix[:max_length]

    target_len = max_length - len(suffix)
    if not word_boundary:
        return text[:target_len] + suffix

    cut = text[:target_len + 1]
    last_space = cut.rfind(" ")
    if last_space > 0:
        return text[:last_space].rstrip() + suffix
    return text[:target_len] + suffix


def truncate_text(
    text: str,
    max_length: int,
    *,
    suffix: str = "...",
) -> str:
    """Truncate text to max_length, appending suffix if truncated. Alias for truncate."""
    return truncate(text, max_length, suffix=suffix, word_boundary=False)


def slugify(
    text: str,
    *,
    separator: str = "-",
    lowercase: bool = True,
) -> str:
    """Convert arbitrary text into a URL-friendly slug.

    Parameters
    ----------
    text : str
        Input text.
    separator : str, default="-"
        Delimiter between slug segments.
    lowercase : bool, default=True
        Whether to convert text to lowercase.

    Returns
    -------
    str
        Cleaned slug string.
    """
    if not isinstance(text, str):
        raise TypeError("text must be a str")
    if not isinstance(separator, str):
        raise TypeError("separator must be a str")
    s = text.strip()
    if lowercase:
        s = s.lower()
    cleaned = re.sub(r"[^\w\s-]", "", s)
    slug = re.sub(r"[-\s]+", separator, cleaned).strip(separator)
    return slug


def levenshtein_distance(
    a: str,
    b: str,
    *,
    max_distance: int | None = None,
) -> int:
    """Calculate the Levenshtein distance between two strings.

    Parameters
    ----------
    a, b : str
        Strings to compare.
    max_distance : int | None, optional
        Maximum distance threshold; returns max_distance + 1 early if exceeded.
    """
    if not isinstance(a, str) or not isinstance(b, str):
        raise TypeError("inputs must be strings")
    if max_distance is not None:
        if isinstance(max_distance, bool) or not isinstance(max_distance, int) or max_distance < 0:
            raise ValueError("max_distance must be a non-negative integer or None")

    if a == b:
        return 0
    if not a:
        d = len(b)
        return min(d, max_distance + 1) if max_distance is not None else d
    if not b:
        d = len(a)
        return min(d, max_distance + 1) if max_distance is not None else d

    if len(a) > len(b):
        a, b = b, a

    if max_distance is not None and len(b) - len(a) > max_distance:
        return max_distance + 1

    prev = list(range(len(a) + 1))
    for j, ch_b in enumerate(b, 1):
        curr = [j] * (len(a) + 1)
        for i, ch_a in enumerate(a, 1):
            cost = 0 if ch_a == ch_b else 1
            curr[i] = min(
                curr[i - 1] + 1,
                prev[i] + 1,
                prev[i - 1] + cost,
            )
        if max_distance is not None and min(curr) > max_distance:
            return max_distance + 1
        prev = curr

    res = prev[len(a)]
    if max_distance is not None and res > max_distance:
        return max_distance + 1
    return res


def damerau_levenshtein_distance(
    a: str,
    b: str,
) -> int:
    """Calculate Damerau-Levenshtein distance with adjacent transpositions."""
    if not isinstance(a, str) or not isinstance(b, str):
        raise TypeError("inputs must be strings")
    if a == b:
        return 0
    len_a, len_b = len(a), len(b)
    if len_a == 0:
        return len_b
    if len_b == 0:
        return len_a

    d = [[0] * (len_b + 2) for _ in range(len_a + 2)]
    max_dist = len_a + len_b
    d[0][0] = max_dist

    for i in range(len_a + 1):
        d[i + 1][0] = max_dist
        d[i + 1][1] = i
    for j in range(len_b + 1):
        d[0][j + 1] = max_dist
        d[1][j + 1] = j

    da: dict[str, int] = {}
    for i in range(1, len_a + 1):
        db = 0
        for j in range(1, len_b + 1):
            k = da.get(b[j - 1], 0)
            l = db
            cost = 0 if a[i - 1] == b[j - 1] else 1
            if cost == 0:
                db = j

            d[i + 1][j + 1] = min(
                d[i][j + 1] + 1,
                d[i + 1][j] + 1,
                d[i][j] + cost,
                d[k][l] + (i - k - 1) + 1 + (j - l - 1),
            )
        da[a[i - 1]] = i

    return d[len_a + 1][len_b + 1]


def jaro_winkler_similarity(
    a: str,
    b: str,
    *,
    prefix_weight: float = 0.1,
) -> float:
    """Calculate the Jaro-Winkler string similarity in range [0.0, 1.0]."""
    if not isinstance(a, str) or not isinstance(b, str):
        raise TypeError("inputs must be strings")
    if (
        isinstance(prefix_weight, bool)
        or not isinstance(prefix_weight, (int, float))
        or not (0.0 <= prefix_weight <= 0.25)
    ):
        raise ValueError("prefix_weight must be a float between 0.0 and 0.25")

    if a == b:
        return 1.0
    len_a, len_b = len(a), len(b)
    if len_a == 0 or len_b == 0:
        return 0.0

    match_distance = (max(len_a, len_b) // 2) - 1
    if match_distance < 0:
        match_distance = 0

    a_matches = [False] * len_a
    b_matches = [False] * len_b
    matches = 0

    for i in range(len_a):
        start = max(0, i - match_distance)
        end = min(i + match_distance + 1, len_b)
        for j in range(start, end):
            if b_matches[j] or a[i] != b[j]:
                continue
            a_matches[i] = True
            b_matches[j] = True
            matches += 1
            break

    if matches == 0:
        return 0.0

    k = 0
    transpositions = 0
    for i in range(len_a):
        if not a_matches[i]:
            continue
        while not b_matches[k]:
            k += 1
        if a[i] != b[k]:
            transpositions += 1
        k += 1

    jaro = (
        (matches / len_a) +
        (matches / len_b) +
        ((matches - transpositions / 2) / matches)
    ) / 3.0

    prefix_len = 0
    for i in range(min(4, len_a, len_b)):
        if a[i] == b[i]:
            prefix_len += 1
        else:
            break

    return jaro + (prefix_len * prefix_weight * (1.0 - jaro))


def hamming_distance(
    a: str | bytes,
    b: str | bytes,
) -> int:
    """Calculate the Hamming distance between two equal-length strings or byte sequences."""
    if not isinstance(a, (str, bytes)) or not isinstance(b, (str, bytes)):
        raise TypeError("inputs must be both strings or both bytes")
    if type(a) is not type(b):
        raise TypeError("inputs must have the same type")
    if len(a) != len(b):
        raise ValueError(f"inputs must be of equal length (got {len(a)} and {len(b)})")
    return sum(ch1 != ch2 for ch1, ch2 in zip(a, b, strict=True))


def word_wrap(
    text: str,
    width: int = 70,
    *,
    indent: str = "",
    subsequent_indent: str = "",
) -> str:
    """Wrap text to specified line width preserving paragraph breaks."""
    if not isinstance(text, str):
        raise TypeError("text must be a str")
    if isinstance(width, bool) or not isinstance(width, int) or width < 1:
        raise ValueError("width must be a positive integer")

    import textwrap
    lines = []
    paragraphs = text.split("\n")
    for i, p in enumerate(paragraphs):
        ind = indent if i == 0 else subsequent_indent
        wrapped = textwrap.fill(
            p,
            width=width,
            initial_indent=ind,
            subsequent_indent=subsequent_indent,
            break_long_words=True,
        )
        lines.append(wrapped)
    return "\n".join(lines)


def indent_block(
    text: str,
    prefix: str = "    ",
    *,
    predicate: Callable[[str], bool] | None = None,
) -> str:
    """Indent lines in text with a prefix string."""
    if not isinstance(text, str):
        raise TypeError("text must be a str")
    if not isinstance(prefix, str):
        raise TypeError("prefix must be a str")
    cond = predicate if predicate is not None else (lambda line: bool(line.strip()))
    return "".join(
        (prefix + line if cond(line) else line)
        for line in text.splitlines(keepends=True)
    )


def dedent_block(
    text: str,
) -> str:
    """Remove any common leading whitespace from every line in text."""
    if not isinstance(text, str):
        raise TypeError("text must be a str")
    import textwrap
    return textwrap.dedent(text)


def camel_to_snake(
    s: str,
) -> str:
    """Convert camelCase or PascalCase string to snake_case."""
    if not isinstance(s, str):
        raise TypeError("input must be a string")
    s1 = re.sub(r"([A-Z]+)([A-Z][a-z])", r"\1_\2", s)
    s2 = re.sub(r"([a-z\d])([A-Z])", r"\1_\2", s1)
    return s2.lower()


def snake_to_camel(
    s: str,
    *,
    capitalize_first: bool = False,
) -> str:
    """Convert snake_case string to camelCase or PascalCase."""
    if not isinstance(s, str):
        raise TypeError("input must be a string")
    parts = s.split("_")
    non_empty = [p for p in parts if p]
    if not non_empty:
        return ""
    result = "".join(word.capitalize() for word in non_empty)
    if not capitalize_first:
        result = result[0].lower() + result[1:]
    return result


_MINOR_WORDS = frozenset({
    "a", "an", "and", "as", "at", "but", "by", "for", "in",
    "nor", "of", "on", "or", "so", "the", "to", "up", "yet"
})


def title_case(
    s: str,
) -> str:
    """Convert string to Title Case respecting common minor words."""
    if not isinstance(s, str):
        raise TypeError("input must be a string")
    words = s.split()
    if not words:
        return ""
    res = []
    for i, w in enumerate(words):
        lw = w.lower()
        if i == 0 or i == len(words) - 1 or lw not in _MINOR_WORDS:
            res.append(w.capitalize())
        else:
            res.append(lw)
    return " ".join(res)


def strip_problematic_chars(
    text: str,
) -> str:
    """Strip characters that break text pipelines after copy-paste.

    Replaces U+2010 (HYPHEN) and U+2011 (NON-BREAKING HYPHEN) with an ASCII
    hyphen and drops U+0016 (SYN, an ASCII control char), which commonly
    appear after copy-paste from word processors or PDF extraction.

    Parameters
    ----------
    text : str
        Text to clean.

    Returns
    -------
    str
        The cleaned text.
    """
    return text.replace("\u2010", "-").replace("\u2011", "-").replace("\x16", "")


__all__ = [
    "blank_spans",
    "camel_to_snake",
    "damerau_levenshtein_distance",
    "dedent_block",
    "deduplicate_spans",
    "hamming_distance",
    "indent_block",
    "jaro_winkler_similarity",
    "levenshtein_distance",
    "slugify",
    "snake_to_camel",
    "strip_problematic_chars",
    "title_case",
    "truncate",
    "truncate_text",
    "word_pattern",
    "word_wrap",
]
