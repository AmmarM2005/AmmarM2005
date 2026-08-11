#!/usr/bin/env python3
"""
generate_portrait.py

Turns a headshot into a self-typing ASCII-art SVG that survives GitHub's
README sanitiser (no <style>, no external requests, animation via SMIL).

Pipeline: rembg cutout -> bilateral filter -> CLAHE -> darkening curve
          -> map to a 13-character brightness ramp -> per-row clipPath
          typing animation, staggered top to bottom.

Usage:
    python3 scripts/generate_portrait.py assets/photo/me.jpg portrait.svg

Requires: pillow numpy opencv-python-headless rembg onnxruntime
"""

import sys
import base64
import numpy as np
from PIL import Image
import cv2
from rembg import remove

# --- geometry constants (do not change without re-checking Part 4 of the guide) ---
COLS = 90
FONT_SIZE = 12.9
CHAR_W = 7.74          # exact advance for JetBrains Mono / DejaVu Sans Mono at this size
CHAR_H = 16.6
DISPLAY_WIDTH_PX = 460
RAMP = " .`:-=+*cs#%@"  # blank end maps to background; keep exactly these 13 chars
                        # (must match the font subset in Part 4)


def load_and_cutout(path: str) -> Image.Image:
    """Remove the background and force it to white so it lands on the blank
    end of the ramp instead of filling with '@'."""
    with open(path, "rb") as f:
        raw = f.read()
    cut = remove(raw)  # returns RGBA PNG bytes with transparent background
    img = Image.open(__import__("io").BytesIO(cut)).convert("RGBA")
    bg = Image.new("RGBA", img.size, (255, 255, 255, 255))
    bg.paste(img, mask=img.split()[3])
    return bg.convert("RGB")


def preprocess(img: Image.Image) -> np.ndarray:
    arr = np.array(img.convert("L"))
    # bilateral filter: smooth skin, keep edges
    arr = cv2.bilateralFilter(arr, d=9, sigmaColor=75, sigmaSpace=75)
    # CLAHE: local contrast so a flatly-lit face doesn't collapse to one tone
    clahe = cv2.createCLAHE(clipLimit=3.0, tileGridSize=(8, 8))
    arr = clahe.apply(arr)
    # darkening curve — the fix that keeps glasses/brows/lips from washing out
    normed = (arr.astype(np.float32) / 255.0) ** 1.7
    arr = (normed * 255).astype(np.uint8)
    return arr


def to_ascii_grid(arr: np.ndarray, cols: int = COLS) -> list[str]:
    h, w = arr.shape
    rows = max(1, round(cols * (h / w) * 0.48))
    resized = cv2.resize(arr, (cols, rows), interpolation=cv2.INTER_AREA)
    ramp = RAMP
    n = len(ramp) - 1
    lines = []
    for r in range(rows):
        line = []
        for c in range(cols):
            v = resized[r, c]  # 0 = dark, 255 = light
            idx = n - int((v / 255.0) * n)  # dark -> dense char
            line.append(ramp[idx])
        lines.append("".join(line))
    return lines


def load_font_b64(woff2_path: str | None) -> str | None:
    if not woff2_path:
        return None
    with open(woff2_path, "rb") as f:
        return base64.b64encode(f.read()).decode("ascii")


def build_svg(lines: list[str], font_b64: str | None = None) -> str:
    rows = len(lines)
    cols = max(len(l) for l in lines)
    width = cols * CHAR_W
    height = rows * CHAR_H

    font_face = ""
    font_family = "ui-monospace, 'DejaVu Sans Mono', 'Liberation Mono', monospace"
    if font_b64:
        font_face = f"""
    <style>
      @font-face {{
        font-family: 'ProfileMono';
        src: url(data:font/woff2;base64,{font_b64}) format('woff2');
      }}
    </style>"""
        font_family = "'ProfileMono', ui-monospace, monospace"
        # NOTE: <style> is stripped by GitHub's README sanitiser but this SVG
        # is loaded via <img>, which renders the raw file directly and is not
        # sanitised the same way — that's *why* Part 4 requires the img-tag path.

    row_svgs = []
    for i, line in enumerate(lines):
        escaped = (
            line.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
        )
        y = (i + 1) * CHAR_H - CHAR_H * 0.25
        row_w = len(line) * CHAR_W
        begin = round(i * 0.09, 2)
        row_svgs.append(f'''
    <clipPath id="clip{i}">
      <rect x="0" y="{i * CHAR_H}" width="0" height="{CHAR_H}">
        <animate attributeName="width" from="0" to="{row_w}"
                 dur="0.5s" begin="{begin}s" fill="freeze" />
      </rect>
    </clipPath>''')

    text_elems = []
    for i, line in enumerate(lines):
        escaped = (
            line.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
        )
        y = (i + 1) * CHAR_H - CHAR_H * 0.25
        text_elems.append(
            f'<text x="0" y="{y:.1f}" clip-path="url(#clip{i})" '
            f'font-family="{font_family}" font-size="{FONT_SIZE}" '
            f'xml:space="preserve" fill="var(--portrait-fg, #39d353)">{escaped}</text>'
        )

    svg = f'''<svg viewBox="0 0 {width:.1f} {height:.1f}" width="{DISPLAY_WIDTH_PX}"
     xmlns="http://www.w3.org/2000/svg" role="img" aria-label="ASCII self-portrait">{font_face}
  <defs>{"".join(row_svgs)}
  </defs>
  <rect width="100%" height="100%" fill="none" />
  {"".join(text_elems)}
</svg>'''
    return svg


def main():
    if len(sys.argv) < 3:
        print("usage: generate_portrait.py <photo> <out.svg> [font.woff2]")
        sys.exit(1)
    photo_path, out_path = sys.argv[1], sys.argv[2]
    font_path = sys.argv[3] if len(sys.argv) > 3 else None

    img = load_and_cutout(photo_path)
    arr = preprocess(img)
    lines = to_ascii_grid(arr)
    font_b64 = load_font_b64(font_path)
    svg = build_svg(lines, font_b64)

    with open(out_path, "w") as f:
        f.write(svg)
    print(f"wrote {out_path}  ({len(lines)} rows x {max(len(l) for l in lines)} cols)")


if __name__ == "__main__":
    main()
