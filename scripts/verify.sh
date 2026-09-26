#!/usr/bin/env bash
set -euo pipefail

python -m compileall -q src tests
ruff check src tests benchmarks
mypy src/gunz_utils
pytest -q
