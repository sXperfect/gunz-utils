#!/bin/bash
set -e

# Ensure we are in the project root
cd "$(dirname "$0")/.."

# Install docs dependencies if needed (assuming pip is available)
# pip install .[docs]

# Clean build directory
rm -rf docs/_build

# Build docs
sphinx-build -b html docs docs/_build/html

echo "Documentation built in docs/_build/html"
