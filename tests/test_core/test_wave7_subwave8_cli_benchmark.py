"""Tests for Wave 7 Sub-Wave 8: Lightweight CLI Utilities & Benchmark Summaries."""

from gunz_utils.benchmark import (
    export_benchmark_csv,
    export_benchmark_json,
    format_summary_matrix,
)
from gunz_utils.cli_utils import SimpleArgParser


def test_simple_arg_parser_flags_and_options():
    parser = SimpleArgParser(prog="tool", description="Test CLI Tool")
    parser.add_flag("verbose", short="v", help="Verbose mode")
    parser.add_option("port", short="p", type=int, default=8000, help="Listen port")
    parser.add_argument("filename", help="Input file")

    # Long flag and option
    res = parser.parse_args(["--verbose", "--port", "9090", "input.txt"])
    assert res["verbose"] is True
    assert res["port"] == 9090
    assert res["filename"] == "input.txt"

    # Short flag and option with =
    res2 = parser.parse_args(["-v", "--port=3000", "output.txt"])
    assert res2["verbose"] is True
    assert res2["port"] == 3000
    assert res2["filename"] == "output.txt"

    # Default values
    res3 = parser.parse_args(["just_file.txt"])
    assert res3["verbose"] is False
    assert res3["port"] == 8000
    assert res3["filename"] == "just_file.txt"

    help_text = parser.format_help()
    assert "Usage: tool [OPTIONS] <filename>" in help_text
    assert "--verbose" in help_text
    assert "--port" in help_text


def test_benchmark_export_and_matrix():
    data = [
        {"benchmark": "bm1", "ops_per_sec": 1000, "duration": 0.05},
        {"benchmark": "bm2", "ops_per_sec": 2000, "duration": 0.02},
    ]

    csv_out = export_benchmark_csv(data)
    assert "benchmark,ops_per_sec,duration" in csv_out
    assert "bm1,1000,0.05" in csv_out

    json_out = export_benchmark_json(data)
    assert '"benchmark": "bm1"' in json_out

    matrix = format_summary_matrix(data)
    assert "bm1" in matrix
    assert "ops_per_sec" in matrix
