#!/usr/bin/env bash
# Render the architecture diagram to PNG and SVG. Requires Graphviz (`dot`).
set -euo pipefail
cd "$(dirname "$0")"
for name in architecture; do
  dot -Tpng -Gdpi=110 "$name.dot" -o "$name.png"
  dot -Tsvg "$name.dot" -o "$name.svg"
done
echo "Rendered: architecture.png, architecture.svg"
