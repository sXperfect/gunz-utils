"""Perpetual security audit phase 27 (round 4, deepest).

Re-audit of ``buffers``, ``content_store``, ``fs``, ``serialization``,
``context``, and ``typed_config``.

Finding:

1. ``buffers.as_readonly_view`` accepts non-bytes-like inputs and silently
   coerces them into a byte buffer via the ``bytes(data)`` fallback instead of
   rejecting them with ``TypeError``.

   buffers.py:31-38 tries ``memoryview(data).cast("B")`` and, on any
   ``TypeError``, falls back to ``view = memoryview(bytes(data))``.  There is
   no runtime type check that ``data`` is ``bytes | bytearray | memoryview``,
   even though that is the documented contract (buffers.py:18-20).  Python's
   ``bytes()`` constructor silently coerces several unrelated types:

     - ``bytes(5)`` -> ``b"\\x00\\x00\\x00\\x00\\x00"`` (N zero bytes for an
       ``int``), so ``as_readonly_view(5)`` returns five zero bytes instead of
       raising ``TypeError``;
     - ``bytes([1, 2, 3])`` / ``bytes(range(3))`` -> a byte buffer built from
       an arbitrary iterable, so ``as_readonly_view([1, 2, 3])`` silently
       returns ``b"\\x01\\x02\\x03"``;
     - ``bytes(1 << 30)`` attempts to allocate 1 GiB of zero bytes, so a
       stray large ``int`` (a size, a count, a return code, ...) becomes a
       memory-exhaustion / denial-of-service vector instead of a clear error.

   Expected: non-bytes-like input is rejected up front with ``TypeError``, and
   the zero-copy/fallback logic only ever runs for ``bytes | bytearray |
   memoryview``.
"""

import pytest

from gunz_utils.buffers import as_readonly_view


def test_as_readonly_view_rejects_integer_input():
    """RED: an ``int`` is silently converted to that many zero bytes by the
    ``bytes(data)`` fallback instead of being rejected as a non-bytes-like
    input.  ``as_readonly_view(5)`` currently returns ``b"\\x00"*5``.
    """
    with pytest.raises(TypeError):
        as_readonly_view(5)


def test_as_readonly_view_rejects_zero_int_input():
    """RED: ``as_readonly_view(0)`` currently returns an empty byte buffer
    rather than raising ``TypeError`` for a non-bytes-like input.
    """
    with pytest.raises(TypeError):
        as_readonly_view(0)


def test_as_readonly_view_rejects_iterable_input():
    """RED: an arbitrary iterable of small ints is silently coerced into a
    byte buffer (``bytes([1, 2, 3])`` == ``b"\\x01\\x02\\x03"``) instead of
    being rejected as a non-bytes-like input.
    """
    with pytest.raises(TypeError):
        as_readonly_view([1, 2, 3])
    with pytest.raises(TypeError):
        as_readonly_view(range(3))


def test_as_readonly_view_rejects_large_integer_without_huge_allocation():
    """RED: a stray large ``int`` triggers an unbounded zero-byte allocation
    through ``bytes(1 << 30)`` (a memory-exhaustion / DoS vector).  It must be
    rejected cheaply with ``TypeError`` and must never allocate.
    """
    with pytest.raises(TypeError):
        as_readonly_view(1 << 30)


def test_as_readonly_view_accepts_bytes_like_inputs():
    """GREEN: valid bytes-like inputs (bytes, bytearray, contiguous and
    non-contiguous memoryviews) still yield a readonly byte view.  This pins
    the correct behavior so the fix only adds input validation.
    """
    for data in (b"abc", bytearray(b"def"), memoryview(b"ghi")):
        view = as_readonly_view(data)
        assert view.readonly
        assert bytes(view) == bytes(data)

    stepped = as_readonly_view(memoryview(b"abcdef")[::2])
    assert stepped.readonly
    assert bytes(stepped) == b"ace"
