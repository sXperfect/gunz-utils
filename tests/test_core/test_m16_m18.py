from __future__ import annotations

import unittest

from gunz_utils.binary import ByteReader, encode_uvarint
from gunz_utils.buffers import as_readonly_view, dispatch


class TestM16M18(unittest.TestCase):
    def test_zero_copy_view(self) -> None:
        source = bytearray(b"abc")
        view = as_readonly_view(source)
        self.assertEqual(bytes(view), b"abc")
        self.assertTrue(view.readonly)

    def test_varint_round_trip(self) -> None:
        for value in [0, 1, 127, 128, 16384, 2**63 - 1]:
            encoded = encode_uvarint(value)
            self.assertEqual(ByteReader(encoded).read_uvarint(), value)

    def test_bounds(self) -> None:
        reader = ByteReader(b"x")
        with self.assertRaises(EOFError):
            reader.read(2)

    def test_dispatch(self) -> None:
        def reference() -> str:
            return "python"
        self.assertEqual(dispatch(reference)(), "python")


if __name__ == "__main__":
    unittest.main()
