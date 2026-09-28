"""Adversarial proof tests for families that entered the audit at A1."""

from __future__ import annotations

import asyncio
import hashlib
import io
import signal
from contextlib import AbstractAsyncContextManager, AbstractContextManager
from pathlib import Path
from unittest.mock import patch

import pytest

import gunz_utils.content_store as content_store_module
import gunz_utils.leases as leases_module
from gunz_utils.concurrency import gather_limited, map_unordered
from gunz_utils.content_store import ContentAddressedStore
from gunz_utils.ext.validation_stdlib import type_checked
from gunz_utils.fs import transactional_directory
from gunz_utils.io import atomic_write
from gunz_utils.leases import LeaseTiming, run_with_lease_heartbeat
from gunz_utils.partitions import partition_overlaps
from gunz_utils.pipeline import worker_map
from gunz_utils.plugins import discover_plugins
from gunz_utils.resources import AsyncResourceGroup, ResourceGroup
from gunz_utils.signals import install_termination_handler
from gunz_utils.streaming import BoundedWriter, DigestWriter, copy_and_hash, hash_stream
from gunz_utils.versioning import (
    SchemaMigrationError,
    SchemaMigrator,
    VersionedEnvelope,
)


class _PartialThenStop:
    def __init__(self) -> None:
        self.data = bytearray()
        self.calls = 0

    def write(self, data: object) -> int:
        view = memoryview(data)
        self.calls += 1
        if self.calls == 1:
            self.data.extend(view[:1])
            return 1
        return 0


class _OverReportingWriter:
    def write(self, data: object) -> int:
        return len(memoryview(data)) + 1


def test_streaming_partial_failure_accounts_only_committed_bytes() -> None:
    bounded_target = _PartialThenStop()
    bounded = BoundedWriter(bounded_target, max_bytes=3)
    with pytest.raises(OSError, match="no forward progress"):
        bounded.write(b"abc")
    assert bounded.bytes_written == 1
    assert bytes(bounded_target.data) == b"a"

    digest_target = _PartialThenStop()
    digest = DigestWriter(digest_target)
    with pytest.raises(OSError, match="no forward progress"):
        digest.write(b"abc")
    assert digest.bytes_written == 1
    assert digest.hexdigest == hashlib.sha256(b"a").hexdigest()


def test_streaming_rejects_invalid_write_counts_and_size_domains() -> None:
    writer = BoundedWriter(_OverReportingWriter(), max_bytes=3)
    with pytest.raises(OSError, match="invalid write count"):
        writer.write(b"abc")
    assert writer.bytes_written == 0

    for invalid in (True, -1, 1.5):
        with pytest.raises(ValueError):
            BoundedWriter(io.BytesIO(), max_bytes=invalid)  # type: ignore[arg-type]
        with pytest.raises(ValueError):
            DigestWriter(
                io.BytesIO(),
                max_bytes=invalid,  # type: ignore[arg-type]
            )

    for invalid in (True, 0, -1, 1.5):
        with pytest.raises(ValueError):
            hash_stream(
                io.BytesIO(b"x"),
                chunk_size=invalid,  # type: ignore[arg-type]
            )
        with pytest.raises(ValueError):
            copy_and_hash(
                io.BytesIO(b"x"),
                io.BytesIO(),
                chunk_size=invalid,  # type: ignore[arg-type]
            )


def _subset(mask: int) -> tuple[str, ...]:
    universe = ("x", "y", "z")
    return tuple(
        value
        for index, value in enumerate(universe)
        if mask & (1 << index)
    )


def test_partition_overlap_matches_exhaustive_small_domain_oracle() -> None:
    names = ("a", "b", "c")
    for left_mask in range(8):
        for middle_mask in range(8):
            for right_mask in range(8):
                groups = {
                    "a": _subset(left_mask),
                    "b": _subset(middle_mask),
                    "c": _subset(right_mask),
                }
                actual = partition_overlaps(groups)
                expected = {}
                for left_index, left in enumerate(names):
                    for right in names[left_index + 1 :]:
                        overlap = set(groups[left]) & set(groups[right])
                        if overlap:
                            expected[(left, right)] = frozenset(overlap)
                assert actual == expected


def test_partition_overlap_rejects_whitespace_only_name() -> None:
    with pytest.raises(ValueError, match="partition names"):
        partition_overlaps({"   ": ("x",)})


def test_version_migration_runs_each_step_once_and_preserves_metadata() -> None:
    calls: list[int] = []
    migrator = SchemaMigrator()

    def to_v2(payload: dict[str, int]) -> dict[str, int]:
        calls.append(1)
        return {**payload, "v": 2}

    def to_v3(payload: dict[str, int]) -> dict[str, int]:
        calls.append(2)
        return {**payload, "v": 3}

    migrator.register("demo", 1, to_v2)
    migrator.register("demo", 2, to_v3)
    source_metadata = {"source": "audit"}
    envelope = VersionedEnvelope("demo", 1, {"v": 1}, source_metadata)

    result = migrator.migrate(envelope, target_version=3)

    assert calls == [1, 2]
    assert result.version == 3
    assert result.payload == {"v": 3}
    assert result.metadata == {"source": "audit"}
    assert envelope.payload == {"v": 1}
    source_metadata["source"] = "changed"
    assert result.metadata == {"source": "audit"}


def test_versioning_rejects_whitespace_schema_and_duplicate_step() -> None:
    with pytest.raises(ValueError, match="schema"):
        VersionedEnvelope("   ", 1, {})
    with pytest.raises(SchemaMigrationError, match="schema"):
        VersionedEnvelope.from_dict(
            {"schema": "   ", "version": 1, "payload": {}}
        )

    migrator = SchemaMigrator()
    migrator.register("demo", 1, lambda value: value)
    with pytest.raises(ValueError, match="already registered"):
        migrator.register("demo", 1, lambda value: value)


def test_stdlib_validator_enforces_pep604_union() -> None:
    @type_checked
    def accepts_optional(value: int | None) -> int | None:
        return value

    assert accepts_optional(3) == 3
    assert accepts_optional(None) is None
    for invalid in ("3", True, 3.5):
        with pytest.raises(TypeError):
            accepts_optional(invalid)  # type: ignore[arg-type]


def test_plugin_discovery_validates_configuration_before_lookup() -> None:
    for invalid in ("", "   ", 1, None):
        with pytest.raises(ValueError, match="group"):
            discover_plugins(invalid)  # type: ignore[arg-type]
    with pytest.raises(ValueError, match="instantiate"):
        discover_plugins("demo.plugins", instantiate=1)  # type: ignore[arg-type]


def test_content_store_fallback_publication_and_failure_cleanup(
    tmp_path: Path,
) -> None:
    store = ContentAddressedStore(tmp_path / "store")

    with patch.object(
        content_store_module.os,
        "link",
        side_effect=OSError("hard links unavailable"),
    ):
        artifact = store.put_bytes(b"fallback")
    assert artifact.path.read_bytes() == b"fallback"
    assert store.verify(artifact.digest)

    failing = ContentAddressedStore(tmp_path / "failing-store")
    with (
        patch.object(
            content_store_module.os,
            "link",
            side_effect=OSError("hard links unavailable"),
        ),
        patch.object(
            content_store_module.os,
            "replace",
            side_effect=OSError("replace failed"),
        ),
    ):
        with pytest.raises(OSError, match="replace failed"):
            failing.put_bytes(b"payload")
    assert list(failing.root.glob(".incoming.*.tmp")) == []


def test_atomic_write_fsync_failure_before_replace_preserves_original(
    tmp_path: Path,
) -> None:
    target = tmp_path / "value.txt"
    target.write_text("old", encoding="utf-8")

    with patch("gunz_utils.io.os.fsync", side_effect=OSError("fsync failed")):
        with pytest.raises(OSError, match="fsync failed"):
            atomic_write(target, "new", durable=True)

    assert target.read_text(encoding="utf-8") == "old"
    assert list(tmp_path.glob(".value.txt.*.tmp")) == []


def test_atomic_write_directory_fsync_failure_has_documented_visibility(
    tmp_path: Path,
) -> None:
    target = tmp_path / "value.txt"
    target.write_text("old", encoding="utf-8")

    with patch(
        "gunz_utils.io.os.fsync",
        side_effect=[None, OSError("directory fsync failed")],
    ):
        with pytest.raises(OSError, match="directory fsync failed"):
            atomic_write(target, "new", durable=True)

    assert target.read_text(encoding="utf-8") == "new"
    assert list(tmp_path.glob(".value.txt.*.tmp")) == []


def test_transactional_directory_cleans_failed_staging(
    tmp_path: Path,
) -> None:
    target = tmp_path / "published"
    with pytest.raises(RuntimeError, match="build failed"):
        with transactional_directory(target) as staging:
            (staging / "data.txt").write_text("partial", encoding="utf-8")
            raise RuntimeError("build failed")

    assert not target.exists()
    assert list(tmp_path.glob(".published.*")) == []


def test_transactional_directory_replace_failure_cleans_staging(
    tmp_path: Path,
) -> None:
    target = tmp_path / "published"
    with patch("gunz_utils.fs.os.replace", side_effect=OSError("publish failed")):
        with pytest.raises(OSError, match="publish failed"):
            with transactional_directory(target) as staging:
                (staging / "data.txt").write_text("complete", encoding="utf-8")

    assert not target.exists()
    assert list(tmp_path.glob(".published.*")) == []


def test_lease_outer_cancellation_cleans_operation_and_heartbeat(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def scenario() -> None:
        operation_started = asyncio.Event()
        operation_cancelled = asyncio.Event()
        heartbeat_cancelled = asyncio.Event()

        async def fake_heartbeat(*_args: object, **_kwargs: object) -> None:
            try:
                await asyncio.Event().wait()
            finally:
                heartbeat_cancelled.set()

        async def work() -> None:
            operation_started.set()
            try:
                await asyncio.Event().wait()
            finally:
                operation_cancelled.set()

        async def renew() -> bool:
            return True

        monkeypatch.setattr(leases_module, "_heartbeat_loop", fake_heartbeat)
        task = asyncio.create_task(
            run_with_lease_heartbeat(
                work,
                renew,
                heartbeat_interval=1.0,
            )
        )
        await operation_started.wait()
        await asyncio.sleep(0)
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task
        assert operation_cancelled.is_set()
        assert heartbeat_cancelled.is_set()

    asyncio.run(scenario())


def test_lease_timing_and_mode_flags_have_strict_domains() -> None:
    for invalid in (True, 0, -1, float("nan"), float("inf")):
        with pytest.raises(ValueError):
            LeaseTiming(
                lease_seconds=10,
                heartbeat_interval=invalid,  # type: ignore[arg-type]
            )

    async def work() -> None:
        return None

    async def renew() -> bool:
        return True

    with pytest.raises(ValueError, match="renew_immediately"):
        asyncio.run(
            run_with_lease_heartbeat(
                work,
                renew,
                heartbeat_interval=1,
                renew_immediately=1,  # type: ignore[arg-type]
            )
        )


def test_gather_limited_outer_cancellation_cleans_bounded_tasks() -> None:
    async def scenario() -> None:
        started = 0
        active = 0
        all_started = asyncio.Event()

        async def work() -> int:
            nonlocal started, active
            started += 1
            active += 1
            if started == 2:
                all_started.set()
            try:
                await asyncio.Event().wait()
            finally:
                active -= 1

        task = asyncio.create_task(
            gather_limited(
                (work() for _ in range(10)),
                limit=2,
            )
        )
        await all_started.wait()
        assert started == 2
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task
        assert active == 0

    asyncio.run(scenario())


def test_concurrency_rejects_boolean_and_non_integer_configuration() -> None:
    async def scenario() -> None:
        for invalid in (True, 0, 1.5):
            with pytest.raises(ValueError, match="limit"):
                await gather_limited([], limit=invalid)  # type: ignore[arg-type]
        with pytest.raises(ValueError, match="return_exceptions"):
            await gather_limited(
                [],
                limit=1,
                return_exceptions=1,  # type: ignore[arg-type]
            )

    asyncio.run(scenario())


def test_map_unordered_close_cancels_pending_tasks() -> None:
    async def scenario() -> None:
        started = 0
        cancelled: set[int] = set()
        all_started = asyncio.Event()
        never = asyncio.Event()

        async def work(value: int) -> int:
            nonlocal started
            started += 1
            if started == 3:
                all_started.set()
            await all_started.wait()
            if value == 0:
                return value
            try:
                await never.wait()
            finally:
                cancelled.add(value)
            return value

        stream = map_unordered(work, range(3), limit=3)
        assert await anext(stream) == 0
        await stream.aclose()
        await asyncio.sleep(0)
        assert cancelled == {1, 2}

    asyncio.run(scenario())


def test_worker_pipeline_is_bounded_and_cleans_on_early_close() -> None:
    async def scenario() -> None:
        active = 0
        peak = 0
        started = 0
        cancelled = 0
        two_started = asyncio.Event()
        never = asyncio.Event()

        async def work(value: int) -> int:
            nonlocal active, peak, started, cancelled
            active += 1
            peak = max(peak, active)
            started += 1
            if started == 2:
                two_started.set()
            try:
                await two_started.wait()
                if value == 0:
                    return value
                await never.wait()
                return value
            finally:
                if value != 0:
                    cancelled += 1
                active -= 1

        stream = worker_map(
            work,
            range(20),
            workers=2,
            queue_size=1,
        )
        assert await anext(stream) == 0
        await stream.aclose()
        await asyncio.sleep(0)
        assert peak <= 2
        assert active == 0
        assert cancelled >= 1

        for invalid in (True, 0, 1.5):
            invalid_stream = worker_map(
                work,
                [],
                workers=invalid,  # type: ignore[arg-type]
            )
            with pytest.raises(ValueError, match="workers"):
                await anext(invalid_stream)

        invalid_queue = worker_map(
            work,
            [],
            workers=1,
            queue_size=True,  # type: ignore[arg-type]
        )
        with pytest.raises(ValueError, match="queue_size"):
            await anext(invalid_queue)

    asyncio.run(scenario())


class _SyncResource(AbstractContextManager[str]):
    def __init__(self, name: str, events: list[str]) -> None:
        self.name = name
        self.events = events

    def __enter__(self) -> str:
        self.events.append(f"enter:{self.name}")
        return self.name

    def __exit__(self, *_args: object) -> None:
        self.events.append(f"exit:{self.name}")


class _AsyncResource(AbstractAsyncContextManager[str]):
    def __init__(self, name: str, events: list[str]) -> None:
        self.name = name
        self.events = events

    async def __aenter__(self) -> str:
        self.events.append(f"enter:{self.name}")
        return self.name

    async def __aexit__(self, *_args: object) -> None:
        self.events.append(f"exit:{self.name}")


def test_resource_group_releases_in_reverse_order_on_failure() -> None:
    events: list[str] = []
    with pytest.raises(RuntimeError, match="boom"):
        with ResourceGroup() as group:
            assert group.enter(_SyncResource("a", events)) == "a"
            assert group.enter(_SyncResource("b", events)) == "b"
            raise RuntimeError("boom")

    assert events == ["enter:a", "enter:b", "exit:b", "exit:a"]


def test_async_resource_group_releases_in_reverse_order_on_failure() -> None:
    async def scenario() -> None:
        events: list[str] = []
        with pytest.raises(RuntimeError, match="boom"):
            async with AsyncResourceGroup() as group:
                assert await group.enter(_AsyncResource("a", events)) == "a"
                assert await group.enter(_AsyncResource("b", events)) == "b"
                raise RuntimeError("boom")

        assert events == ["enter:a", "enter:b", "exit:b", "exit:a"]

    asyncio.run(scenario())


def test_termination_registration_rejects_invalid_domain_before_install() -> None:
    for signum in (True, 0, -1, 1.5):
        with pytest.raises(ValueError, match="signum"):
            install_termination_handler(
                lambda _signal: None,
                signum=signum,  # type: ignore[arg-type]
            )

    with pytest.raises(ValueError, match="exit_after"):
        install_termination_handler(
            lambda _signal: None,
            signum=signal.SIGTERM,
            exit_after=1,  # type: ignore[arg-type]
        )
