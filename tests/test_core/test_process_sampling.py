"""Deterministic process sampling checks for exit races and memory cadence."""

import math
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

from gunz_utils.benchmark.process import (
    ProcessSample,
    _memory_rollup,
    _parse_proc_stat,
    profile_command,
)


def _sample(process_count: int = 1) -> ProcessSample:
    return ProcessSample(
        elapsed=0.1,
        process_count=process_count,
        cpu_user_seconds=0.0,
        cpu_system_seconds=0.0,
        rss_bytes=1024,
        pss_bytes=None,
        private_bytes=None,
        read_bytes=0,
        write_bytes=0,
        threads=1,
        minor_faults=0,
        major_faults=0,
        voluntary_context_switches=0,
        involuntary_context_switches=0,
        processes=(),
    )


class TestProcessSampling(unittest.TestCase):
    """Exercise process races without relying on operating system timing."""

    def test_proc_stat_parser_preserves_spaces_and_parentheses(self) -> None:
        text = (
            "123 (worker pool (x)) "
            "S 1 0 0 0 0 0 7 0 9 0 11 13 0 0 0 0 4 0 0 0 5"
        )
        pid, command, fields = _parse_proc_stat(text)
        self.assertEqual(pid, 123)
        self.assertEqual(command, "worker pool (x)")
        self.assertEqual(fields[3], "1")
        self.assertEqual(fields[13], "11")
        self.assertEqual(fields[14], "13")
        self.assertEqual(fields[19], "4")
        self.assertEqual(fields[23], "5")


    def test_rollup_ignores_mapping_header(self) -> None:
        """Real Linux rollups include a nonnumeric mapping header."""
        text = (
            "00400000-7fffffff ---p 00000000 00:00 0 [rollup]\n"
            "Pss: 12 kB\nPrivate_Clean: 3 kB\nPrivate_Dirty: 4 kB\n"
        )
        with patch.object(Path, "read_text", return_value=text):
            self.assertEqual(
                _memory_rollup(Path("/proc/1/smaps_rollup")), (12288, 7168)
            )

    def test_rollup_process_exit_is_unknown_memory(self) -> None:
        """A process may exit after its rollup path is discovered."""
        with patch.object(Path, "read_text", side_effect=ProcessLookupError):
            self.assertEqual(_memory_rollup(Path("/proc/1/smaps_rollup")), (None, None))

    def test_sparse_memory_and_no_post_exit_sample(self) -> None:
        """Detailed memory is sampled periodically without inventing a tail."""
        process = Mock(pid=123, returncode=0)
        process.poll.side_effect = [None] * 6 + [0]
        with (
            patch(
                "gunz_utils.benchmark.process.subprocess.Popen", return_value=process
            ),
            patch("gunz_utils.benchmark.process.Path.exists", return_value=True),
            patch("gunz_utils.benchmark.process.time.sleep"),
            patch(
                "gunz_utils.benchmark.process._linux_snapshot", return_value=_sample()
            ) as snapshot,
        ):
            profile = profile_command(
                ["command"], memory_detail="full", detailed_memory_every=5
            )
        self.assertEqual(len(profile.samples), 6)
        self.assertEqual(
            [call.kwargs["memory_detail"] for call in snapshot.call_args_list],
            ["full", "rss", "rss", "rss", "rss", "full"],
        )

    def test_empty_snapshot_from_exit_race_is_discarded(self) -> None:
        """A process disappearing during observation must not add an empty tail."""
        process = Mock(pid=123, returncode=0)
        process.poll.side_effect = [None, None, 0]
        with (
            patch(
                "gunz_utils.benchmark.process.subprocess.Popen", return_value=process
            ),
            patch("gunz_utils.benchmark.process.Path.exists", return_value=True),
            patch("gunz_utils.benchmark.process.time.sleep"),
            patch(
                "gunz_utils.benchmark.process._linux_snapshot",
                side_effect=[_sample(), _sample(0)],
            ),
        ):
            profile = profile_command(["command"])
        self.assertEqual(len(profile.samples), 1)
        self.assertEqual(profile.samples[-1].process_count, 1)

    def test_invalid_options_do_not_launch_command(self) -> None:
        """Validate sampling options before creating a subprocess."""
        for options in (
            {"memory_detail": "unknown"},
            {"detailed_memory_every": 0},
            {"detailed_memory_every": -1},
            {"detailed_memory_every": 1.5},
            {"interval": math.nan},
            {"interval": math.inf},
            {"interval": True},
        ):
            with self.subTest(options=options):
                with patch("gunz_utils.benchmark.process.subprocess.Popen") as launch:
                    with self.assertRaises(ValueError):
                        profile_command(["command"], **options)
                    launch.assert_not_called()


    def test_sampler_failure_terminates_launched_process(self) -> None:
        process = Mock(pid=123, returncode=None)
        process.poll.return_value = None
        process.wait.return_value = 0
        with (
            patch(
                "gunz_utils.benchmark.process.subprocess.Popen",
                return_value=process,
            ),
            patch(
                "gunz_utils.benchmark.process.Path.exists",
                return_value=True,
            ),
            patch(
                "gunz_utils.benchmark.process._linux_snapshot",
                side_effect=RuntimeError("sample failed"),
            ),
        ):
            with self.assertRaisesRegex(RuntimeError, "sample failed"):
                profile_command(["command"])
        process.terminate.assert_called_once()
        process.wait.assert_called()
