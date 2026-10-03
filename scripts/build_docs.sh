#!/bin/bash
set -e

echo "========================================"
echo "      Building Documentation (Utils)"
echo "========================================"

# Get the project root directory
PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
DOCS_DIR="$PROJECT_ROOT/docs"
SOURCE_DIR="$DOCS_DIR/source"
SRC_DIR="$PROJECT_ROOT/src/gunz_utils"

echo "Project Root: $PROJECT_ROOT"
echo "Source Dir:   $SOURCE_DIR"

# 1. Clean previous build
echo "-> Cleaning previous build..."
rm -rf "$DOCS_DIR/_build"

# 2. Build HTML
echo "-> Building HTML..."
cd "$SOURCE_DIR"
if command -v sphinx-build >/dev/null 2>&1; then
    sphinx-build -b html -W . "$DOCS_DIR/_build/html"
elif [ -n "${PYTHON:-}" ] && "$PYTHON" -m sphinx.cmd.build --version >/dev/null 2>&1; then
    "$PYTHON" -m sphinx.cmd.build -b html -W . "$DOCS_DIR/_build/html"
else
    python3 -m sphinx.cmd.build -b html -W . "$DOCS_DIR/_build/html"
fi

echo "========================================"
echo "Build Complete!"
echo "Open: file://$DOCS_DIR/_build/html/index.html"
echo "========================================"
