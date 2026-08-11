#!/usr/bin/env bash
# Subsets JetBrains Mono into small woff2 files so each SVG stays light.
# JetBrains Mono is SIL OFL — safe to commit to a public repo. Ship
# assets/font/LICENSE next to it.
#
# Usage: ./scripts/subset_font.sh path/to/JetBrainsMono-Regular.ttf
set -euo pipefail
pip install --quiet fonttools brotli

SRC="$1"
OUT_DIR="assets/font"
mkdir -p "$OUT_DIR"

# 13 characters used by the ASCII ramp — must match RAMP in generate_portrait.py
pyftsubset "$SRC" --text=' .`:-=+*cs#%@' \
  --flavor=woff2 --layout-features='' --no-hinting -o "$OUT_DIR/ramp.woff2"

# Basic latin + digits, for headings and data-graphic labels
pyftsubset "$SRC" --unicodes='U+0020-007E' \
  --flavor=woff2 --layout-features='' --no-hinting -o "$OUT_DIR/basic.woff2"

echo "wrote $OUT_DIR/ramp.woff2 and $OUT_DIR/basic.woff2"
ls -la "$OUT_DIR"
