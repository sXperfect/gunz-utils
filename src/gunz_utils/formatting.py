"""Human-readable formatters for byte counts, durations, and large numbers.

Provides three reusable formatters that are stable enough to appear in
log lines, CLI output, and status messages without each consumer
hand-rolling its own convention.
"""
from __future__ import annotations

__author__ = "Yeremia Gunawan Adhisantoso"
__email__ = "yeremiag@gmail.com"
__license__ = "Clear BSD"

# =============================================================================
# STANDARD LIBRARY IMPORTS
# =============================================================================
import math
import os
import re
import sys
from collections.abc import Mapping, Sequence
from decimal import Decimal
from typing import Any, Literal

# =============================================================================
# LOCAL APPLICATION IMPORTS
# =============================================================================
#? Re-export the package version through this module's namespace for
#? backwards-compatible module-level access.
from ._version import __version__ as __version__

__all__ = [
    "escape_terminal",
    "format_bytes",
    "format_count",
    "format_duration",
    "format_hex_dump",
    "format_key_value",
    "format_number",
    "format_percentage",
    "format_progress_bar",
    "format_table",
    "pad_string",
    "parse_bytes",
    "parse_duration",
    "quote_if_needed",
    "strip_ansi_codes",
    "supports_color",
    "visible_width",
]


def _validated_precision(
    precision: int,
) -> int:
    """Validate and return a decimal precision within the supported range.

    Parameters
    ----------
    precision : int
        The precision to validate. Must not be a boolean.

    Returns
    -------
    int
        The validated precision.

    Raises
    ------
    ValueError
        If ``precision`` is a bool, not an integer, or outside ``0..20``.
    """
    if (
        isinstance(precision, bool)
        or not isinstance(precision, int)
        or not 0 <= precision <= 20
    ):
        raise ValueError("precision must be an integer in the range 0..20")
    return precision


def _finite_float(
    value: object,
    *,
    name: str,
) -> float:
    """Coerce a value to a finite float, rejecting booleans and non-finite numbers.

    Parameters
    ----------
    value : object
        The value to coerce.
    name : str
        The parameter name, used in error messages.

    Returns
    -------
    float
        The value converted to a finite float.

    Raises
    ------
    ValueError
        If ``value`` is a bool, not a real number, or not finitely
        representable as a float.
    """
    if isinstance(value, bool) or not isinstance(value, int | float):
        raise ValueError(f"{name} must be a finite real number")
    try:
        result = float(value)
    except OverflowError as exc:
        raise ValueError(f"{name} must be representable as a finite float") from exc
    if not math.isfinite(result):
        raise ValueError(f"{name} must be a finite real number")
    return result


def format_bytes(
    #? --- Input ---
    n: float,
    #? --- Output options ---
    *,
    precision: int = 1,
    binary: bool = False,
) -> str:
    """Format a byte count as a human-readable string.

    Uses SI units by default (KB = 1000 B) so that values match the
    conventions used by storage vendors and network throughput tools.
    Pass ``binary=True`` for IEC units (KiB = 1024 B) when reporting
    RAM or memory-mapped file sizes.

    Parameters
    ----------
    n : float
        Byte count. May be negative; the sign is preserved on output.
    precision : int, optional
        Number of decimal places for scaled values. The unscaled byte
        count is always emitted as an integer, truncating the magnitude toward
        zero while preserving a negative sign. Default is 1.
    binary : bool, optional
        If ``False`` (default), use SI suffixes ``B/KB/MB/GB/TB`` with
        a base of 1000. If ``True``, use IEC suffixes
        ``B/KiB/MiB/GiB/TiB`` with a base of 1024.

    Returns
    -------
    str
        Human-readable byte string such as ``"1.5 KB"`` or ``"1.0 GiB"``.

    Examples
    --------
    >>> format_bytes(0)
    '0 B'
    >>> format_bytes(1536)
    '1.5 KB'
    >>> format_bytes(1024, binary=True)
    '1.0 KiB'
    """
    #? Negative values are formatted by recursing on the magnitude and
    #? prefixing a minus sign, which keeps the scaling logic single-path.
    if not isinstance(binary, bool):
        raise TypeError("binary must be bool")
    precision = _validated_precision(precision)
    n = _finite_float(n, name="n")
    if n < 0:
        return f"-{format_bytes(-n, precision=precision, binary=binary)}"
    base = 1024 if binary else 1000
    #? SI units are uppercase (KB, MB); IEC units use the canonical KiB/MiB
    #? suffix spelling to disambiguate powers of 2 from powers of 10.
    suffixes = (
        ["B", "KiB", "MiB", "GiB", "TiB"] if binary else ["B", "KB", "MB", "GB", "TB"]
    )
    if n < base:
        return f"{int(n)} {suffixes[0]}"
    for idx, suffix in enumerate(suffixes[1:], start=1):
        next_n = n / base
        formatted = f"{next_n:.{precision}f}"
        if float(formatted) < base or idx == len(suffixes) - 1:
            return f"{formatted} {suffix}"
        n = next_n
    return f"{n:.{precision}f} {suffixes[-1]}"


def format_duration(
    seconds: float,
    *,
    precision: int = 1,
) -> str:
    """Format an elapsed duration as a human-readable string.

    Uses adaptive precision: sub-second values render as milliseconds,
    sub-minute values render as fractional seconds, and values of a
    minute or longer render as a ``d/h/m/s`` composite. Composite
    segments always use integer seconds to keep the output stable and
    grep-friendly.

    Parameters
    ----------
    seconds : float
        Elapsed time in seconds. May be negative; the sign is preserved.
    precision : int, optional
        Decimal places for the fractional-seconds branch (sub-minute
        values). Default is 1.

    Returns
    -------
    str
        Human-readable duration such as ``"500ms"``, ``"45.6s"``,
        ``"1m 30s"``, or ``"1d 1h 1m 1s"``.

    Examples
    --------
    >>> format_duration(0)
    '0ms'
    >>> format_duration(0.5)
    '500ms'
    >>> format_duration(3661)
    '1h 1m 1s'
    """
    precision = _validated_precision(precision)
    seconds = _finite_float(seconds, name="seconds")
    if seconds < 0:
        return f"-{format_duration(-seconds, precision=precision)}"
    #? Sub-second values are reported as whole milliseconds to avoid
    #? log lines like "0.0001s" that bury the signal in noise.
    if seconds < 1:
        ms = int(seconds * 1000)
        if ms < 1000:
            return f"{ms}ms"
        seconds = 1.0
    if seconds < 60:
        formatted = f"{seconds:.{precision}f}"
        if float(formatted) < 60:
            return f"{formatted}s"
        seconds = 60.0
    #? Composite segments (minutes and above) drop sub-second precision
    #? via int(): a 90.4s call becomes "1m 30s", which reads better than
    #? "1m 30.4s" in scrollback.
    minutes, s = divmod(int(seconds), 60)
    if minutes < 60:
        return f"{minutes}m {s}s"
    hours, m = divmod(minutes, 60)
    if hours < 24:
        return f"{hours}h {m}m {s}s"
    days, h = divmod(hours, 24)
    return f"{days}d {h}h {m}m {s}s"


def format_count(
    n: int,
    *,
    precision: int = 1,
) -> str:
    """Format a large integer count with K/M/B/T suffixes.

    Follows the SI short-scale convention used by dashboards and
    analytics tools (1K = 1000, 1M = 1e6, 1B = 1e9, 1T = 1e12).
    Values smaller than 1000 in absolute value are rendered as plain
    integers so that small counts are never artificially rounded.

    Parameters
    ----------
    n : int
        Integer count. May be negative; the sign is preserved.
    precision : int, optional
        Decimal places for scaled values. Default is 1.

    Returns
    -------
    str
        Human-readable count such as ``"999"``, ``"1.5K"``, or
        ``"1.2M"``. Values beyond the tera scale remain on the
        ``T`` suffix with whatever magnitude remains.

    Examples
    --------
    >>> format_count(0)
    '0'
    >>> format_count(1500)
    '1.5K'
    >>> format_count(1_234_567)
    '1.2M'
    """
    precision = _validated_precision(precision)
    if isinstance(n, bool) or not isinstance(n, int):
        raise ValueError("n must be an integer")
    if abs(n) < 1000:
        return str(n)
    sign = "-" if n < 0 else ""
    value = Decimal(abs(n))
    suffixes = ["K", "M", "B", "T"]
    for idx, suffix in enumerate(suffixes):
        value /= 1000
        formatted = f"{value:.{precision}f}"
        if Decimal(formatted) < 1000 or idx == len(suffixes) - 1:
            return f"{sign}{formatted}{suffix}"
    return f"{sign}{value:.{precision}f}T"


_DANGEROUS_UNICODE = frozenset(
    {
        "\u202a",
        "\u202b",
        "\u202c",
        "\u202d",
        "\u202e",
        "\u2066",
        "\u2067",
        "\u2068",
        "\u2069",
        "\u200b",
        "\u200c",
        "\u200d",
        "\u200e",
        "\u200f",
        "\ufeff",
    }
)


def escape_terminal(
    text: str,
    *,
    multiline: bool = False,
) -> str:
    """Make untrusted text visible without emitting terminal controls.

    Parameters
    ----------
    text : str
        Source, filename, message, or diff text to display.
    multiline : bool, default=False
        Whether to preserve structural newlines.

    Returns
    -------
    str
        Printable text with controls and invisible Unicode characters escaped.
    """
    if not isinstance(text, str):
        raise TypeError("text must be a string")
    if not isinstance(multiline, bool):
        raise TypeError("multiline must be bool")
    escaped: list[str] = []
    for character in text:
        if character in _DANGEROUS_UNICODE:
            codepoint = ord(character)
            escaped.append(f"\\u{codepoint:04x}")
        elif character.isprintable() or (multiline and character == "\n"):
            escaped.append(character)
        elif character in ("\t", "\n", "\r"):
            escaped.append({"\t": r"\t", "\n": r"\n", "\r": r"\r"}[character])
        else:
            codepoint = ord(character)
            if codepoint <= 0xFF:
                escaped.append(f"\\x{codepoint:02x}")
            elif codepoint <= 0xFFFF:
                escaped.append(f"\\u{codepoint:04x}")
            else:
                escaped.append(f"\\U{codepoint:08x}")
    return "".join(escaped)


def supports_color(
    no_color_flag: bool = False,
    stream: Any = None,
) -> bool:
    """Determine whether ANSI color output should be enabled.

    Follows the NO_COLOR and FORCE_COLOR terminal conventions.

    Parameters
    ----------
    no_color_flag : bool, default=False
        Explicit caller override disabling color.
    stream : Any, optional
        Stream target to check for tty capabilities. Defaults to sys.stdout.

    Returns
    -------
    bool
        True if colored escape sequences should be emitted.
    """
    if not isinstance(no_color_flag, bool):
        raise TypeError("no_color_flag must be bool")
    if no_color_flag:
        return False
    if "NO_COLOR" in os.environ:
        return False
    if os.environ.get("FORCE_COLOR") in ("1", "true"):
        return True
    if os.environ.get("TERM") == "dumb":
        return False
    target = stream if stream is not None else sys.stdout
    return hasattr(target, "isatty") and target.isatty()


def parse_bytes(
    text: str,
) -> int:
    """Parse a human-readable byte count string into an integer number of bytes.

    Supports SI suffixes (B, KB, MB, GB, TB) and IEC suffixes (B, KiB, MiB, GiB, TiB).
    Whitespace between the number and unit is optional.

    Parameters
    ----------
    text : str
        Input string such as ``"1.5 KiB"``, ``"10 MB"``, or ``"512 B"``.

    Returns
    -------
    int
        Exact byte count.
    """
    if not isinstance(text, str):
        raise TypeError("text must be a string")
    cleaned = text.strip()
    if not cleaned:
        raise ValueError("empty byte string")

    multipliers = {
        "b": 1,
        "kb": 1000,
        "mb": 1000**2,
        "gb": 1000**3,
        "tb": 1000**4,
        "kib": 1024,
        "mib": 1024**2,
        "gib": 1024**3,
        "tib": 1024**4,
    }

    sign = 1
    if cleaned.startswith("-"):
        sign = -1
        cleaned = cleaned[1:].strip()
    elif cleaned.startswith("+"):
        cleaned = cleaned[1:].strip()

    idx = 0
    while idx < len(cleaned) and (cleaned[idx].isdigit() or cleaned[idx] == "."):
        idx += 1
    num_part = cleaned[:idx].strip()
    unit_part = cleaned[idx:].strip().lower()

    if not num_part:
        raise ValueError(f"invalid byte string: {text!r}")
    try:
        val = float(num_part)
    except ValueError as exc:
        raise ValueError(f"invalid byte value in: {text!r}") from exc
    if not math.isfinite(val) or val < 0:
        raise ValueError(f"invalid byte number in: {text!r}")

    if not unit_part:
        unit_part = "b"

    if unit_part not in multipliers:
        raise ValueError(f"unrecognized byte suffix: {unit_part!r} in {text!r}")

    return int(sign * round(val * multipliers[unit_part]))


def parse_duration(
    text: str,
) -> float:
    """Parse a human-readable duration string into elapsed seconds (float).

    Supports composite segments (e.g. ``"1h 30m"``, ``"1d 2h 3m 4s"``) and
    sub-second units (``"ms"``, ``"us"``, ``"µs"``, ``"ns"``).

    Parameters
    ----------
    text : str
        Duration string.

    Returns
    -------
    float
        Total seconds as a finite float.
    """
    if not isinstance(text, str):
        raise TypeError("text must be a string")
    cleaned = text.strip()
    if not cleaned:
        raise ValueError("empty duration string")

    sign = 1.0
    if cleaned.startswith("-"):
        sign = -1.0
        cleaned = cleaned[1:].strip()
    elif cleaned.startswith("+"):
        cleaned = cleaned[1:].strip()

    unit_multipliers = {
        "ns": 1e-9,
        "us": 1e-6,
        "µs": 1e-6,
        "ms": 1e-3,
        "s": 1.0,
        "m": 60.0,
        "h": 3600.0,
        "d": 86400.0,
    }

    pattern = re.compile(r"([0-9]+(?:\.[0-9]+)?)\s*([a-zA-Zµ]+)")
    matches = pattern.findall(cleaned)
    if not matches:
        raise ValueError(f"invalid duration format: {text!r}")

    reconstructed = "".join(f"{num}{unit}" for num, unit in matches)
    no_space_clean = re.sub(r"\s+", "", cleaned)
    if reconstructed != no_space_clean:
        raise ValueError(f"unrecognized characters in duration: {text!r}")

    total = 0.0
    for num_str, unit_str in matches:
        u = unit_str.lower()
        if unit_str == "µs":
            u = "µs"
        if u not in unit_multipliers:
            raise ValueError(f"unknown duration unit: {unit_str!r}")
        val = float(num_str)
        if not math.isfinite(val):
            raise ValueError(f"non-finite duration component: {num_str!r}")
        total += val * unit_multipliers[u]

    return sign * total


def format_percentage(
    ratio: float,
    *,
    precision: int = 1,
    signed: bool = False,
) -> str:
    """Format a numeric ratio as a percentage string (e.g. 0.125 -> '12.5%').

    Parameters
    ----------
    ratio : float
        Fractional value (e.g. 0.5 for 50%).
    precision : int, optional
        Decimal places for the percentage. Default is 1.
    signed : bool, optional
        If True, prefix positive values with '+'. Default is False.

    Returns
    -------
    str
        Formatted percentage string.
    """
    precision = _validated_precision(precision)
    if not isinstance(signed, bool):
        raise TypeError("signed must be bool")
    val = _finite_float(ratio, name="ratio")
    pct = val * 100.0
    sign_str = "+" if signed and pct > 0 else ""
    return f"{sign_str}{pct:.{precision}f}%"


def format_table(
    headers: Sequence[str],
    rows: Sequence[Sequence[Any]],
    *,
    alignments: Sequence[Literal["left", "right", "center"]] | None = None,
) -> str:
    """Format headers and tabular rows as an ASCII / Markdown-compatible table.

    Parameters
    ----------
    headers : Sequence[str]
        Column header names.
    rows : Sequence[Sequence[Any]]
        Row data entries.
    alignments : Sequence[Literal["left", "right", "center"]] | None, optional
        Per-column alignment. Defaults to left-aligned.

    Returns
    -------
    str
        Formatted table string.
    """
    if isinstance(headers, (str, bytes, bytearray)):
        raise TypeError("headers must be a sequence of strings, not a string")
    if isinstance(rows, (str, bytes, bytearray)):
        raise TypeError("rows must be a sequence of rows, not a string")

    header_list = [str(h) for h in headers]
    if not header_list:
        raise ValueError("headers must not be empty")

    num_cols = len(header_list)

    if alignments is not None:
        if isinstance(alignments, (str, bytes, bytearray)):
            raise TypeError("alignments must be a sequence of alignment strings")
        align_list = list(alignments)
        if len(align_list) != num_cols:
            raise ValueError(
                f"alignments length ({len(align_list)}) "
                    f"must match column count ({num_cols})"
            )
        for a in align_list:
            if a not in {"left", "right", "center"}:
                raise ValueError(
                    f"invalid alignment: {a!r}; expected left, right, or center"
                )
    else:
        align_list = ["left"] * num_cols

    formatted_rows: list[list[str]] = []
    for row in rows:
        if isinstance(row, (str, bytes, bytearray)):
            raise TypeError("each row must be a sequence of cells, not a string")
        row_cells = [str(c) for c in row]
        if len(row_cells) != num_cols:
            raise ValueError(
                f"row length ({len(row_cells)}) does "
                    f"not match column count ({num_cols})"
            )
        formatted_rows.append(row_cells)

    col_widths = [len(h) for h in header_list]
    for r in formatted_rows:
        for idx, cell in enumerate(r):
            col_widths[idx] = max(col_widths[idx], len(cell))

    def _pad(
        cell: str,
        width: int,
        align: str,
    ) -> str:
        if align == "right":
            return cell.rjust(width)
        if align == "center":
            return cell.center(width)
        return cell.ljust(width)

    header_line = (
        "| "
        + " | ".join(
            _pad(h, w, a)
            for h, w, a in zip(header_list, col_widths, align_list, strict=True)
        )
        + " |"
    )

    sep_parts: list[str] = []
    for w, a in zip(col_widths, align_list, strict=True):
        if a == "right":
            sep_parts.append("-" * max(1, w - 1) + ":")
        elif a == "center":
            sep_parts.append(
                ":" + "-" * max(1, w - 2) + ":" if w >= 2 else ":-:"
            )
        else:
            sep_parts.append("-" * max(1, w))
    sep_line = "| " + " | ".join(sep_parts) + " |"

    row_lines = [
        "| "
        + " | ".join(
            _pad(c, w, a)
            for c, w, a in zip(row, col_widths, align_list, strict=True)
        )
        + " |"
        for row in formatted_rows
    ]

    return "\n".join([header_line, sep_line, *row_lines])


_ANSI_ESCAPE_RE = re.compile(r"\x1B(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~])")


def strip_ansi_codes(
    text: str,
) -> str:
    """Remove ANSI escape sequences from text.

    Parameters
    ----------
    text : str
        Input string possibly containing ANSI codes.

    Returns
    -------
    str
        Cleaned string without ANSI escape sequences.
    """
    if not isinstance(text, str):
        raise TypeError("text must be a str")
    return _ANSI_ESCAPE_RE.sub("", text)


def visible_width(
    text: str,
) -> int:
    """Calculate the visible printable width of a string ignoring ANSI escape sequences.

    Parameters
    ----------
    text : str
        Input string.

    Returns
    -------
    int
        Character width when displayed in a terminal.
    """
    return len(strip_ansi_codes(text))


def pad_string(
    text: str,
    width: int,
    *,
    align: Literal["left", "right", "center"] = "left",
    pad_char: str = " ",
) -> str:
    """Pad string to width taking ANSI escape sequences into account.

    Parameters
    ----------
    text : str
        String to pad.
    width : int
        Target visible column width.
    align : {'left', 'right', 'center'}, default='left'
        Alignment direction.
    pad_char : str, default=' '
        Single padding character.

    Returns
    -------
    str
        Padded string.
    """
    if not isinstance(text, str):
        raise TypeError("text must be a str")
    if not isinstance(pad_char, str) or len(pad_char) != 1:
        raise ValueError("pad_char must be a single character")
    if align not in ("left", "right", "center"):
        raise ValueError(f"invalid alignment: {align!r}")
    vis_w = visible_width(text)
    if vis_w >= width:
        return text
    diff = width - vis_w
    if align == "right":
        return (pad_char * diff) + text
    if align == "center":
        left = diff // 2
        right = diff - left
        return (pad_char * left) + text + (pad_char * right)
    return text + (pad_char * diff)


def format_number(
    n: int | float,
    *,
    precision: int = 2,
    compact: bool = False,
) -> str:
    """Format a number with comma groupings or compact SI suffixes (k, M, B, T).

    Parameters
    ----------
    n : int | float
        Numeric value to format.
    precision : int, default=2
        Decimal places.
    compact : bool, default=False
        If True, use metric suffixes (e.g. 1.23M).

    Returns
    -------
    str
        Formatted number string.
    """
    if isinstance(n, bool) or not isinstance(n, (int, float)):
        raise TypeError("n must be a number")
    if not math.isfinite(float(n)):
        return str(n)
    precision = _validated_precision(precision)
    if not compact:
        if isinstance(n, int):
            return f"{n:,}"
        return f"{n:,.{precision}f}"

    abs_n = abs(float(n))
    sign = "-" if n < 0 else ""
    suffixes = [
        (1e12, "T"),
        (1e9, "B"),
        (1e6, "M"),
        (1e3, "k"),
    ]
    for scale, suffix in suffixes:
        if abs_n >= scale:
            val = abs_n / scale
            return f"{sign}{val:.{precision}f}{suffix}"
    if isinstance(n, int):
        return f"{n}"
    return f"{n:.{precision}f}"


def format_progress_bar(
    progress: float,
    *,
    width: int = 20,
    fill: str = "█",
    empty: str = "░",
) -> str:
    """Format a visual progress bar for a progress value between 0.0 and 1.0.

    Parameters
    ----------
    progress : float
        Ratio between 0.0 and 1.0.
    width : int, default=20
        Total width of the bar in characters.
    fill : str, default='█'
        Character used for the completed portion.
    empty : str, default='░'
        Character used for the remaining portion.

    Returns
    -------
    str
        Formatted progress bar string.
    """
    if isinstance(progress, bool) or not isinstance(progress, (int, float)):
        raise TypeError("progress must be a number")
    if isinstance(width, bool) or not isinstance(width, int) or width < 1:
        raise ValueError("width must be a positive integer")
    clamped = max(0.0, min(1.0, float(progress)))
    filled_len = int(round(clamped * width))
    empty_len = width - filled_len
    return (fill * filled_len) + (empty * empty_len)


def format_key_value(
    pairs: Mapping[str, Any] | Sequence[tuple[str, Any]],
    *,
    separator: str = ": ",
    indent: int = 2,
) -> str:
    """Format structured key-value pairs with aligned separators.

    Parameters
    ----------
    pairs : Mapping[str, Any] | Sequence[tuple[str, Any]]
        Pairs to format.
    separator : str, default=': '
        Delimiter between key and value.
    indent : int, default=2
        Leading indentation spaces.

    Returns
    -------
    str
        Formatted key-value block string.
    """
    if isinstance(pairs, Mapping):
        items = list(pairs.items())
    elif isinstance(pairs, Sequence) and not isinstance(pairs, (str, bytes)):
        items = list(pairs)
    else:
        raise TypeError("pairs must be a Mapping or Sequence of tuples")

    if not items:
        return ""
    max_k_len = max(len(str(k)) for k, _ in items)
    ind = " " * indent
    lines = []
    for k, v in items:
        k_str = str(k).ljust(max_k_len)
        lines.append(f"{ind}{k_str}{separator}{v}")
    return "\n".join(lines)


def format_hex_dump(
    data: bytes | bytearray | memoryview,
    *,
    bytes_per_line: int = 16,
) -> str:
    """Format binary data as a canonical hex dump with offset, hex bytes, and ASCII.

    Parameters
    ----------
    data : bytes | bytearray | memoryview
        Binary buffer.
    bytes_per_line : int, default=16
        Number of bytes displayed per line.

    Returns
    -------
    str
        Formatted hex dump text.
    """
    if not isinstance(data, (bytes, bytearray, memoryview)):
        raise TypeError("data must be bytes-like")
    if isinstance(
    bytes_per_line,
    bool) or not isinstance(
        bytes_per_line,
         int) or bytes_per_line < 1:
        raise ValueError("bytes_per_line must be a positive integer")

    raw = bytes(data)
    if not raw:
        return ""

    lines = []
    for offset in range(0, len(raw), bytes_per_line):
        chunk = raw[offset : offset + bytes_per_line]
        hex_parts = [f"{b:02x}" for b in chunk]
        hex_str = " ".join(hex_parts)
        expected_hex_len = bytes_per_line * 3 - 1
        hex_str = hex_str.ljust(expected_hex_len)
        ascii_parts = [chr(b) if 0x20 <= b <= 0x7E else "." for b in chunk]
        ascii_str = "".join(ascii_parts)
        lines.append(f"{offset:08x}  {hex_str}  |{ascii_str}|")
    return "\n".join(lines)


def quote_if_needed(
    text: str,
) -> str:
    """Wrap string in quotes if it contains whitespace or special delimiter characters.

    Parameters
    ----------
    text : str
        Input string.

    Returns
    -------
    str
        Quoted or original string.
    """
    if not isinstance(text, str):
        raise TypeError("text must be a str")
    if not text:
        return '""'
    if any(c in text for c in ' \t\n\r"\'=;,|'):
        escaped = text.replace('"', '\\"')
        return f'"{escaped}"'
    return text


