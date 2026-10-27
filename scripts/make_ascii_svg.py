"""Convert data/portrait.png into an animated ASCII-art SVG.

Each row of characters wipes in from left to right with a block cursor at
the edge; rows are staggered top-to-bottom and then freeze. Pure SVG/SMIL,
no JavaScript, so it animates inside GitHub's <img> sandbox.

Usage:
    python scripts/make_ascii_svg.py [input.png] [output.svg]
Env:
    COLS   number of character columns (default 84)
    STATIC set to 1 to skip the animation (useful for previews)
"""
import os
import sys
from pathlib import Path
from xml.sax.saxutils import escape

import numpy as np
from PIL import Image

SRC = Path(sys.argv[1]) if len(sys.argv) > 1 else Path("data/portrait.png")
OUT = Path(sys.argv[2]) if len(sys.argv) > 2 else Path("felipe-ascii.svg")

COLS = int(os.environ.get("COLS", "84"))
STATIC = os.environ.get("STATIC") == "1"

# Light to dark; leading space makes a white background vanish.
RAMP = " .`:-=+*cs#%@"

FONT_SIZE = 7.2            # px
CHAR_W = FONT_SIZE * 0.602  # advance width of Courier-like fonts
LINE_H = FONT_SIZE * 1.18
PAD = 8


def to_ascii(img: Image.Image, cols: int) -> list[str]:
    w, h = img.size
    rows = max(1, int(round(h / w * cols * (CHAR_W / LINE_H))))
    small = img.convert("L").resize((cols, rows), Image.LANCZOS)
    a = np.asarray(small, dtype=np.float32) / 255.0
    # brightness 1.0 (white) -> index 0 (space); black -> densest glyph
    idx = np.clip(((1.0 - a) * (len(RAMP) - 1)).round().astype(int), 0, len(RAMP) - 1)
    lines = ["".join(RAMP[i] for i in row) for row in idx]
    # Trim fully empty rows at top/bottom so the portrait is tight.
    while lines and not lines[0].strip():
        lines.pop(0)
    while lines and not lines[-1].strip():
        lines.pop()
    return lines


def build_svg(lines: list[str]) -> str:
    cols = max(len(l) for l in lines)
    width = int(cols * CHAR_W + PAD * 2)
    height = int(len(lines) * LINE_H + PAD * 2)
    row_dur = 0.9
    stagger = 0.045

    parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" '
        f'viewBox="0 0 {width} {height}">',
        "<style>",
        "text{font-family:'JetBrains Mono','Fira Code','SFMono-Regular',Consolas,'Courier New',monospace;"
        f"font-size:{FONT_SIZE}px;fill:#b8c0cc;white-space:pre;dominant-baseline:hanging}}",
        ".cur{fill:#39d353}",
        "@media (prefers-color-scheme:light){text{fill:#3b434d}.cur{fill:#1f883d}}",
        "</style>",
        "<defs>",
    ]
    if not STATIC:
        for i in range(len(lines)):
            begin = i * stagger
            parts.append(
                f'<clipPath id="c{i}"><rect x="0" y="{PAD + i * LINE_H - 1:.2f}" width="0" '
                f'height="{LINE_H + 2:.2f}">'
                f'<animate attributeName="width" from="0" to="{width}" dur="{row_dur}s" '
                f'begin="{begin:.3f}s" fill="freeze"/></rect></clipPath>'
            )
    parts.append("</defs>")

    for i, line in enumerate(lines):
        y = PAD + i * LINE_H
        clip = "" if STATIC else f' clip-path="url(#c{i})"'
        parts.append(
            f'<g{clip}><text x="{PAD}" y="{y:.2f}" xml:space="preserve">{escape(line)}</text></g>'
        )
        if not STATIC:
            begin = i * stagger
            parts.append(
                f'<rect class="cur" x="{PAD}" y="{y:.2f}" width="{CHAR_W:.2f}" height="{LINE_H - 1:.2f}" opacity="0">'
                f'<set attributeName="opacity" to="1" begin="{begin:.3f}s"/>'
                f'<animate attributeName="x" from="{PAD}" to="{PAD + cols * CHAR_W:.2f}" dur="{row_dur}s" '
                f'begin="{begin:.3f}s" fill="freeze"/>'
                f'<set attributeName="opacity" to="0" begin="{begin + row_dur:.3f}s" fill="freeze"/></rect>'
            )
    parts.append("</svg>")
    return "\n".join(parts)


def main() -> None:
    img = Image.open(SRC)
    lines = to_ascii(img, COLS)
    OUT.write_text(build_svg(lines), encoding="utf-8")
    print(f"wrote {OUT}: {len(lines)} rows x {COLS} cols")


if __name__ == "__main__":
    main()
