"""Tests for ``gunz_utils.redaction`` secret-masking helpers."""

from __future__ import annotations

import unittest

from gunz_utils import SECRET_PATTERNS, redact, redact_dict
from gunz_utils.redaction import _is_secret_key


class TestRedact(unittest.TestCase):
    """Behaviour of the single-value :func:`redact` helper."""

    def test_long_string_shows_first_and_last_two_chars(self):
        """A long string keeps ``show_chars`` on each side of the mask.

        With the default ``show_chars=2`` a 7-character string keeps the
        first two and last two characters, hiding the middle three.
        """
        self.assertEqual(redact("hunter2"), "hu****r2")
        # 'sk-1234567890abcdef' has length 18 -> prefix 'sk', suffix 'ef'.
        self.assertEqual(redact("sk-1234567890abcdef"), "sk****ef")

    def test_short_string_fully_masked(self):
        """Strings at or below the reveal threshold collapse to ``****``."""
        # Default show_chars=2 -> threshold is 4 -> length-4 strings are masked.
        self.assertEqual(redact("abcd"), "****")
        # Length 1 -> fully masked.
        self.assertEqual(redact("x"), "****")
        # Length 2 == 2 * show_chars -> fully masked.
        self.assertEqual(redact("ab"), "****")
        # Length 5 > 2 * show_chars -> partial mask (not "short" test, sorry).
        self.assertEqual(redact("abcde"), "ab****de")

    def test_empty_string_returns_empty_string(self):
        """An empty string falls below the threshold and is fully masked.

        With ``show_chars=2`` the threshold is 4, so an empty string is
        at-or-below the threshold and gets fully masked to ``"****"``.
        """
        self.assertEqual(redact(""), "****")

    def test_show_chars_zero_yields_full_mask(self):
        """``show_chars=0`` reveals nothing on either side."""
        # Threshold 0 -> any non-empty string is fully masked.
        self.assertEqual(redact("hunter2", show_chars=0), "****hunter2")
        # show_chars=0 means slice [:0] + **** + slice [-0:] = '****' + original.
        self.assertEqual(redact("a", show_chars=0), "****a")

    def test_show_chars_one(self):
        """``show_chars=1`` exposes a single character at each end."""
        self.assertEqual(redact("hunter2", show_chars=1), "h****2")
        # 2 chars total <= 2 * 1 -> fully masked.
        self.assertEqual(redact("ab", show_chars=1), "****")
        # 3 chars total > 2 -> partial mask.
        self.assertEqual(redact("abc", show_chars=1), "a****c")

    def test_show_chars_four(self):
        """Larger ``show_chars`` reveal more of the value."""
        self.assertEqual(redact("hunter2!!", show_chars=4), "hunt****r2!!")
        # Length 8 == 2 * 4 -> fully masked.
        self.assertEqual(redact("hunter22", show_chars=4), "****")
        # Length 7 < 2 * 4 -> fully masked (threshold catches it).
        self.assertEqual(redact("hunter2", show_chars=4), "****")

    def test_non_string_inputs_pass_through(self):
        """Non-string inputs are returned untouched."""
        self.assertEqual(redact(12345), 12345)
        self.assertIsNone(redact(None))
        self.assertEqual(redact(3.14), 3.14)
        sample = {"k": "v"}
        self.assertIs(redact(sample), sample)
        sample_list = [1, 2, 3]
        self.assertIs(redact(sample_list), sample_list)


class TestRedactDict(unittest.TestCase):
    """Behaviour of the recursive :func:`redact_dict` helper."""

    def test_top_level_secret_keys_are_masked(self):
        """Keys matching any default pattern are masked at the top level."""
        cfg = {"host": "api.example.com", "password": "hunter2"}
        out = redact_dict(cfg)
        self.assertEqual(out["host"], "api.example.com")
        # 'hunter2' -> default show_chars=2 -> 'hu****r2'.
        self.assertEqual(out["password"], "hu****r2")

    def test_non_secret_keys_are_untouched(self):
        """Plain keys propagate their values unchanged."""
        cfg = {"host": "api.example.com", "port": 443, "username": "alice"}
        self.assertEqual(
            redact_dict(cfg),
            {"host": "api.example.com", "port": 443, "username": "alice"},
        )

    def test_nested_dict_secrets_are_masked(self):
        """Dicts nested inside other dicts are walked recursively."""
        cfg = {"auth": {"token": "abc123xyz", "expires": 1234567890}}
        out = redact_dict(cfg)
        # 'abc123xyz' length 9 > 4 -> 'ab****yz'.
        self.assertEqual(out["auth"]["token"], "ab****yz")
        self.assertEqual(out["auth"]["expires"], 1234567890)

    def test_list_of_dicts_secrets_are_masked(self):
        """Lists containing dicts are walked element by element."""
        cfg = {"checks": [{"name": "db", "password": "secret123"}]}
        out = redact_dict(cfg)
        self.assertEqual(out["checks"][0]["name"], "db")
        # 'secret123' length 9 > 4 -> 'se****23'.
        self.assertEqual(out["checks"][0]["password"], "se****23")

    def test_mixed_case_keys_are_detected(self):
        """Matching is case-insensitive on both the key and patterns."""
        cfg = {
            "Password": "hunter2",
            "API_KEY": "sk-1234567890abcdef",
            "Auth": "Bearer xyz",
            "AUTHORIZATION": "Token abc",
        }
        out = redact_dict(cfg)
        self.assertEqual(out["Password"], "hu****r2")
        self.assertEqual(out["API_KEY"], "sk****ef")
        # 'Bearer xyz' length 10 > 4 -> 'Be****yz'.
        self.assertEqual(out["Auth"], "Be****yz")
        # 'Token abc' length 9 > 4 -> 'To****bc'.
        self.assertEqual(out["AUTHORIZATION"], "To****bc")

    def test_substring_keys_are_detected(self):
        """Keys containing the pattern as a substring also match."""
        cfg = {"user_password_hash": "value", "db_password": "secret"}
        out = redact_dict(cfg)
        # 'value' length 5 > 4 -> 'va****ue'.
        self.assertEqual(out["user_password_hash"], "va****ue")
        # 'secret' length 6 > 4 -> 'se****et'.
        self.assertEqual(out["db_password"], "se****et")

    def test_custom_patterns_restrict_masking(self):
        """Supplying ``patterns`` limits which keys are considered secret."""
        cfg = {"api_key": "sk-1234567890abcdef", "password": "hunter2"}
        out = redact_dict(cfg, patterns=frozenset({"api_key"}))
        # Only api_key masked.
        self.assertEqual(out["api_key"], "sk****ef")
        # password is no longer a secret under the custom set.
        self.assertEqual(out["password"], "hunter2")

    def test_custom_patterns_can_introduce_new_names(self):
        """Custom patterns can target keys not in the default set."""
        cfg = {"ssn": "123-45-6789", "phone": "555-1234"}
        out = redact_dict(cfg, patterns=frozenset({"ssn", "phone"}))
        # '123-45-6789' length 11 > 4 -> '12****89'.
        self.assertEqual(out["ssn"], "12****89")
        # '555-1234' length 8 > 4 -> '55****34'.
        self.assertEqual(out["phone"], "55****34")

    def test_non_dict_input_passes_through(self):
        """Scalars and other non-collection inputs are returned unchanged."""
        self.assertEqual(redact_dict("just a string"), "just a string")
        self.assertEqual(redact_dict(42), 42)
        self.assertIsNone(redact_dict(None))
        # A bare list without dicts also passes through unchanged because
        # its elements are not dicts/lists and so the recursion returns
        # them verbatim.
        self.assertEqual(redact_dict([1, 2, 3]), [1, 2, 3])

    def test_empty_dict_returns_empty_dict(self):
        """Empty input dict yields an empty output dict of the same shape."""
        self.assertEqual(redact_dict({}), {})

    def test_dict_is_not_mutated(self):
        """The original mapping is left intact after redaction."""
        cfg = {"password": "hunter2", "host": "api"}
        snapshot = {"password": "hunter2", "host": "api"}
        redact_dict(cfg)
        self.assertEqual(cfg, snapshot)

    def test_show_chars_propagates_to_nested_values(self):
        """``show_chars`` is forwarded into every recursive :func:`redact` call."""
        cfg = {"password": "hunter2", "auth": {"token": "abc123xyz"}}
        out = redact_dict(cfg, show_chars=4)
        # 'hunter2' length 7 <= 2 * 4 -> fully masked.
        self.assertEqual(out["password"], "****")
        # 'abc123xyz' length 9 > 2 * 4 -> partial mask: 'abc1****3xyz'.
        self.assertEqual(out["auth"]["token"], "abc1****3xyz")


class TestSecretPatterns(unittest.TestCase):
    """Sanity checks on the module-level :data:`SECRET_PATTERNS` set."""

    def test_contains_common_secret_names(self):
        """The default set covers the patterns documented in the spec."""
        expected = {
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
        for name in expected:
            self.assertIn(name, SECRET_PATTERNS)

    def test_is_frozenset(self):
        """``SECRET_PATTERNS`` is immutable so it can be safely shared."""
        self.assertIsInstance(SECRET_PATTERNS, frozenset)


class TestIsSecretKey(unittest.TestCase):
    """Direct checks for the ``_is_secret_key`` substring helper."""

    def test_non_string_keys_return_false(self):
        """Non-string keys never match secret patterns."""
        self.assertFalse(_is_secret_key(123, SECRET_PATTERNS))
        self.assertFalse(_is_secret_key(None, SECRET_PATTERNS))
        self.assertFalse(_is_secret_key(("password",), SECRET_PATTERNS))

    def test_substring_match_is_case_insensitive(self):
        """Both upper- and mixed-case keys match lower-case patterns."""
        self.assertTrue(_is_secret_key("password", SECRET_PATTERNS))
        self.assertTrue(_is_secret_key("PASSWORD", SECRET_PATTERNS))
        self.assertTrue(_is_secret_key("User_Password", SECRET_PATTERNS))
        self.assertFalse(_is_secret_key("username", SECRET_PATTERNS))


if __name__ == "__main__":
    unittest.main()
