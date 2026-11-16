"""Tests for Wave 5 Sub-Wave 2: Formatting & Visualization (#14–#26)."""
# =============================================================================
# STANDARD LIBRARY IMPORTS
# =============================================================================

from __future__ import annotations

# =============================================================================
# LOCAL APPLICATION IMPORTS
# =============================================================================
from gunz_utils.formatting import (
    format_duration,
    format_hex_dump,
    format_key_value,
    format_number,
    format_percentage,
    format_progress_bar,
    format_table,
    pad_string,
    parse_duration,
    quote_if_needed,
    strip_ansi_codes,
    visible_width,
)


def test_format_duration_and_parse_duration():
    assert format_duration(3665.0) == "1h 1m 5s"
    assert format_duration(45.0) == "45.0s"

    assert parse_duration("1h 1m 5s") == 3665.0
    assert parse_duration("500ms") == 0.5


def test_format_number():
    #? Comma separation
    assert format_number(1234567) == "1,234,567"
    assert format_number(1234.567, precision=2) == "1,234.57"

    #? Compact SI
    assert format_number(1500, compact=True) == "1.50k"
    assert format_number(2500000, compact=True) == "2.50M"
    assert format_number(3200000000, compact=True) == "3.20B"
    assert format_number(42, compact=True) == "42"


def test_format_percentage():
    assert format_percentage(0.754) == "75.4%"
    assert format_percentage(0.5, precision=0) == "50%"
    assert format_percentage(0.12, signed=True) == "+12.0%"


def test_format_table():
    headers = ["Name", "Score", "Rank"]
    rows = [["Alice", 98, 1], ["Bob", 84, 2]]
    table = format_table(headers, rows, alignments=["left", "right", "center"])
    assert "| Name" in table
    assert "| Alice" in table
    assert "| Bob" in table
    assert ":--:" in table  #? Markdown center indicator


def test_format_key_value():
    data = {"Status": "OK", "Response Time": "12ms", "Errors": 0}
    formatted = format_key_value(data)
    lines = formatted.split("\n")
    assert len(lines) == 3
    #? Check alignment
    assert "Status       : OK" in lines[0]
    assert "Response Time: 12ms" in lines[1]


def test_format_progress_bar():
    bar_half = format_progress_bar(0.5, width=10, fill="=", empty="-")
    assert bar_half == "=====" + "-----"

    bar_full = format_progress_bar(1.0, width=10, fill="=", empty="-")
    assert bar_full == "=========="

    bar_empty = format_progress_bar(0.0, width=10, fill="=", empty="-")
    assert bar_empty == "----------"


def test_format_hex_dump():
    data = b"Hello, World!\x00\x01\x02"
    dump = format_hex_dump(data, bytes_per_line=16)
    assert dump.startswith("00000000  48 65 6c 6c 6f 2c 20 57 6f 72 6c 64 21 00 01 02")
    assert "|Hello, World!..." in dump


def test_strip_ansi_codes_and_visible_width():
    colored = "\x1b[31mRed Alert\x1b[0m"
    assert strip_ansi_codes(colored) == "Red Alert"
    assert visible_width(colored) == 9  #? len("Red Alert")


def test_pad_string():
    colored = "\x1b[32mSuccess\x1b[0m"  #? Visible len 7
    #? Left align
    padded_left = pad_string(colored, 10, align="left")
    assert visible_width(padded_left) == 10
    assert padded_left.endswith("   ")

    #? Right align
    padded_right = pad_string(colored, 10, align="right")
    assert visible_width(padded_right) == 10
    assert padded_right.startswith("   ")


def test_quote_if_needed():
    assert quote_if_needed("simple") == "simple"
    assert quote_if_needed("with space") == '"with space"'
    assert quote_if_needed("key=val") == '"key=val"'
    assert quote_if_needed("") == '""'
