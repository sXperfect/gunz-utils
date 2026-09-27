"""Command-line interface for cross-project benchmark utilities."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from .compare import compare_results
from .io import load_result
from .process import profile_command


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="gunz-benchmark")
    commands = parser.add_subparsers(dest="command", required=True)

    compare = commands.add_parser("compare")
    compare.add_argument("baseline")
    compare.add_argument("candidate")
    compare.add_argument("--median-threshold", type=float, default=0.05)
    compare.add_argument("--p95-threshold", type=float, default=0.10)

    profile = commands.add_parser("profile")
    profile.add_argument("--output", required=True)
    profile.add_argument("--interval", type=float, default=0.02)
    profile.add_argument("program", nargs=argparse.REMAINDER)

    args = parser.parse_args(argv)
    if args.command == "compare":
        result = compare_results(
            load_result(args.baseline),
            load_result(args.candidate),
            median_threshold=args.median_threshold,
            p95_threshold=args.p95_threshold,
        )
        print(json.dumps(result.__dict__, indent=2, sort_keys=True))
        return 1 if result.regressed else 0

    if not args.program:
        parser.error("profile requires a command after options")
    profile_result = profile_command(args.program, interval=args.interval)
    Path(args.output).write_text(
        json.dumps(profile_result.to_dict(), indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return profile_result.returncode


if __name__ == "__main__":
    raise SystemExit(main())
