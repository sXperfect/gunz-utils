# =============================================================================
# STANDARD LIBRARY IMPORTS
# =============================================================================

import unittest

# isort: split
# =============================================================================
# LOCAL APPLICATION IMPORTS
# =============================================================================

from gunz_utils.formatting import (
    escape_terminal,
    format_bytes,
    format_count,
    format_duration,
    supports_color,
)


class TestFormatBytes(unittest.TestCase):
    def test_zero(self):
        self.assertEqual(format_bytes(0), "0 B")

    def test_sub_kilobyte(self):
        self.assertEqual(format_bytes(512), "512 B")

    def test_exact_kilobyte_si(self):
        self.assertEqual(format_bytes(1024), "1.0 KB")

    def test_fractional_kilobyte(self):
        self.assertEqual(format_bytes(1536), "1.5 KB")

    def test_megabyte(self):
        self.assertEqual(format_bytes(1024 * 1024), "1.0 MB")

    def test_gigabyte(self):
        self.assertEqual(format_bytes(1_000_000_000), "1.0 GB")

    def test_terabyte(self):
        self.assertEqual(format_bytes(1_000_000_000_000), "1.0 TB")

    def test_precision_zero(self):
        self.assertEqual(format_bytes(1536, precision=0), "2 KB")

    def test_precision_two(self):
        self.assertEqual(format_bytes(1500, precision=2), "1.50 KB")

    def test_binary_kibibyte(self):
        self.assertEqual(format_bytes(1024, binary=True), "1.0 KiB")

    def test_binary_gibibyte(self):
        self.assertEqual(format_bytes(2**30, binary=True), "1.0 GiB")

    def test_negative(self):
        self.assertEqual(format_bytes(-1536), "-1.5 KB")

    def test_negative_binary(self):
        self.assertEqual(format_bytes(-2048, binary=True), "-2.0 KiB")


class TestFormatDuration(unittest.TestCase):
    def test_zero(self):
        self.assertEqual(format_duration(0), "0ms")

    def test_sub_second(self):
        self.assertEqual(format_duration(0.5), "500ms")

    def test_sub_second_small(self):
        self.assertEqual(format_duration(0.001), "1ms")

    def test_seconds(self):
        self.assertEqual(format_duration(30), "30.0s")

    def test_seconds_fractional(self):
        self.assertEqual(format_duration(45.6), "45.6s")

    def test_minutes_seconds(self):
        self.assertEqual(format_duration(90), "1m 30s")

    def test_hours_minutes_seconds(self):
        self.assertEqual(format_duration(3661), "1h 1m 1s")

    def test_day_composite(self):
        self.assertEqual(format_duration(86400), "1d 0h 0m 0s")

    def test_multi_day_composite(self):
        self.assertEqual(format_duration(90061), "1d 1h 1m 1s")

    def test_precision_zero(self):
        self.assertEqual(format_duration(45.6, precision=0), "46s")

    def test_negative(self):
        self.assertEqual(format_duration(-30), "-30.0s")

    def test_negative_sub_second(self):
        self.assertEqual(format_duration(-0.5), "-500ms")


class TestFormatCount(unittest.TestCase):
    def test_zero(self):
        self.assertEqual(format_count(0), "0")

    def test_sub_thousand(self):
        self.assertEqual(format_count(999), "999")

    def test_exact_thousand(self):
        self.assertEqual(format_count(1000), "1.0K")

    def test_fractional_thousand(self):
        self.assertEqual(format_count(1500), "1.5K")

    def test_million(self):
        self.assertEqual(format_count(1_000_000), "1.0M")

    def test_million_fractional(self):
        self.assertEqual(format_count(1_234_567), "1.2M")

    def test_billion(self):
        self.assertEqual(format_count(1_000_000_000), "1.0B")

    def test_precision_zero(self):
        self.assertEqual(format_count(1234, precision=0), "1K")

    def test_negative(self):
        self.assertEqual(format_count(-1500), "-1.5K")

    def test_negative_small(self):
        self.assertEqual(format_count(-999), "-999")


class TestEscapeTerminal(unittest.TestCase):
    def test_printable_text_untouched(self) -> None:
        self.assertEqual(escape_terminal("hello world! 123"), "hello world! 123")

    def test_escapes_tabs_and_newlines(self) -> None:
        self.assertEqual(escape_terminal("a\tb\nc\r"), r"a\tb\nc\r")

    def test_multiline_preserves_newline(self) -> None:
        self.assertEqual(escape_terminal("a\nb\n", multiline=True), "a\nb\n")

    def test_escapes_ansi_and_control_chars(self) -> None:
        self.assertEqual(escape_terminal("\x1b[31mred\x1b[0m"), r"\x1b[31mred\x1b[0m")
        self.assertEqual(escape_terminal("\x00\x07"), r"\x00\x07")

    def test_escapes_bidi_controls(self) -> None:
        self.assertEqual(escape_terminal("\u202eRTL"), r"\u202eRTL")


class TestSupportsColor(unittest.TestCase):
    def test_no_color_flag_overrides_everything(self) -> None:
        import os
        from unittest.mock import patch

        with patch.dict(os.environ, {"FORCE_COLOR": "1"}):
            self.assertFalse(supports_color(no_color_flag=True))

    def test_no_color_env_var(self) -> None:
        import os
        from unittest.mock import patch

        with patch.dict(os.environ, {"NO_COLOR": "1", "FORCE_COLOR": "1"}):
            self.assertFalse(supports_color())

    def test_force_color_env_var(self) -> None:
        import os
        from unittest.mock import patch

        env = dict(os.environ)
        env.pop("NO_COLOR", None)
        env["FORCE_COLOR"] = "1"
        with patch.dict(os.environ, env, clear=True):
            self.assertTrue(supports_color())


if __name__ == "__main__":
    unittest.main()

