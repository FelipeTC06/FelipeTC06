"""Render the last N days as a city with ONE BUILDING PER COMMIT.

Each day is a column (left = oldest, right = today). Each commit of that
day is a building placed behind the previous one, so a busy day becomes a
deep block. The number of rows therefore follows the busiest day, not the
weekday. Heights vary building to building (a fixed golden-ratio sequence,
taller band for busier days) purely for the skyline look: the number of
buildings is the real count.

Oblique projection with plain shapes (front, lit top, shaded side), CSS
keyframes only (no JavaScript), dark and light themes.

Usage:
    python scripts/render_commit_city_svg.py [input.json] [output.svg]
Env:
    DAYS     window in days (default 30)
    STATIC   1 for the final frame, no animation
"""
import datetime as dt
import json
import math
import os
import sys
from pathlib import Path

SRC = Path(sys.argv[1]) if len(sys.argv) > 1 else Path("data/contributions.json")
OUT = Path(sys.argv[2]) if len(sys.argv) > 2 else Path("contrib-city.svg")
STATIC = os.environ.get("STATIC") == "1"
DAYS = int(os.environ.get("DAYS", "30"))

CELL = 14            # building width
GAP = 10             # gap between day columns
PITCH = CELL + GAP
DX_MAX, DY_MAX = 7, 5
MAX_DEPTH_PX = 120   # the deepest column may use this much x-offset
H_BAND = {1: (18, 40), 2: (32, 66), 3: (52, 96), 4: (74, 130)}  # by day level
H_BACK_MAX = 130
PHI = 0.6180339887
LEFT = 28
TOP_PAD = 20
BOTTOM_PAD = 34

MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]

DARK = [
    ("#1d242d", "#2a323c", "#161b22"),
    ("#0e4429", "#176b3f", "#092e1c"),
    ("#006d32", "#14944a", "#004a22"),
    ("#26a641", "#4fcc63", "#1a7a30"),
    ("#39d353", "#7ff089", "#27a63d"),
]
LIGHT = [
    ("#e6e8eb", "#f4f5f7", "#d0d4d9"),
    ("#9be9a8", "#c4f3cb", "#7ccb8a"),
    ("#40c463", "#73d98d", "#30a14e"),
    ("#30a14e", "#4fc06c", "#237a3b"),
    ("#216e39", "#3b9452", "#174d28"),
]


def main() -> None:
    data = json.loads(SRC.read_text(encoding="utf-8"))
    by_date = {d["date"]: d["count"] for d in data["days"]}
    last = dt.date.fromisoformat(data["days"][-1]["date"])
    window = [last - dt.timedelta(days=i) for i in range(DAYS - 1, -1, -1)]
    counts = [by_date.get(d.isoformat(), 0) for d in window]
    max_count = max(counts) if counts else 0

    # quartile colour levels over the window
    nonzero = sorted(c for c in counts if c)
    thr = [nonzero[min(len(nonzero) - 1, int(len(nonzero) * p))] for p in (0.25, 0.5, 0.75)] if nonzero else [0, 0, 0]

    def level(c: int) -> int:
        if c == 0:
            return 0
        for i, t in enumerate(thr):
            if c <= t:
                return i + 1
        return 4

    rows = max(max_count, 1)
    dx = min(DX_MAX, MAX_DEPTH_PX / rows)
    dy = dx * DY_MAX / DX_MAX

    def height(col: int, i: int, lvl: int) -> float:   # i-th building of a day
        lo, hi = H_BAND[max(lvl, 1)]
        t = ((i + 1) * PHI + col * 0.37) % 1.0
        return lo + (hi - lo) * t

    base_y = TOP_PAD + H_BACK_MAX + (rows - 1) * dy
    W = int(LEFT + DAYS * PITCH + (rows - 1) * dx + CELL + 20)
    H = int(base_y + BOTTOM_PAD)

    css = [
        "text{font-family:-apple-system,'Segoe UI',Helvetica,Arial,sans-serif;font-size:10px;fill:#8b949e}",
        ".ground{stroke:#30363d;stroke-width:1}.slab{fill:#161b22}",
    ]
    for i, (f, t, s) in enumerate(DARK):
        css.append(f".f{i}{{fill:{f}}}.t{i}{{fill:{t}}}.s{i}{{fill:{s}}}")
    css.append("@media (prefers-color-scheme:light){"
               + "".join(f".f{i}{{fill:{f}}}.t{i}{{fill:{t}}}.s{i}{{fill:{s}}}" for i, (f, t, s) in enumerate(LIGHT))
               + "text{fill:#57606a}.ground{stroke:#d0d7de}.slab{fill:#ebedf0}}")
    if not STATIC:
        css.append("@keyframes rise{from{transform:scaleY(0)}to{transform:scaleY(1)}}"
                   ".b{transform:scaleY(0);animation:rise .6s cubic-bezier(.2,.9,.3,1.15) forwards}")

    out = [f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" viewBox="0 0 {W} {H}">',
           "<style>", *css, "</style>"]

    # ground: one slab per day column, drawn as a flat plot the buildings stand on
    for col, c in enumerate(counts):
        depth = max(c, 1)
        x = LEFT + col * PITCH
        y = base_y
        out.append(
            f'<polygon class="slab" points="{x},{y} {x + CELL},{y} '
            f'{x + CELL + depth * dx:.1f},{y - depth * dy:.1f} {x + depth * dx:.1f},{y - depth * dy:.1f}" opacity=".9"/>'
        )
    out.append(f'<line class="ground" x1="{LEFT - 6}" y1="{base_y + 0.5}" x2="{LEFT + DAYS * PITCH - GAP + 6}" y2="{base_y + 0.5}"/>')

    # buildings: back rows first so nearer ones cover farther ones; inside a
    # row, left to right
    for row in range(rows - 1, -1, -1):
        for col, c in enumerate(counts):
            if row >= c:
                continue
            lvl = level(c)
            h = height(col, row, lvl)
            x = LEFT + col * PITCH + row * dx
            y = base_y - row * dy
            top = y - h
            delay = col * 0.05 + row * 0.04
            anim = "" if STATIC else f' class="b" style="transform-origin:{x:.2f}px {y:.2f}px;animation-delay:{delay:.3f}s"'
            out.append(
                f'<g{anim}><title>{c} commits on {window[col].isoformat()}</title>'
                f'<rect class="f{lvl}" x="{x:.2f}" y="{top:.2f}" width="{CELL}" height="{h:.2f}"/>'
                f'<polygon class="t{lvl}" points="{x:.2f},{top:.2f} {x + CELL:.2f},{top:.2f} '
                f'{x + CELL + dx:.2f},{top - dy:.2f} {x + dx:.2f},{top - dy:.2f}"/>'
                f'<polygon class="s{lvl}" points="{x + CELL:.2f},{top:.2f} {x + CELL + dx:.2f},{top - dy:.2f} '
                f'{x + CELL + dx:.2f},{y - dy:.2f} {x + CELL:.2f},{y:.2f}"/></g>'
            )

    # date labels: first day, every Monday, and today
    for col, d in enumerate(window):
        is_edge = col == 0 or col == DAYS - 1
        if is_edge or (d.weekday() == 0 and 2 <= col <= DAYS - 3):
            label = f"{d.day} {MONTHS[d.month - 1]}" if (col == 0 or d.day <= 7 or col == DAYS - 1) else str(d.day)
            anchor = "middle"
            out.append(f'<text x="{LEFT + col * PITCH + CELL / 2:.1f}" y="{base_y + 16}" text-anchor="{anchor}">{label}</text>')

    out.append("</svg>")
    OUT.write_text("\n".join(out), encoding="utf-8")
    print(f"wrote {OUT} ({W}x{H}, {DAYS} days, {sum(counts)} buildings, {rows} rows)")


if __name__ == "__main__":
    main()
