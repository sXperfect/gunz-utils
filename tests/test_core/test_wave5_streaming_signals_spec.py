"""Tests for Wave 5: streaming I/O, signals, and specs (#57–#70)."""

from __future__ import annotations

import array
import asyncio
import io
import math
import signal
import unittest
from dataclasses import dataclass

from gunz_utils.sentinels import UNSET
from gunz_utils.signals import (
    AsyncSignalRegistration,
    GracefulShutdown,
    SignalRegistration,
    install_async_signal_handlers,
    install_termination_handler,
)
from gunz_utils.spec import (
    coerce_spec_mapping,
    coerce_spec_sequence,
    from_object_or_fields,
)
from gunz_utils.streaming import (
    BoundedWriter,
    DigestWriter,
    StreamCopyResult,
    copy_and_hash,
    iter_jsonl,
    write_jsonl,
)


@dataclass(frozen=True)
class DummyConfig:
    host: str = "localhost"
    port: int = 8080


class TestWave5Streaming(unittest.TestCase):
    def test_item57_iter_jsonl_eager_validation_and_float_check(self) -> None:
        # Eager validation raises immediately, without next()
        with self.assertRaises(TypeError):
            iter_jsonl("not-a-stream")  # type: ignore[arg-type]
        with self.assertRaises(ValueError):
            iter_jsonl(io.StringIO(""), max_line_length=0)
        with self.assertRaises(ValueError):
            iter_jsonl(io.StringIO(""), max_line_length=-5)

        # Non-finite float rejection
        stream = io.StringIO('{"val": 1e999}\n')
        with self.assertRaises(ValueError):
            list(iter_jsonl(stream))

    def test_item58_write_jsonl_string_guard_and_deterministic(self) -> None:
        buf = io.StringIO()
        with self.assertRaises(TypeError):
            write_jsonl(buf, "bare string")  # type: ignore[arg-type]
        with self.assertRaises(TypeError):
            write_jsonl(buf, b"bare bytes")  # type: ignore[arg-type]

        # Valid write
        count = write_jsonl(buf, [{"b": 2, "a": 1}])
        self.assertEqual(count, 1)
        self.assertEqual(buf.getvalue(), '{"a":1,"b":2}\n')

    def test_item59_bounded_writer_multibyte_and_context(self) -> None:
        buf = io.BytesIO()
        writer = BoundedWriter(buf, max_bytes=8)
        self.assertEqual(writer.remaining_bytes, 8)

        # multi-byte array
        arr = array.array("I", [1, 2])  # 2 unsigned ints = 8 bytes
        written = writer.write(memoryview(arr))
        self.assertEqual(written, 8)
        self.assertEqual(writer.remaining_bytes, 0)
        self.assertEqual(writer.bytes_written, 8)

        # Exceed limit
        with self.assertRaises(ValueError):
            writer.write(b"1")

        # Context manager
        with BoundedWriter(io.BytesIO(), max_bytes=10) as bw:
            bw.write(b"hello")
            self.assertEqual(bw.remaining_bytes, 5)

    def test_item60_digest_writer_multibyte_and_flush(self) -> None:
        buf = io.BytesIO()
        with DigestWriter(buf, max_bytes=16) as dw:
            dw.write(bytearray(b"abcdefgh"))
            dw.flush()
            self.assertGreater(len(dw.hexdigest), 0)

    def test_item61_copy_and_hash_stream_capability_validation(self) -> None:
        with self.assertRaises(TypeError):
            copy_and_hash("not-a-stream", io.BytesIO())  # type: ignore[arg-type]
        with self.assertRaises(TypeError):
            copy_and_hash(io.BytesIO(), "not-a-stream")  # type: ignore[arg-type]

        src = io.BytesIO(b"data to copy")
        dst = io.BytesIO()
        res = copy_and_hash(src, dst)
        self.assertEqual(res.bytes_written, 12)
        self.assertEqual(dst.getvalue(), b"data to copy")


class TestWave5Signals(unittest.IsolatedAsyncioTestCase):
    def test_item62_graceful_shutdown_eager_signums_validation(self) -> None:
        with self.assertRaises(ValueError):
            GracefulShutdown(signums=())
        with self.assertRaises(ValueError):
            GracefulShutdown(signums=(-1,))
        with self.assertRaises(TypeError):
            GracefulShutdown(signums="SIGINT")  # type: ignore[arg-type]

    def test_item63_trigger_shutdown_preserves_signal_and_validates(self) -> None:
        gs = GracefulShutdown()
        with self.assertRaises(ValueError):
            gs.trigger_shutdown(-99)
        with self.assertRaises(ValueError):
            gs.trigger_shutdown(True)  # type: ignore[arg-type]

        gs.trigger_shutdown(signal.SIGINT)
        self.assertEqual(gs.signal_received, signal.SIGINT)
        # Calling trigger_shutdown() without a signum does not wipe existing signal
        gs.trigger_shutdown(None)
        self.assertEqual(gs.signal_received, signal.SIGINT)

    async def test_item64_graceful_shutdown_wait(self) -> None:
        gs = GracefulShutdown()
        # Timeout expiration returns False
        done = await gs.wait(timeout=0.01)
        self.assertFalse(done)

        # Triggered shutdown returns True
        gs.trigger_shutdown()
        done = await gs.wait(timeout=0.1)
        self.assertTrue(done)

    def test_item65_signal_registration_slots_and_restored(self) -> None:
        reg = SignalRegistration(signum=signal.SIGUSR1, previous=signal.SIG_DFL, handler=lambda s, f: None)
        self.assertFalse(reg.restored)
        self.assertTrue(hasattr(reg, "__slots__"))

    def test_item66_install_signal_handlers_callable_validation(self) -> None:
        with self.assertRaises(TypeError):
            install_termination_handler("not-a-callable")  # type: ignore[arg-type]
        with self.assertRaises(TypeError):
            install_async_signal_handlers("not-a-callable")  # type: ignore[arg-type]


class TestWave5Spec(unittest.TestCase):
    def test_item67_from_object_or_fields(self) -> None:
        with self.assertRaises(TypeError):
            from_object_or_fields("not-a-class", None, {})  # type: ignore[arg-type]
        with self.assertRaises(TypeError):
            from_object_or_fields(DummyConfig, None, "not-a-dict")  # type: ignore[arg-type]
        with self.assertRaises(TypeError):
            from_object_or_fields(DummyConfig, None, {}, allow_none="yes")  # type: ignore[arg-type]

        # Valid build from fields
        cfg = from_object_or_fields(DummyConfig, None, {"host": "127.0.0.1", "port": UNSET})
        self.assertEqual(cfg, DummyConfig(host="127.0.0.1", port=8080))

    def test_item68_coerce_spec_sequence_guards(self) -> None:
        with self.assertRaises(TypeError):
            coerce_spec_sequence(DummyConfig, "bare string")  # type: ignore[arg-type]
        with self.assertRaises(TypeError):
            coerce_spec_sequence("not-a-class", [])  # type: ignore[arg-type]

        res = coerce_spec_sequence(DummyConfig, [{"host": "a"}, DummyConfig(host="b")])
        self.assertEqual(len(res), 2)
        self.assertEqual(res[0].host, "a")
        self.assertEqual(res[1].host, "b")

    def test_item69_item70_coerce_spec_mapping(self) -> None:
        with self.assertRaises(TypeError):
            coerce_spec_mapping("not-a-class", {})  # type: ignore[arg-type]
        with self.assertRaises(TypeError):
            coerce_spec_mapping(DummyConfig, "not-a-dict")  # type: ignore[arg-type]

        raw = {
            "primary": {"host": "srv1", "port": 9000},
            "replica": DummyConfig(host="srv2", port=9001),
        }
        res = coerce_spec_mapping(DummyConfig, raw)
        self.assertIsInstance(res["primary"], DummyConfig)
        self.assertEqual(res["primary"].host, "srv1")
        self.assertEqual(res["replica"].port, 9001)


if __name__ == "__main__":
    unittest.main()
