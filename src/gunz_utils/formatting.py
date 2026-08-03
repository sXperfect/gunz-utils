"""Human-readable formatters for byte counts, durations, and large numbers.

Provides three reusable formatters that are stable enough to appear in
log lines, CLI output, and status messages without each consumer
hand-rolling its own convention.
"""

from __future__ import annotations

__author__ = "Yeremia Gunawan Adhisantoso"
__email__ = "adhisant@tnt.uni-hannover.de"
__license__ = "BSD 3-Clause"
__version__ = "1.6.0"

__all__ = ["format_bytes", "format_duration", "format_count"]


def format_bytes(
    n: float,
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
        count is always emitted as an integer. Default is 1.
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
    n = float(n)
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
    for _i, suffix in enumerate(suffixes[1:], start=1):
        n /= base
        if n < base:
            return f"{n:.{precision}f} {suffix}"
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
    '0s'
    >>> format_duration(0.5)
    '500ms'
    >>> format_duration(3661)
    '1h 1m 1s'
    """
    seconds = float(seconds)
    if seconds < 0:
        return f"-{format_duration(-seconds, precision=precision)}"
    #? Sub-second values are reported as whole milliseconds to avoid
    #? log lines like "0.0001s" that bury the signal in noise.
    if seconds < 1:
        return f"{int(seconds * 1000)}ms"
    if seconds < 60:
        return f"{seconds:.{precision}f}s"
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
    n = int(n)
    if abs(n) < 1000:
        return str(n)
    sign = "-" if n < 0 else ""
    value = float(abs(n))
    for suffix in ["K", "M", "B", "T"]:
        value /= 1000
        if value < 1000:
            return f"{sign}{value:.{precision}f}{suffix}"
    return f"{sign}{value:.{precision}f}T"
