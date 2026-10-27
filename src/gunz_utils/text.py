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
from collections.abc import Iterable, Sequence

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

    Returns
    -------
    re.Pattern[str]
        A compiled case-insensitive pattern.
    """
    words = term.split(" ")
    tail = words[-1]
    head = " ".join(words[:-1])

    if head:
        head_pattern = _SEPARATOR.join(re.escape(word) for word in head.split(" "))
        pattern = (
            rf"(?<!\w){head_pattern}{_SEPARATOR}{re.escape(tail)}"
            rf"{_SUFFIXES}(?!\w)"
        )
    else:
        pattern = rf"(?<!\w){re.escape(tail)}{_SUFFIXES}(?!\w)"

    return re.compile(pattern, re.IGNORECASE)


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
    chars = list(text)
    for pattern in patterns:
        for match in pattern.finditer(text):
            for index in range(match.start(), min(match.end(), len(chars))):
                if chars[index] != "\n":
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
    ordered = sorted(
        candidates,
        key=lambda item: (item[0], -(item[1] - item[0]), str(item[2])),
    )
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

    return kept


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
    "deduplicate_spans",
    "strip_problematic_chars",
    "word_pattern",
]
