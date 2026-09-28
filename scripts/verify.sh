#!/usr/bin/env bash
# Local aggregate verification entry point.
# The hosted workflow additionally supplies --compat-python python3.12.
set -euo pipefail

args=(--summary-json tmp/ci-summary.json)
if command -v python3.12 >/dev/null 2>&1; then
    args+=(--compat-python python3.12)
fi

python scripts/audit_ci.py "${args[@]}"
