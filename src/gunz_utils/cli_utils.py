"""Zero-dependency command-line argument parser for options, flags, and help formatting.
"""

# =============================================================================
# STANDARD LIBRARY IMPORTS
# =============================================================================

from __future__ import annotations

import sys
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Any


@dataclass(slots=True)
class _ArgRule:
    name: str
    short: str | None
    is_flag: bool
    type: type
    default: Any
    help: str
    nargs: str  #? "1", "?", "*", "+"


class SimpleArgParser:
    """Lightweight command-line parser with zero third-party dependencies."""

    def __init__(self,
        prog: str = "",
        description: str = "",
    ) -> None:
        self.prog = prog or (sys.argv[0] if sys.argv else "app")
        self.description = description
        self._flags_and_options: dict[str, _ArgRule] = {}
        self._short_map: dict[str, str] = {}
        self._positionals: list[_ArgRule] = []

    def add_flag(self,
        name: str,
        short: str | None = None,
        default: bool = False,
        help: str = "",
    ) -> SimpleArgParser:
        """Register a boolean flag (e.g. --verbose or -v)."""
        clean_name = name.lstrip("-")
        rule = _ArgRule(
            name=clean_name,
            short=short.lstrip("-") if short else None,
            is_flag=True,
            type=bool,
            default=default,
            help=help,
            nargs="0",
        )
        self._flags_and_options[clean_name] = rule
        if rule.short:
            self._short_map[rule.short] = clean_name
        return self

    def add_option(self,
        name: str,
        short: str | None = None,
        type: type = str,
        default: Any = None,
        help: str = "",
    ) -> SimpleArgParser:
        """Register a key-value option (e.g. --port 8080 or -p 8080)."""
        clean_name = name.lstrip("-")
        rule = _ArgRule(
            name=clean_name,
            short=short.lstrip("-") if short else None,
            is_flag=False,
            type=type,
            default=default,
            help=help,
            nargs="1",
        )
        self._flags_and_options[clean_name] = rule
        if rule.short:
            self._short_map[rule.short] = clean_name
        return self

    def add_argument(self,
        name: str,
        nargs: str = "1",
        default: Any = None,
        help: str = "",
    ) -> SimpleArgParser:
        """Register a positional argument."""
        rule = _ArgRule(
            name=name,
            short=None,
            is_flag=False,
            type=str,
            default=default,
            help=help,
            nargs=nargs,
        )
        self._positionals.append(rule)
        return self

    def parse_args(self,
        args: Sequence[str] | None = None,
    ) -> dict[str, Any]:
        """Parse arguments into a dictionary of names and values."""
        argv = list(sys.argv[1:] if args is None else args)
        result: dict[str, Any] = {
            r.name: r.default for r in self._flags_and_options.values()
        }
        for pos in self._positionals:
            result[pos.name] = [] if pos.nargs in ("*", "+") else pos.default

        positional_vals: list[str] = []
        i = 0
        while i < len(argv):
            arg = argv[i]
            if arg in ("-h", "--help"):
                print(self.format_help())
                sys.exit(0)

            if arg.startswith("--"):
                key = arg[2:]
                val: Any = None
                if "=" in key:
                    key, val = key.split("=", 1)
                rule = self._flags_and_options.get(key)
                if rule is None:
                    raise ValueError(f"unknown option: --{key}")
                if rule.is_flag:
                    result[key] = not rule.default if val is None else bool(val)
                else:
                    if val is None:
                        i += 1
                        if i >= len(argv):
                            raise ValueError(f"option --{key} requires an argument")
                        val = argv[i]
                    result[key] = rule.type(val)
            elif arg.startswith("-") and len(arg) > 1:
                short_key = arg[1:]
                short_option = self._short_map.get(short_key)
                if short_option is None:
                    raise ValueError(f"unknown short option: -{short_key}")
                rule = self._flags_and_options[short_option]
                if rule.is_flag:
                    result[short_option] = not rule.default
                else:
                    i += 1
                    if i >= len(argv):
                        raise ValueError(f"option -{short_key} requires an argument")
                    result[short_option] = rule.type(argv[i])
            else:
                positional_vals.append(arg)
            i += 1

        #? Match positionals
        pos_idx = 0
        for rule in self._positionals:
            if rule.nargs == "1":
                if pos_idx < len(positional_vals):
                    result[rule.name] = positional_vals[pos_idx]
                    pos_idx += 1
            elif rule.nargs in ("*", "+"):
                result[rule.name] = positional_vals[pos_idx:]
                pos_idx = len(positional_vals)

        return result

    def format_help(self) -> str:
        """Format an informative help message."""
        lines = [f"Usage: {self.prog} [OPTIONS]"]
        if self._positionals:
            lines[0] += " " + " ".join(f"<{p.name}>" for p in self._positionals)
        if self.description:
            lines.append(f"\n{self.description}\n")

        lines.append("Options:")
        for rule in sorted(self._flags_and_options.values(), key=lambda r: r.name):
            short_str = f"-{rule.short}, " if rule.short else "    "
            flag_str = f"{short_str}--{rule.name}"
            help_str = f": {rule.help}" if rule.help else ""
            default_str = (
                f" (default: {rule.default})" if rule.default is not None else ""
            )
            lines.append(f"  {flag_str:<25} {help_str}{default_str}")

        return "\n".join(lines)


__all__ = ["SimpleArgParser"]
