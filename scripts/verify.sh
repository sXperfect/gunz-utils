#!/usr/bin/env bash
# Local verification entry point mirroring the intended hosted gates.
# Delegates to scripts/ci.py so the local surface always matches CI.
set -euo pipefail

python scripts/ci.py all
