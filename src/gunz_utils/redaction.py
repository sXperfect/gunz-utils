"""Secret masking utilities for safe logging and display.

Provides functions to partially mask credential values (API keys, tokens,
passwords) so they can be safely printed, logged, or included in error
reports without leaking the underlying secret. The two main entry points
are :func:`redact` for masking a single value and :func:`redact_dict` for
recursively walking a nested configuration structure and masking only the
values whose keys match a known secret pattern.
"""

from __future__ import annotations

__author__ = "Yeremia Gunawan Adhisantoso"
__email__ = "adhisant@tnt.uni-hannover.de"
__license__ = "BSD 3-Clause"
__version__ = "1.6.0"

__all__ = ["redact", "redact_dict", "SECRET_PATTERNS"]

# ? Case-insensitive substring match against dict keys. A frozenset is used
# ? so membership tests are O(1) and the collection itself is immutable
# ? and hashable, preventing accidental mutation at runtime.
SECRET_PATTERNS: frozenset[str] = frozenset(
    {
        "password",
        "passwd",
        "secret",
        "token",
        "api_key",
        "apikey",
        "access_key",
        "secret_key",
        "auth",
        "authorization",
        "credential",
        "credentials",
        "private_key",
        "session_token",
        "refresh_token",
    }
)

# ? Single canonical mask string. Reusing one constant avoids accidental
# ? format drift across callers (e.g. mixing '*' and '•' in log output)
# ? and keeps the redaction footprint short in tight log lines.
_MASK = "****"


def redact(value: object, *, show_chars: int = 2) -> object:
    """Mask a string value, preserving ``show_chars`` characters on each end.

    The default ``show_chars=2`` exposes only a small prefix/suffix while
    hiding the bulk of the secret; for very short strings this would
    reveal too much, so values whose length is ``<= 2 * show_chars`` are
    fully masked instead.

    Parameters
    ----------
    value : object
        The value to mask. Non-string inputs are returned unchanged so
        callers can pass arbitrary config dicts through without
        pre-filtering.
    show_chars : int, optional
        Number of characters to leave visible at the start and the end
        of the string. Must be non-negative. Defaults to ``2``.

    Returns
    -------
    object
        Either the masked string (same length preserved) or the
        original value if it was not a string.

    Examples
    --------
    >>> redact("hunter2")
    'h****2'
    >>> redact("hunter2", show_chars=4)
    'hunte****er2'
    >>> redact("hi")
    '****'
    >>> redact(12345)
    12345
    """
    if not isinstance(value, str):
        return value
    # ? Strings at or below the "reveal both ends" threshold contain
    # ? almost no hidden material, so we collapse them to the full mask
    # ? rather than exposing prefix == suffix.
    if len(value) <= 2 * show_chars:
        return _MASK
    return f"{value[:show_chars]}{_MASK}{value[-show_chars:]}"


def _is_secret_key(key: object, patterns: frozenset[str]) -> bool:
    """Return True if ``key`` (case-insensitively) contains any pattern.

    Parameters
    ----------
    key : object
        The dict key to inspect. Non-string keys (e.g. ``int``) are
        treated as non-secret.
    patterns : frozenset[str]
        Lower-case substrings to look for inside the key name.

    Returns
    -------
    bool
        ``True`` when at least one pattern appears in the lower-cased
        key, otherwise ``False``.
    """
    if not isinstance(key, str):
        return False
    # ? Substring (rather than equality) match means a key like
    # ? "user_password_hash" or "DB_PASSWORD" is still caught without
    # ? enumerating every camelCase / snake_case permutation.
    key_lower = key.lower()
    return any(pattern in key_lower for pattern in patterns)


def redact_dict(
    d: object,
    *,
    patterns: frozenset[str] | None = None,
    show_chars: int = 2,
) -> object:
    """Recursively mask string values whose keys match secret patterns.

    Dicts are walked key by key; for each key that matches ``patterns``
    the associated value is passed through :func:`redact`, otherwise
    the value is recursed into so nested dicts and lists are handled.
    Lists are walked element by element. Anything that is neither a
    ``dict`` nor a ``list`` is returned unchanged.

    Parameters
    ----------
    d : object
        The structure to redact. Typically a ``dict``; scalars and other
        non-collection types are returned as-is.
    patterns : frozenset[str] | None, optional
        Substring patterns used by :func:`_is_secret_key`. When ``None``
        (the default) the module-level :data:`SECRET_PATTERNS` is used.
    show_chars : int, optional
        Forwarded to :func:`redact` for every masked leaf value.

    Returns
    -------
    object
        A new structure with the same shape as ``d`` but with secret
        leaves masked. The input ``d`` is not mutated.
    """
    if patterns is None:
        patterns = SECRET_PATTERNS
    if isinstance(d, dict):
        return {
            key: (
                redact(value, show_chars=show_chars)
                if _is_secret_key(key, patterns) and isinstance(value, str)
                else redact_dict(value, patterns=patterns, show_chars=show_chars)
            )
            for key, value in d.items()
        }
    if isinstance(d, list):
        return [
            redact_dict(item, patterns=patterns, show_chars=show_chars) for item in d
        ]
    return d
