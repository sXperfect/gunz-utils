"""Proof tests for benchmark/storage families that entered the audit as A0."""

from __future__ import annotations

import json
import math
from pathlib import Path
from types import SimpleNamespace

import pytest

import gunz_utils.benchmark.overhead as overhead_module
import gunz_utils.benchmark.perf as perf_module
from gunz_utils.benchmark.artifacts import register_artifact, verify_artifact
from gunz_utils.benchmark.export import save_process_csv
from gunz_utils.benchmark.io import save_result
from gunz_utils.benchmark.overhead import measure_runner_overhead
from gunz_utils.benchmark.perf import perf_record, perf_stat
from gunz_utils.benchmark.performance import PerformanceRun
from gunz_utils.benchmark.plot import _cpu_cores, plot_process_samples
from gunz_utils.benchmark.process import ProcessProfile, ProcessSample
from gunz_utils.benchmark.report import format_process_profile
from gunz_utils.benchmark.result import BenchmarkResult, BenchmarkStats, SystemInfo
from gunz_utils.benchmark.run_directory import save_run_directory
from gunz_utils.benchmark.safe_io import load_result_checked
from gunz_utils.benchmark.worker import WorkerResult, run_python_worker, worker_json


def _result() -> BenchmarkResult:
    return BenchmarkResult(
        name="audit",
        samples=(1.0, 2.0),
        stats=BenchmarkStats(
            minimum=1.0,
            median=1.5,
            mean=1.5,
            p95=1.95,
            p99=1.99,
            maximum=2.0,
            stddev=0.5,
            ops_per_second=2.0 / 3.0,
        ),
        warmup=1,
        iterations=2,
        system=SystemInfo(
            python="3.11",
            platform="test",
            machine="test",
            processor="test",
            cpu_count=1,
        ),
    )


def _profile() -> ProcessProfile:
    first = ProcessSample(
        elapsed=1.0,
        process_count=1,
        cpu_user_seconds=0.2,
        cpu_system_seconds=0.1,
        rss_bytes=100,
        pss_bytes=90,
        private_bytes=80,
        read_bytes=10,
        write_bytes=20,
        threads=2,
        minor_faults=3,
        major_faults=0,
        voluntary_context_switches=4,
        involuntary_context_switches=1,
        processes=(),
    )
    second = ProcessSample(
        elapsed=2.0,
        process_count=1,
        cpu_user_seconds=0.6,
        cpu_system_seconds=0.2,
        rss_bytes=120,
        pss_bytes=100,
        private_bytes=90,
        read_bytes=30,
        write_bytes=40,
        threads=2,
        minor_faults=5,
        major_faults=0,
        voluntary_context_switches=6,
        involuntary_context_switches=1,
        processes=(),
    )
    return ProcessProfile(
        args=("command",),
        returncode=0,
        wall_seconds=2.0,
        peak_rss_bytes=120,
        peak_pss_bytes=100,
        peak_private_bytes=90,
        cpu_user_seconds=0.6,
        cpu_system_seconds=0.2,
        read_bytes=30,
        write_bytes=40,
        peak_process_count=1,
        peak_threads=2,
        minor_faults=5,
        major_faults=0,
        voluntary_context_switches=6,
        involuntary_context_switches=1,
        samples=(first, second),
    )


def test_safe_result_loader_round_trips_valid_result(tmp_path: Path) -> None:
    path = tmp_path / "result.json"
    expected = _result()
    save_result(expected, path)
    assert load_result_checked(path) == expected


@pytest.mark.parametrize("max_bytes", [0, -1, True, 1.5])
def test_safe_result_loader_rejects_invalid_size_limit(
    tmp_path: Path,
    max_bytes: object,
) -> None:
    path = tmp_path / "result.json"
    path.write_text("{}", encoding="utf-8")
    with pytest.raises(ValueError):
        load_result_checked(path, max_bytes=max_bytes)  # type: ignore[arg-type]


def test_safe_result_loader_rejects_oversized_and_non_finite_samples(
    tmp_path: Path,
) -> None:
    path = tmp_path / "result.json"
    save_result(_result(), path)
    with pytest.raises(ValueError, match="size limit"):
        load_result_checked(path, max_bytes=8)

    data = _result().to_dict()
    data["samples"] = [math.nan, 2.0]
    path.write_text(json.dumps(data), encoding="utf-8")
    with pytest.raises(ValueError, match="sample"):
        load_result_checked(path)


def test_safe_result_loader_rejects_boolean_schema_and_iteration_fields(
    tmp_path: Path,
) -> None:
    path = tmp_path / "result.json"
    for key in ("schema_version", "iterations", "warmup"):
        data = _result().to_dict()
        data[key] = True
        path.write_text(json.dumps(data), encoding="utf-8")
        with pytest.raises(ValueError):
            load_result_checked(path)


def test_artifact_registry_detects_tampering(tmp_path: Path) -> None:
    artifact = tmp_path / "artifact.bin"
    artifact.write_bytes(b"original")
    run = register_artifact(
        PerformanceRun("run", SystemInfo.capture()),
        artifact,
        kind="data",
    )
    registered = run.artifacts[0]
    assert verify_artifact(registered)
    artifact.write_bytes(b"changed")
    assert not verify_artifact(registered)


def test_artifact_registry_rejects_symlink(tmp_path: Path) -> None:
    target = tmp_path / "target.bin"
    target.write_bytes(b"value")
    link = tmp_path / "link.bin"
    try:
        link.symlink_to(target)
    except (NotImplementedError, OSError):
        pytest.skip("symlinks unavailable")

    with pytest.raises(ValueError, match="non-symlink"):
        register_artifact(
            PerformanceRun("run", SystemInfo.capture()),
            link,
            kind="data",
        )


def test_run_directory_resolves_artifact_name_collisions(tmp_path: Path) -> None:
    left = tmp_path / "left"
    right = tmp_path / "right"
    left.mkdir()
    right.mkdir()
    first = left / "same.bin"
    second = right / "same.bin"
    first.write_bytes(b"first")
    second.write_bytes(b"second")

    run = PerformanceRun("run", SystemInfo.capture())
    run = register_artifact(run, first, kind="data")
    run = register_artifact(run, second, kind="data")
    saved = save_run_directory(run, tmp_path / "saved")

    names = [Path(item.path).name for item in saved.artifacts]
    assert names == ["same.bin", "same-1.bin"]
    assert all(verify_artifact(item) for item in saved.artifacts)
    assert (tmp_path / "saved" / "run.json").is_file()


def test_perf_stat_parses_non_finite_counter_as_unknown(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(perf_module, "perf_available", lambda: True)

    def fake_run(command: list[str], **_kwargs: object) -> SimpleNamespace:
        output = Path(command[command.index("-o") + 1])
        output.write_text("nan,,cycles\n123,,instructions\n", encoding="utf-8")
        return SimpleNamespace(returncode=0)

    monkeypatch.setattr(perf_module.subprocess, "run", fake_run)
    result = perf_stat(["command"], events=("cycles",))
    assert result.counters[0].event == "cycles"
    assert result.counters[0].value is None
    assert result.counters[1].value == 123.0


@pytest.mark.parametrize("events", [("",), (1,)])
def test_perf_stat_rejects_invalid_event_names(events: object) -> None:
    with pytest.raises(ValueError):
        perf_stat(["command"], events=events)  # type: ignore[arg-type]


@pytest.mark.parametrize("frequency", [0, -1, True, 1.5])
def test_perf_record_rejects_invalid_frequency(
    tmp_path: Path,
    frequency: object,
) -> None:
    with pytest.raises(ValueError):
        perf_record(
            ["command"],
            tmp_path / "perf.data",
            frequency=frequency,  # type: ignore[arg-type]
        )


@pytest.mark.parametrize("timeout", [0, -1, math.nan, math.inf, True])
def test_worker_rejects_invalid_timeout(timeout: object) -> None:
    with pytest.raises(ValueError):
        run_python_worker("module", timeout=timeout)  # type: ignore[arg-type]


def test_worker_protocol_requires_strict_json_and_success() -> None:
    assert worker_json(WorkerResult(0, '{"value": 1}', "")) == {"value": 1}
    with pytest.raises(ValueError, match="non-standard JSON"):
        worker_json(WorkerResult(0, '{"value": NaN}', ""))
    with pytest.raises(RuntimeError, match="exit code 2"):
        worker_json(WorkerResult(2, "", "failed"))


def test_reporting_export_and_process_plot_transform(tmp_path: Path) -> None:
    profile = _profile()
    report = format_process_profile(profile)
    assert "Average CPU cores" in report
    assert "120" in report

    path = tmp_path / "profile.csv"
    save_process_csv(profile, path)
    csv_text = path.read_text(encoding="utf-8")
    assert "elapsed,process_count" in csv_text
    assert "120" in csv_text

    times, values = _cpu_cores(profile)
    assert times == [2.0]
    assert values == pytest.approx([0.5])

    with pytest.raises(ValueError, match="unsupported"):
        plot_process_samples(profile, "not-a-metric")


def test_overhead_probe_rejects_boolean_iterations() -> None:
    with pytest.raises(ValueError):
        measure_runner_overhead(iterations=True)


def test_overhead_probe_handles_zero_timer_resolution(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(overhead_module.time, "perf_counter", lambda: 1.0)
    fake = SimpleNamespace(stats=SimpleNamespace(mean=0.5))
    monkeypatch.setattr(overhead_module, "benchmark", lambda *_a, **_kw: fake)
    result = measure_runner_overhead(iterations=2)
    assert result.timer_pair_seconds == 0
    assert math.isinf(result.ratio)
