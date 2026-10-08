"""Acknowledged spawn-process proofs of cooperating CAS publication contracts."""

from __future__ import annotations

import errno
import hashlib
import multiprocessing
import os
from collections.abc import Iterator
from contextlib import contextmanager
from multiprocessing.connection import Connection
from multiprocessing.process import BaseProcess
from pathlib import Path
from typing import Any, cast

import pytest

from gunz_utils.content_store import ContentAddressedStore

_WAIT_SECONDS = 15.0
_PAYLOAD = bytes(range(256)) * 2048


def _require_hardlinks(directory: Path, fallback: bool) -> None:
    if fallback:
        return
    source, target = directory / "link-probe", directory / "link-probe-copy"
    source.write_bytes(b"probe")
    try:
        os.link(source, target)
    except OSError:
        pytest.skip("ordinary publication proof requires filesystem hard links")
    finally:
        target.unlink(missing_ok=True)
        source.unlink(missing_ok=True)


def _receive(connection: Connection) -> tuple[Any, ...]:
    if not connection.poll(_WAIT_SECONDS):
        raise TimeoutError("child did not acknowledge the requested CAS phase")
    message = connection.recv()
    if not isinstance(message, tuple):
        raise TypeError("child sent an invalid proof message")
    return message


def _publisher(
    root: str,
    payload: bytes,
    fallback: bool,
    phase: str,
    connection: Connection,
    fanout: int,
) -> None:
    """Pause at the actual publication syscall, preserving real store execution."""
    import gunz_utils.content_store as module

    original_link, original_replace = module.os.link, module.os.replace

    def publication(*args: Any, **kwargs: Any) -> None:
        temporary = Path(root) / Path(args[0]).name
        if phase == "after":
            operation = original_replace if fallback else original_link
            operation(*args, **kwargs)
        connection.send(("publication", temporary.name, phase))
        if _receive(connection) != ("continue",):
            raise ValueError("unexpected parent publication command")
        if phase == "error":
            raise OSError(errno.ENOSPC, "synthetic publication failure")
        if phase != "after":
            operation = original_replace if fallback else original_link
            operation(*args, **kwargs)

    def unavailable(*args: Any, **kwargs: Any) -> None:
        raise OSError(errno.EOPNOTSUPP, "hard links unavailable in this proof")

    if fallback:
        module.os.link = unavailable
        module.os.replace = publication
    else:
        module.os.link = publication
    try:
        store = ContentAddressedStore(Path(root), fanout_levels=fanout)
        connection.send(("ready", os.getpid()))
        if _receive(connection) != ("start",):
            raise ValueError("unexpected parent start command")
        artifact = store.put_bytes(payload)
        connection.send(
            (
                "success",
                artifact.digest,
                artifact.size_bytes,
                artifact.path.stat().st_ino,
            )
        )
    except BaseException as error:
        connection.send(("error", type(error).__name__))
    finally:
        module.os.link, module.os.replace = original_link, original_replace
        connection.close()


def _reader(
    root: str,
    digest: str,
    connection: Connection,
    fanout: int,
    hold_verification: bool,
) -> None:
    held = False

    class ObservedStore(ContentAddressedStore):
        def _verify_handle(
            self, descriptor: int, digest: str, size_bytes: int | None = None
        ) -> None:
            nonlocal held
            super()._verify_handle(descriptor, digest, size_bytes)
            if hold_verification and not held:
                held = True
                observed = os.read(descriptor, len(_PAYLOAD))
                os.lseek(descriptor, 0, os.SEEK_SET)
                connection.send(
                    (
                        "verified",
                        os.fstat(descriptor).st_ino,
                        hashlib.sha256(observed).hexdigest(),
                    )
                )
                if _receive(connection) != ("resume",):
                    raise ValueError("unexpected reader verification command")

    store = ObservedStore(Path(root), fanout_levels=fanout)
    connection.send(("ready", os.getpid()))
    try:
        while True:
            command = _receive(connection)
            if command == ("stop",):
                connection.send(("stopped",))
                return
            if command[0] != "read":
                raise ValueError("unexpected reader command")
            observations: list[tuple[Any, ...]] = []
            for _ in range(command[1]):
                try:
                    path = store.get(digest)
                except KeyError:
                    observations.append(("missing",))
                except ValueError as error:
                    if str(error) != "artifact changed during operation":
                        raise
                    observations.append(("identity_changed",))
                else:
                    data = path.read_bytes()
                    observations.append(
                        (
                            "present",
                            len(data),
                            hashlib.sha256(data).hexdigest(),
                            data == _PAYLOAD,
                            path.stat().st_ino,
                        )
                    )
            connection.send(("observations", observations))
    except BaseException as error:
        connection.send(("error", type(error).__name__))
    finally:
        connection.close()


def _corruptor(root: str, digest: str, connection: Connection) -> None:
    try:
        target = Path(root) / digest[:2] / digest
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(b"independent corrupt competitor")
        connection.send(("corrupt", os.getpid()))
    finally:
        connection.close()


class _Children:
    def __init__(self) -> None:
        self.context = multiprocessing.get_context("spawn")
        self.started: list[tuple[BaseProcess, Connection]] = []

    def start(self, target: Any, *args: Any) -> tuple[BaseProcess, Connection]:
        parent, child = self.context.Pipe()
        process = self.context.Process(target=target, args=(*args, child))
        try:
            process.start()
        except BaseException:
            parent.close()
            child.close()
            raise
        child.close()
        self.started.append((process, parent))
        return process, parent

    def publisher(
        self, root: Path, fallback: bool, *, phase: str = "before", fanout: int = 1
    ) -> tuple[BaseProcess, Connection]:
        # Child connection must precede fanout in this public helper's worker signature.
        parent, child = self.context.Pipe()
        process = self.context.Process(
            target=_publisher,
            args=(str(root), _PAYLOAD, fallback, phase, child, fanout),
        )
        try:
            process.start()
        except BaseException:
            parent.close()
            child.close()
            raise
        child.close()
        self.started.append((process, parent))
        assert _receive(parent)[0] == "ready"
        return process, parent

    def reader(
        self, root: Path, digest: str, fanout: int, *, hold_verification: bool = False
    ) -> Connection:
        parent, child = self.context.Pipe()
        process = self.context.Process(
            target=_reader, args=(str(root), digest, child, fanout, hold_verification)
        )
        try:
            process.start()
        except BaseException:
            parent.close()
            child.close()
            raise
        child.close()
        self.started.append((process, parent))
        assert _receive(parent)[0] == "ready"
        return parent

    @staticmethod
    def finish(process: BaseProcess) -> None:
        process.join(_WAIT_SECONDS)
        assert not process.is_alive(), "child did not finish after acknowledgment"
        assert process.exitcode == 0

    def close(self) -> None:
        for process, connection in self.started:
            connection.close()
            process.join(0.25)
            if process.is_alive():
                process.kill()
            process.join(_WAIT_SECONDS)
            if process.is_alive():
                raise RuntimeError("could not reap a spawned CAS proof process")
            process.close()


@contextmanager
def _children() -> Iterator[_Children]:
    children = _Children()
    try:
        yield children
    finally:
        children.close()


def _read(connection: Connection, count: int = 1) -> list[tuple[Any, ...]]:
    connection.send(("read", count))
    result = _receive(connection)
    assert result[0] == "observations", result
    return cast(list[tuple[Any, ...]], result[1])


def _assert_observations(observations: list[tuple[Any, ...]], digest: str) -> None:
    for observation in observations:
        if observation not in {("missing",), ("identity_changed",)}:
            assert observation[:4] == ("present", len(_PAYLOAD), digest, True)


@pytest.mark.parametrize("fallback", [False, True])
@pytest.mark.parametrize("fanout", [0, 2])
def test_independent_publishers_and_reader_preserve_same_digest_bytes(
    tmp_path: Path, fallback: bool, fanout: int
) -> None:
    _require_hardlinks(tmp_path, fallback)
    root = tmp_path / "store"
    digest = hashlib.sha256(_PAYLOAD).hexdigest()
    with _children() as children:
        first, first_pipe = children.publisher(root, fallback, fanout=fanout)
        second, second_pipe = children.publisher(root, fallback, fanout=fanout)
        reader = children.reader(root, digest, fanout)
        first_pipe.send(("start",))
        second_pipe.send(("start",))
        assert _receive(first_pipe)[0] == "publication"
        assert _receive(second_pipe)[0] == "publication"
        assert _read(reader) == [("missing",)]
        first_pipe.send(("continue",))
        _assert_observations(_read(reader, 16), digest)
        first_result = _receive(first_pipe)
        assert first_result[:3] == ("success", digest, len(_PAYLOAD))
        assert _read(reader)[0][:4] == ("present", len(_PAYLOAD), digest, True)
        second_pipe.send(("continue",))
        _assert_observations(_read(reader, 16), digest)
        second_result = _receive(second_pipe)
        assert second_result[:3] == ("success", digest, len(_PAYLOAD))
        # Normal no-replace retains winner; documented fallback may replace inode.
        if os.name == "posix":
            assert (first_result[3] != second_result[3]) == fallback
        assert _read(reader)[0][:4] == ("present", len(_PAYLOAD), digest, True)
        reader.send(("stop",))
        assert _receive(reader) == ("stopped",)
        children.finish(first)
        children.finish(second)
    assert list(root.glob(".incoming.*")) == []
    store = ContentAddressedStore(root, fanout_levels=fanout)
    assert store.get(digest).read_bytes() == _PAYLOAD


@pytest.mark.parametrize("fallback", [False, True])
def test_existing_corrupt_process_entry_is_rejected(
    tmp_path: Path, fallback: bool
) -> None:
    _require_hardlinks(tmp_path, fallback)
    root = tmp_path / "store"
    digest = hashlib.sha256(_PAYLOAD).hexdigest()
    with _children() as children:
        competitor, corrupt_pipe = children.start(_corruptor, str(root), digest)
        assert _receive(corrupt_pipe)[0] == "corrupt"
        children.finish(competitor)
        publisher, connection = children.publisher(root, fallback)
        connection.send(("start",))
        if not fallback:
            assert _receive(connection)[0] == "publication"
            connection.send(("continue",))
        assert _receive(connection) == ("error", "ValueError")
        children.finish(publisher)
    assert (
        root / digest[:2] / digest
    ).read_bytes() == b"independent corrupt competitor"
    assert list(root.glob(".incoming.*")) == []


@pytest.mark.parametrize("fallback", [False, True])
@pytest.mark.parametrize("phase", ["before", "after"])
def test_abrupt_publisher_death_at_acknowledged_publication_boundary(
    tmp_path: Path, fallback: bool, phase: str
) -> None:
    _require_hardlinks(tmp_path, fallback)
    root = tmp_path / "store"
    digest = hashlib.sha256(_PAYLOAD).hexdigest()
    with _children() as children:
        publisher, connection = children.publisher(root, fallback, phase=phase)
        connection.send(("start",))
        boundary = _receive(connection)
        assert boundary[0] == "publication"
        temporary = root / boundary[1]
        publisher.kill()
        publisher.join(_WAIT_SECONDS)
        assert not publisher.is_alive()
        assert publisher.exitcode != 0
        store = ContentAddressedStore(root)
        if phase == "before":
            with pytest.raises(KeyError):
                store.get(digest)
            assert temporary.read_bytes() == _PAYLOAD
            assert hashlib.sha256(temporary.read_bytes()).hexdigest() == digest
        else:
            artifact = store.get(digest)
            assert artifact.read_bytes() == _PAYLOAD
            if fallback:
                assert not temporary.exists()
            else:
                assert temporary.read_bytes() == _PAYLOAD
                assert os.path.samefile(temporary, artifact)
        # An independent later publisher works despite any crash-left staging.
        retry, retry_pipe = children.publisher(root, fallback)
        retry_pipe.send(("start",))
        if not fallback or phase == "before":
            assert _receive(retry_pipe)[0] == "publication"
            retry_pipe.send(("continue",))
        assert _receive(retry_pipe)[:3] == ("success", digest, len(_PAYLOAD))
        children.finish(retry)


def test_failed_fallback_process_publication_never_reports_success(
    tmp_path: Path,
) -> None:
    root = tmp_path / "store"
    digest = hashlib.sha256(_PAYLOAD).hexdigest()
    with _children() as children:
        publisher, connection = children.publisher(root, True, phase="error")
        connection.send(("start",))
        assert _receive(connection)[0] == "publication"
        connection.send(("continue",))
        assert _receive(connection) == ("error", "OSError")
        children.finish(publisher)
    with pytest.raises(KeyError):
        ContentAddressedStore(root).get(digest)
    assert list(root.glob(".incoming.*")) == []


def test_reader_fails_closed_if_fallback_replaces_verified_inode(
    tmp_path: Path,
) -> None:
    """Same-content inode changes fail closed; an explicit reader retry succeeds."""
    root = tmp_path / "store"
    digest = hashlib.sha256(_PAYLOAD).hexdigest()
    with _children() as children:
        first, first_pipe = children.publisher(root, True)
        second, second_pipe = children.publisher(root, True)
        first_pipe.send(("start",))
        second_pipe.send(("start",))
        assert _receive(first_pipe)[0] == "publication"
        assert _receive(second_pipe)[0] == "publication"
        first_pipe.send(("continue",))
        first_result = _receive(first_pipe)
        assert first_result[:3] == ("success", digest, len(_PAYLOAD))
        reader = children.reader(root, digest, 1, hold_verification=True)
        reader.send(("read", 1))
        verified = _receive(reader)
        assert verified == ("verified", first_result[3], digest)
        second_pipe.send(("continue",))
        second_result = _receive(second_pipe)
        assert second_result[:3] == ("success", digest, len(_PAYLOAD))
        reader.send(("resume",))
        assert _receive(reader) == ("observations", [("identity_changed",)])
        # Explicit retry by the independent reader succeeds on the new identity.
        assert _read(reader)[0][:4] == ("present", len(_PAYLOAD), digest, True)
        reader.send(("stop",))
        assert _receive(reader) == ("stopped",)
        children.finish(first)
        children.finish(second)
