"""Contract and behavior tests for gunz_utils.text."""

from __future__ import annotations

import re
import unittest

from gunz_utils.text import blank_spans, deduplicate_spans, word_pattern


class TestTextModule(unittest.TestCase):
    """Test word pattern matching, span blanking, and span deduplication."""

    def test_word_pattern_basic(self) -> None:
        pat = word_pattern("refactor")
        self.assertTrue(pat.search("need to refactor this"))
        self.assertTrue(pat.search("we refactored it"))
        self.assertTrue(pat.search("refactoring is fun"))
        self.assertFalse(pat.search("prefactor"))

    def test_word_pattern_inflections(self) -> None:
        # -y to -ies
        pat_dep = word_pattern("dependency")
        self.assertTrue(pat_dep.search("zero dependency"))
        self.assertTrue(pat_dep.search("many dependencies"))

        # -e to -ing
        pat_create = word_pattern("create")
        self.assertTrue(pat_create.search("we create code"))
        self.assertTrue(pat_create.search("creating tests"))
        self.assertTrue(pat_create.search("created cleanly"))

        # multi-word
        pat_multi = word_pattern("sanity check")
        self.assertTrue(pat_multi.search("run a sanity check"))
        self.assertTrue(pat_multi.search("run sanity-check"))
        self.assertTrue(pat_multi.search("run sanity checks"))

    def test_blank_spans_preserves_crlf(self) -> None:
        pat = re.compile(r"secret")
        text = "line1 secret\r\nline2 secret\n"
        blanked = blank_spans(text, [pat])
        self.assertEqual(blanked, "line1       \r\nline2       \n")
        self.assertIn("\r\n", blanked)
        self.assertEqual(len(blanked), len(text))

    def test_deduplicate_spans_prefers_longest(self) -> None:
        # Span B (5, 30) is longer than span A (5, 10) and span C (15, 25)
        candidates = [
            (5, 10, "short"),
            (5, 30, "long"),
            (15, 25, "medium"),
            (35, 40, "separate"),
        ]
        kept = deduplicate_spans(candidates)
        self.assertEqual(len(kept), 2)
        self.assertEqual(kept[0], (5, 30, "long"))
        self.assertEqual(kept[1], (35, 40, "separate"))


if __name__ == "__main__":
    unittest.main()
