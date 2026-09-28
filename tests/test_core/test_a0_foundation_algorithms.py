"""Proof tests for algorithm families that entered the audit as A0."""

from __future__ import annotations

import math
import os
from pathlib import Path

import pytest

from gunz_utils.benchmark.io import GitInfo
from gunz_utils.buffers import as_readonly_view, dispatch
from gunz_utils.collections import group_by, index_by, partition, unique
from gunz_utils.config import env_overrides, merge_configs
from gunz_utils.faults import FailAfter, FaultSequence, InjectedFault
from gunz_utils.formatting import format_bytes, format_count, format_duration
from gunz_utils.identifiers import deterministic_id, short_id
from gunz_utils.network import build_network_uri, tcp_reachable
from gunz_utils.provenance import ExecutionManifest, RuntimeProvenance
from gunz_utils.security import NameAccessPolicy, open_path_under_base, safe_path_join
from gunz_utils.subprocess import CommandResult
from gunz_utils.sync import _normalize_rsync_source, rsync_mirror


def test_collection_transforms_preserve_declared_order_and_duplicate_semantics() -> None:
    assert unique([3, 1, 3, 2, 1]) == [3, 1, 2]
    assert unique([[1], [1], [2]]) == [[1], [2]]
    assert unique(["aa", "b", "cc"], key=len) == ["aa", "b"]
    assert group_by(["a", "bb", "c"], len) == {1: ["a", "c"], 2: ["bb"]}
    assert index_by(["a", "b"], lambda _item: "same") == {"same": "b"}
    assert partition(range(5), lambda value: value % 2 == 0) == (
        [0, 2, 4],
        [1, 3],
    )


@pytest.mark.parametrize("value", [math.nan, math.inf, -math.inf, True])
def test_formatters_reject_non_finite_or_boolean_real_values(value: object) -> None:
    with pytest.raises(ValueError):
        format_bytes(value)  # type: ignore[arg-type]
    with pytest.raises(ValueError):
        format_duration(value)  # type: ignore[arg-type]


@pytest.mark.parametrize("precision", [-1, 21, True, 1.5])
def test_formatters_reject_invalid_precision(precision: object) -> None:
    with pytest.raises(ValueError):
        format_bytes(1_000, precision=precision)  # type: ignore[arg-type]
    with pytest.raises(ValueError):
        format_count(1_000, precision=precision)  # type: ignore[arg-type]


def test_formatting_boundaries_and_arbitrary_size_integer_count() -> None:
    assert format_bytes(999) == "999 B"
    assert format_bytes(1_000) == "1.0 KB"
    assert format_bytes(1_024, binary=True) == "1.0 KiB"
    assert format_duration(0.5) == "500ms"
    assert format_duration(3_661) == "1h 1m 1s"
    assert format_count(999) == "999"
    assert format_count(1_000) == "1.0K"
    assert format_count(10**400).endswith("T")


def test_identifier_contracts_are_deterministic_and_strict() -> None:
    assert deterministic_id("namespace", "value") == deterministic_id(
        "namespace",
        "value",
    )
    assert short_id("value", length=4) == short_id("value", length=64)[:4]
    for length in (3, 65, True):
        with pytest.raises(ValueError):
            short_id("value", length=length)
    with pytest.raises(TypeError):
        deterministic_id("namespace", 1)  # type: ignore[arg-type]
    with pytest.raises(TypeError):
        short_id(1)  # type: ignore[arg-type]


def test_configuration_precedence_is_recursive_and_inputs_are_not_mutated() -> None:
    low = {"db": {"host": "a", "port": 1}, "mode": "low"}
    high = {"db": {"port": 2}}
    merged = merge_configs(low, high)
    assert merged == {"db": {"host": "a", "port": 2}, "mode": "low"}
    assert low == {"db": {"host": "a", "port": 1}, "mode": "low"}
    assert high == {"db": {"port": 2}}

    assert env_overrides(
        {"APP_DB__HOST": "localhost", "OTHER_DB__HOST": "ignored"},
        prefix="APP",
    ) == {"db": {"host": "localhost"}}


@pytest.mark.parametrize(
    ("prefix", "separator"),
    [("", "__"), ("_", "__"), ("APP", ""), ("APP", None)],
)
def test_environment_override_rejects_malformed_path_configuration(
    prefix: object,
    separator: object,
) -> None:
    with pytest.raises(ValueError):
        env_overrides(
            {"APP_DB__HOST": "localhost"},
            prefix=prefix,  # type: ignore[arg-type]
            separator=separator,  # type: ignore[arg-type]
        )

    with pytest.raises(ValueError):
        env_overrides(
            {"APP_DB____HOST": "localhost"},
            prefix="APP",
        )


def test_readonly_view_is_zero_copy_and_dispatch_is_exact() -> None:
    source = bytearray(b"abc")
    view = as_readonly_view(source)
    assert view.readonly
    assert bytes(view) == b"abc"
    source[0] = ord("z")
    assert bytes(view) == b"zbc"
    with pytest.raises(TypeError):
        view[0] = 1

    reference = lambda: "reference"
    accelerated = lambda: "accelerated"
    assert dispatch(reference) is reference
    assert dispatch(reference, accelerated) is accelerated


def test_fault_injectors_have_exact_one_based_transition_semantics() -> None:
    failure = FailAfter(2, lambda: InjectedFault("boom"))
    failure()
    failure()
    with pytest.raises(InjectedFault, match="boom"):
        failure()
    assert failure.calls == 3

    sequence = FaultSequence({2, 4})
    sequence.check(lambda: InjectedFault("x"))
    with pytest.raises(InjectedFault):
        sequence.check(lambda: InjectedFault("x"))
    sequence.check(lambda: InjectedFault("x"))
    with pytest.raises(InjectedFault):
        sequence.check(lambda: InjectedFault("x"))
    assert sequence.calls == 4


def test_runtime_provenance_and_manifest_copy_caller_owned_mappings() -> None:
    environment = {"VISIBLE": "yes"}
    runtime = RuntimeProvenance(
        captured_at="2026-09-28T00:00:00+00:00",
        python_version="3.11",
        python_implementation="CPython",
        platform="test",
        machine="test",
        executable="/python",
        environment=environment,
    )
    environment["VISIBLE"] = "changed"
    assert runtime.environment["VISIBLE"] == "yes"

    config = {"mode": "audit"}
    manifest = ExecutionManifest(
        created_at=runtime.captured_at,
        run_id="run",
        runtime=runtime,
        git=GitInfo(None, None, None),
        config=config,
    )
    config["mode"] = "changed"
    assert manifest.config["mode"] == "audit"


def test_network_uri_handles_ipv6_idna_and_userinfo() -> None:
    assert build_network_uri(
        "HTTPS",
        "2001:db8::1",
        port=443,
        username="a b",
        password="p@ss",
        path="x y",
        query={"q": "a b"},
    ) == "https://a%20b:p%40ss@[2001:db8::1]:443/x%20y?q=a+b"
    assert build_network_uri("https", "münich.example") == (
        "https://xn--mnich-kva.example"
    )


@pytest.mark.parametrize("timeout", [math.nan, math.inf, -math.inf, True, 0])
def test_tcp_reachability_rejects_invalid_timeout(timeout: object) -> None:
    with pytest.raises(ValueError):
        tcp_reachable("localhost", 80, timeout=timeout)  # type: ignore[arg-type]


def test_name_policy_deny_precedence_and_allowlist() -> None:
    policy = NameAccessPolicy(
        allowed=frozenset({"read", "write"}),
        denied=frozenset({"write"}),
    )
    assert policy.allows("read")
    assert not policy.allows("write")
    assert not policy.allows("admin")
    with pytest.raises(PermissionError):
        policy.check("write")
    with pytest.raises(PermissionError):
        policy.check("admin")


def test_safe_path_join_rejects_parent_escape(tmp_path: Path) -> None:
    base = tmp_path / "base"
    base.mkdir()
    with pytest.raises(ValueError, match="outside"):
        safe_path_join(str(base), "..", "escape.txt")


@pytest.mark.skipif(
    os.name != "posix" or not hasattr(os, "O_NOFOLLOW"),
    reason="O_NOFOLLOW contract is POSIX-specific",
)
def test_open_path_under_base_rejects_final_symlink(tmp_path: Path) -> None:
    base = tmp_path / "base"
    base.mkdir()
    target = base / "target.txt"
    target.write_text("safe", encoding="utf-8")
    alias = base / "alias.txt"
    alias.symlink_to(target)

    with pytest.raises(OSError):
        open_path_under_base(str(base), "alias.txt", mode="rb")


def test_sync_source_normalization_preserves_remote_and_local_semantics(
    tmp_path: Path,
) -> None:
    assert _normalize_rsync_source("host:/srv/data/") == "host:/srv/data/"
    local = tmp_path / "source"
    local.mkdir()
    assert _normalize_rsync_source(local) == f"{local.resolve()}/"


def test_rsync_completion_marker_is_success_only(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import gunz_utils.sync as sync_module

    source = tmp_path / "source"
    target = tmp_path / "target"
    source.mkdir()
    monkeypatch.setattr(sync_module.shutil, "which", lambda _name: "/usr/bin/rsync")

    result = CommandResult(("rsync",), 0, "", "", 0.1)
    monkeypatch.setattr(sync_module, "run_command", lambda *_a, **_kw: result)
    completed = rsync_mirror(source, target, lock=False)
    assert completed.completion_marker is not None
    assert completed.completion_marker.read_text(encoding="utf-8") == "complete\n"

    def fail(*_args: object, **_kwargs: object) -> CommandResult:
        raise RuntimeError("transfer failed")

    monkeypatch.setattr(sync_module, "run_command", fail)
    with pytest.raises(RuntimeError, match="transfer failed"):
        rsync_mirror(source, target, lock=False)
    assert completed.completion_marker is not None
    assert not completed.completion_marker.exists()
