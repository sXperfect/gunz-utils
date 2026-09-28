"""Proof tests for algorithm families that entered this sweep at A1."""

from __future__ import annotations

import asyncio
import hashlib
import io
import signal
from contextlib import asynccontextmanager, contextmanager
from pathlib import Path
from typing import Any
from unittest.mock import patch

import pytest

import gunz_utils.concurrency as concurrency_module
import gunz_utils.content_store as content_store_module
import gunz_utils.io as io_module
import gunz_utils.leases as leases_module
from gunz_utils.concurrency import gather_limited, map_unordered
from gunz_utils.content_store import ContentAddressedStore
from gunz_utils.fs import transactional_directory
from gunz_utils.io import atomic_write
from gunz_utils.leases import run_with_lease_heartbeat
from gunz_utils.partitions import PartitionManifest, partition_overlaps
from gunz_utils.pipeline import worker_map
from gunz_utils.plugins import discover_plugins
from gunz_utils.resources import AsyncResourceGroup, ResourceGroup
from gunz_utils.signals import (
    install_async_signal_handlers,
    install_termination_handler,
)
from gunz_utils.streaming import BoundedWriter, DigestWriter, iter_jsonl, write_jsonl
from gunz_utils.versioning import (
    SchemaMigrationError,
    SchemaMigrator,
    VersionedEnvelope,
)


def test_lease_runner_accepts_existing_future() -> None:
    async def scenario() -> str:
        loop = asyncio.get_running_loop()
        result: asyncio.Future[str] = loop.create_future()
        result.set_result("done")

        def operation() -> asyncio.Future[str]:
            return result

        async def renew() -> bool:
            return True

        return await run_with_lease_heartbeat(
            operation,
            renew,
            heartbeat_interval=3600.0,
        )

    assert asyncio.run(scenario()) == "done"


def test_lease_setup_failure_cleans_created_operation(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def scenario() -> None:
        created: list[asyncio.Future[None]] = []
        original_ensure = leases_module.asyncio.ensure_future

        def record_operation(awaitable: Any) -> asyncio.Future[None]:
            future = original_ensure(awaitable)
            created.append(future)
            return future

        def fail_heartbeat(coroutine: Any) -> None:
            coroutine.close()
            raise RuntimeError("heartbeat setup failed")

        monkeypatch.setattr(
            leases_module.asyncio,
            "ensure_future",
            record_operation,
        )
        monkeypatch.setattr(
            leases_module.asyncio,
            "create_task",
            fail_heartbeat,
        )

        async def operation() -> None:
            await asyncio.Event().wait()

        async def renew() -> bool:
            return True

        with pytest.raises(RuntimeError, match="heartbeat setup failed"):
            await run_with_lease_heartbeat(
                operation,
                renew,
                heartbeat_interval=1.0,
            )

        assert len(created) == 1
        assert created[0].done()
        assert created[0].cancelled()

    asyncio.run(scenario())


def test_gather_initial_iteration_failure_cleans_created_tasks(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def scenario() -> None:
        created: list[asyncio.Task[int]] = []
        original_create = concurrency_module.asyncio.create_task

        def record_create(coroutine: Any) -> asyncio.Task[int]:
            task = original_create(coroutine)
            created.append(task)
            return task

        monkeypatch.setattr(
            concurrency_module.asyncio,
            "create_task",
            record_create,
        )

        async def blocked() -> int:
            await asyncio.Event().wait()
            return 1

        def awaitables():
            yield blocked()
            raise RuntimeError("iterator failed")

        with pytest.raises(RuntimeError, match="iterator failed"):
            await gather_limited(
                awaitables(),
                limit=2,
            )

        assert len(created) == 1
        assert created[0].done()
        assert created[0].cancelled()

    asyncio.run(scenario())


def test_map_unordered_initial_iteration_failure_cleans_tasks(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def scenario() -> None:
        created: list[asyncio.Task[int]] = []
        original_create = concurrency_module.asyncio.create_task

        def record_create(coroutine: Any) -> asyncio.Task[int]:
            task = original_create(coroutine)
            created.append(task)
            return task

        monkeypatch.setattr(
            concurrency_module.asyncio,
            "create_task",
            record_create,
        )

        def items():
            yield 1
            raise RuntimeError("items failed")

        async def blocked(value: int) -> int:
            await asyncio.Event().wait()
            return value

        with pytest.raises(RuntimeError, match="items failed"):
            async for _ in map_unordered(
                blocked,
                items(),
                limit=2,
            ):
                pass

        assert len(created) == 1
        assert created[0].done()
        assert created[0].cancelled()

    asyncio.run(scenario())


def test_jsonl_rejects_non_standard_nan_constants() -> None:
    output = io.StringIO()
    with pytest.raises(ValueError):
        write_jsonl(
            output,
            [{"value": float("nan")}],
        )
    assert output.getvalue() == ""

    with pytest.raises(ValueError, match="non-standard JSON"):
        list(iter_jsonl(io.StringIO('{"value": NaN}\n')))


class _FailAfterPrefix(io.BytesIO):
    def __init__(self) -> None:
        super().__init__()
        self._calls = 0

    def write(self, data: Any) -> int:
        self._calls += 1
        if self._calls == 1:
            return super().write(bytes(data[:2]))
        return 0


@pytest.mark.parametrize("writer_type", [BoundedWriter, DigestWriter])
def test_stream_writer_state_tracks_only_committed_prefix(writer_type: type) -> None:
    output = _FailAfterPrefix()
    if writer_type is BoundedWriter:
        writer = writer_type(output, max_bytes=10)
    else:
        writer = writer_type(output, max_bytes=10)

    with pytest.raises(OSError, match="forward progress"):
        writer.write(b"abcd")

    assert output.getvalue() == b"ab"
    assert writer.bytes_written == 2
    if isinstance(writer, DigestWriter):
        assert writer.hexdigest == hashlib.sha256(b"ab").hexdigest()


def test_partition_overlap_matches_exhaustive_set_oracle() -> None:
    names = ("a", "b", "c")
    universe = (0, 1, 2)

    for mask in range(1 << (len(names) * len(universe))):
        groups: dict[str, tuple[int, ...]] = {}
        bit = 0
        for name in names:
            values: list[int] = []
            for value in universe:
                if mask & (1 << bit):
                    values.append(value)
                bit += 1
            groups[name] = tuple(values)

        expected: dict[tuple[str, str], frozenset[int]] = {}
        for left_index, left in enumerate(names):
            for right in names[left_index + 1 :]:
                overlap = set(groups[left]) & set(groups[right])
                if overlap:
                    expected[(left, right)] = frozenset(overlap)

        assert partition_overlaps(groups) == expected


def test_partition_boundaries_reject_invalid_shapes() -> None:
    with pytest.raises(TypeError, match="mapping"):
        PartitionManifest([("items", ["a"])])  # type: ignore[arg-type]

    with pytest.raises(ValueError, match="invalid item"):
        PartitionManifest({"items": (["unhashable"],)})  # type: ignore[list-item]

    with pytest.raises(ValueError, match="unhashable"):
        partition_overlaps({"items": (["x"],)})  # type: ignore[list-item]


def test_version_migration_rejects_invalid_envelope_boundary() -> None:
    with pytest.raises(SchemaMigrationError, match="mapping"):
        VersionedEnvelope.from_dict([])  # type: ignore[arg-type]

    migrator = SchemaMigrator()
    with pytest.raises(TypeError, match="VersionedEnvelope"):
        migrator.migrate(  # type: ignore[arg-type]
            {"schema": "demo"},
            target_version=2,
        )


def test_version_migration_stops_at_first_failure() -> None:
    calls: list[int] = []
    migrator = SchemaMigrator()

    def first(payload: dict[str, int]) -> dict[str, int]:
        calls.append(1)
        return {**payload, "one": 1}

    def fail(payload: dict[str, int]) -> dict[str, int]:
        calls.append(2)
        raise RuntimeError("migration failed")

    def never(payload: dict[str, int]) -> dict[str, int]:
        calls.append(3)
        return payload

    migrator.register("demo", 1, first)
    migrator.register("demo", 2, fail)
    migrator.register("demo", 3, never)

    with pytest.raises(RuntimeError, match="migration failed"):
        migrator.migrate(
            VersionedEnvelope("demo", 1, {}),
            target_version=4,
        )

    assert calls == [1, 2]


class _EntryPoint:
    def __init__(self, name: str, value: str, loaded: object) -> None:
        self.name = name
        self.value = value
        self._loaded = loaded

    def load(self) -> object:
        if isinstance(self._loaded, BaseException):
            raise self._loaded
        return self._loaded


def test_plugin_discovery_keeps_sibling_failures_isolated() -> None:
    entries = [
        _EntryPoint("z", "z:plugin", RuntimeError("secret")),
        _EntryPoint("a", "a:plugin", lambda: "loaded"),
        _EntryPoint("b", "b:plugin", ValueError("broken")),
    ]
    with patch("gunz_utils.plugins.entry_points", return_value=entries):
        results = discover_plugins("audit.plugins", instantiate=True)

    assert [item.info.name for item in results] == ["a", "b", "z"]
    assert results[0].plugin == "loaded"
    assert results[1].error == "ValueError"
    assert results[2].error == "RuntimeError"


def test_plugin_discovery_does_not_swallow_process_control_exceptions() -> None:
    entries = [_EntryPoint("stop", "stop:plugin", SystemExit(3))]
    with (
        patch("gunz_utils.plugins.entry_points", return_value=entries),
        pytest.raises(SystemExit) as captured,
    ):
        discover_plugins("audit.plugins")
    assert captured.value.code == 3


def test_content_store_rejects_symlinked_fanout_ancestor(
    tmp_path: Path,
) -> None:
    store = ContentAddressedStore(
        tmp_path / "store",
        fanout_levels=2,
        fanout_chars=2,
    )
    payload = b"fanout-symlink"
    digest = hashlib.sha256(payload).hexdigest()
    outside = tmp_path / "outside"
    outside.mkdir()
    first = store.root / digest[:2]
    try:
        first.symlink_to(outside, target_is_directory=True)
    except (NotImplementedError, OSError):
        pytest.skip("symlinks unavailable")

    with pytest.raises(ValueError, match="prefix directory"):
        store.put_bytes(payload)

    assert list(outside.iterdir()) == []


def test_content_store_rejects_symlink_root(tmp_path: Path) -> None:
    real = tmp_path / "real"
    real.mkdir()
    alias = tmp_path / "alias"
    try:
        alias.symlink_to(real, target_is_directory=True)
    except (NotImplementedError, OSError):
        pytest.skip("symlinks unavailable")

    with pytest.raises(ValueError, match="root"):
        ContentAddressedStore(alias)


@pytest.mark.parametrize(
    ("name", "value"),
    [
        ("replace", 1),
        ("verify", 1),
        ("fallback_copy", 1),
    ],
)
def test_content_store_materialize_requires_boolean_flags(
    tmp_path: Path,
    name: str,
    value: object,
) -> None:
    store = ContentAddressedStore(tmp_path / "store")
    artifact = store.put_bytes(b"value")
    kwargs = {name: value}

    with pytest.raises(ValueError, match=name):
        store.materialize(
            artifact.digest,
            tmp_path / "out",
            **kwargs,  # type: ignore[arg-type]
        )


def test_content_store_fallback_publication_is_verified(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    store = ContentAddressedStore(tmp_path / "store")
    original_replace = content_store_module.os.replace
    replaced: list[tuple[object, object]] = []

    def no_hardlinks(_source: object, _target: object) -> None:
        raise OSError("hard links unavailable")

    def record_replace(source: object, target: object) -> None:
        replaced.append((source, target))
        original_replace(source, target)

    monkeypatch.setattr(content_store_module.os, "link", no_hardlinks)
    monkeypatch.setattr(content_store_module.os, "replace", record_replace)

    artifact = store.put_bytes(b"fallback")
    assert replaced
    assert artifact.path.read_bytes() == b"fallback"
    assert store.verify(artifact.digest)


def test_atomic_write_replace_failure_preserves_old_target_and_cleans_temp(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    target = tmp_path / "value.txt"
    target.write_text("old", encoding="utf-8")

    def fail_replace(_source: object, _target: object) -> None:
        raise OSError("replace failed")

    monkeypatch.setattr(io_module.os, "replace", fail_replace)

    with pytest.raises(OSError, match="replace failed"):
        atomic_write(target, "new")

    assert target.read_text(encoding="utf-8") == "old"
    assert list(tmp_path.glob(".value.txt.*.tmp")) == []


def test_transactional_directory_cleans_failure_and_preserves_existing_target(
    tmp_path: Path,
) -> None:
    failed = tmp_path / "failed"
    with pytest.raises(RuntimeError, match="body failed"):
        with transactional_directory(failed) as staging:
            (staging / "partial").write_text("x", encoding="utf-8")
            raise RuntimeError("body failed")
    assert not failed.exists()
    assert not list(tmp_path.glob(".failed.*"))

    existing = tmp_path / "existing"
    existing.mkdir()
    (existing / "keep").write_text("old", encoding="utf-8")
    with pytest.raises(FileExistsError):
        with transactional_directory(existing) as staging:
            (staging / "new").write_text("new", encoding="utf-8")
    assert (existing / "keep").read_text(encoding="utf-8") == "old"


def test_transactional_directory_does_not_replace_dangling_symlink(
    tmp_path: Path,
) -> None:
    target = tmp_path / "published"
    missing = tmp_path / "missing"
    try:
        target.symlink_to(missing, target_is_directory=True)
    except (NotImplementedError, OSError):
        pytest.skip("symlinks unavailable")

    with pytest.raises(FileExistsError):
        with transactional_directory(target) as staging:
            (staging / "new").write_text("new", encoding="utf-8")

    assert target.is_symlink()


def test_worker_pipeline_respects_worker_bound() -> None:
    async def scenario() -> tuple[list[int], int]:
        active = 0
        peak = 0

        async def work(value: int) -> int:
            nonlocal active, peak
            active += 1
            peak = max(peak, active)
            try:
                await asyncio.sleep(0)
                return value * 2
            finally:
                active -= 1

        values = [
            value
            async for value in worker_map(
                work,
                range(20),
                workers=3,
                queue_size=2,
            )
        ]
        return values, peak

    values, peak = asyncio.run(scenario())
    assert sorted(values) == [value * 2 for value in range(20)]
    assert peak <= 3


def test_worker_pipeline_failure_cancels_inflight_sibling() -> None:
    async def scenario() -> bool:
        started = asyncio.Event()
        cancelled = asyncio.Event()

        async def work(value: int) -> int:
            if value == 0:
                started.set()
                try:
                    await asyncio.Event().wait()
                finally:
                    cancelled.set()
            await started.wait()
            raise RuntimeError("worker failed")

        with pytest.raises(RuntimeError, match="worker failed"):
            _ = [
                value
                async for value in worker_map(
                    work,
                    [0, 1],
                    workers=2,
                    queue_size=1,
                )
            ]

        return cancelled.is_set()

    assert asyncio.run(scenario())


def test_resource_groups_release_in_reverse_order_on_failure() -> None:
    events: list[str] = []

    @contextmanager
    def resource(name: str):
        events.append(f"enter:{name}")
        try:
            yield name
        finally:
            events.append(f"exit:{name}")

    with pytest.raises(RuntimeError, match="boom"):
        with ResourceGroup() as group:
            assert group.enter(resource("a")) == "a"
            assert group.enter(resource("b")) == "b"
            raise RuntimeError("boom")

    assert events == ["enter:a", "enter:b", "exit:b", "exit:a"]


def test_async_resource_groups_release_in_reverse_order() -> None:
    async def scenario() -> list[str]:
        events: list[str] = []

        @asynccontextmanager
        async def resource(name: str):
            events.append(f"enter:{name}")
            try:
                yield name
            finally:
                events.append(f"exit:{name}")

        async with AsyncResourceGroup() as group:
            assert await group.enter(resource("a")) == "a"
            assert await group.enter(resource("b")) == "b"

        return events

    assert asyncio.run(scenario()) == [
        "enter:a",
        "enter:b",
        "exit:b",
        "exit:a",
    ]


def test_termination_signal_validation_rejects_non_boolean_exit_policy() -> None:
    with pytest.raises(ValueError, match="exit_after"):
        install_termination_handler(
            lambda _signum: None,
            exit_after=1,  # type: ignore[arg-type]
        )


class _FailingLoop:
    def __init__(self) -> None:
        self.added: list[int] = []
        self.removed: list[int] = []

    def add_signal_handler(
        self,
        signum: int,
        _callback: Any,
        *_args: Any,
    ) -> None:
        self.added.append(signum)
        if len(self.added) == 2:
            raise RuntimeError("registration failed")

    def remove_signal_handler(self, signum: int) -> bool:
        self.removed.append(signum)
        return True


def test_async_signal_partial_registration_restores_reverse_order() -> None:
    loop = _FailingLoop()
    previous = {
        signal.SIGINT: "previous-int",
        signal.SIGTERM: "previous-term",
    }

    with (
        patch(
            "gunz_utils.signals.signal.getsignal",
            side_effect=lambda signum: previous[signum],
        ),
        patch("gunz_utils.signals.signal.signal") as restore,
        pytest.raises(RuntimeError, match="registration failed"),
    ):
        install_async_signal_handlers(
            lambda _signum: None,
            signums=(signal.SIGINT, signal.SIGTERM),
            loop=loop,  # type: ignore[arg-type]
        )

    assert loop.removed == [signal.SIGINT]
    assert [call.args[0] for call in restore.call_args_list] == [
        signal.SIGTERM,
        signal.SIGINT,
    ]
