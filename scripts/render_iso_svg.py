"""Render data/contributions.json as an isometric contribution graph, in the
spirit of jasonlong/isometric-contributions: the 53x7 calendar drawn as a
tilted board of cubes, one per day, height proportional to the count, with
a small stats panel (total, busiest day, streaks).

True isometric projection (2:1), three faces per cube (top, left, right),
GitHub's green palette for dark and light themes. Cubes rise in a wave
from the back of the board to the front, CSS keyframes only (no JS).

Usage:
    python scripts/render_iso_svg.py [input.json] [output.svg]
Env:
    STATS   1 to draw the stats panel (default 1)
    STATIC  1 for the final frame, no animation
"""
import datetime as dt
import json
import math
import os
import sys
from pathlib import Path

SRC = Path(sys.argv[1]) if len(sys.argv) > 1 else Path("data/contributions.json")
OUT = Path(sys.argv[2]) if len(sys.argv) > 2 else Path("contrib-iso.svg")
STATIC = os.environ.get("STATIC") == "1"
STATS = os.environ.get("STATS", "1") == "1"

TILE = 13.0               # cube footprint (isometric unit)
GAP = 0.18                # fraction of TILE left empty between cubes
MAX_H = 110.0             # busiest day
MIN_H = 2.0               # empty day slab
COS30, SIN30 = math.cos(math.radians(30)), 0.5
MARGIN = 20

# (top, left, right) per level
DARK = [
    ("#1f2730", "#161c23", "#121820"),
    ("#1a6b3c", "#0e4429", "#0a331f"),
    ("#1f9a48", "#006d32", "#005126"),
    ("#3fcc5d", "#26a641", "#1b7d31"),
    ("#6ff086", "#39d353", "#2aa842"),
]
LIGHT = [
    ("#f0f2f4", "#dfe3e8", "#cfd5dc"),
    ("#b6f0c0", "#9be9a8", "#7ccb8a"),
    ("#67d884", "#40c463", "#2f9d4c"),
    ("#4fbd6a", "#30a14e", "#237a3b"),
    ("#39914f", "#216e39", "#17502a"),
]


def iso(i: float, j: float) -> tuple[float, float]:
    """grid (week i, weekday j) -> screen; weeks run down-right, days down-left."""
    return ((i - j) * TILE * COS30, (i + j) * TILE * SIN30)


def main() -> None:
    data = json.loads(SRC.read_text(encoding="utf-8"))
    days = data["days"]
    by_date = {d["date"]: d for d in days}
    first = dt.date.fromisoformat(days[0]["date"])
    last = dt.date.fromisoformat(days[-1]["date"])
    start = first - dt.timedelta(days=(first.weekday() + 1) % 7)
    weeks = (last - start).days // 7 + 1
    max_count = max((d["count"] for d in days), default=0)
    best = data.get("best_day") or max(days, key=lambda d: d["count"])

    cells = []
    for i in range(weeks):
        for j in range(7):
            d = start + dt.timedelta(weeks=i, days=j)
            rec = by_date.get(d.isoformat())
            if rec:
                cells.append((i, j, rec["count"], rec["level"], d))

    # board extents
    xs = [iso(i + k, j + m)[0] for i, j, *_ in cells for k in (0, 1) for m in (0, 1)]
    ys = [iso(i + k, j + m)[1] for i, j, *_ in cells for k in (0, 1) for m in (0, 1)]
    ox = MARGIN - min(xs)
    oy = MARGIN + MAX_H - min(ys)
    board_w = max(xs) - min(xs)
    stats_w = 230 if STATS else 0
    W = int(board_w + 2 * MARGIN + stats_w)
    H = int(max(ys) - min(ys) + MAX_H + 2 * MARGIN)

    css = [
        "text{font-family:-apple-system,'Segoe UI',Helvetica,Arial,sans-serif;fill:#8b949e}",
        ".h{font-size:11px;letter-spacing:.08em;text-transform:uppercase;fill:#8b949e}",
        ".v{font-size:22px;font-weight:700;fill:#e6edf3}.u{font-size:11px;fill:#8b949e}.d{font-size:10px;fill:#6e7681}",
        ".rule{stroke:#30363d}",
    ]
    for k, (t, l, r) in enumerate(DARK):
        css.append(f".t{k}{{fill:{t}}}.l{k}{{fill:{l}}}.r{k}{{fill:{r}}}")
    css.append("@media (prefers-color-scheme:light){"
               + "".join(f".t{k}{{fill:{t}}}.l{k}{{fill:{l}}}.r{k}{{fill:{r}}}" for k, (t, l, r) in enumerate(LIGHT))
               + "text,.h,.u{fill:#57606a}.v{fill:#1f2328}.d{fill:#8c959f}.rule{stroke:#d0d7de}}")
    if not STATIC:
        css.append("@keyframes rise{from{transform:scaleY(0)}to{transform:scaleY(1)}}"
                   ".c{transform:scaleY(0);animation:rise .55s cubic-bezier(.2,.9,.3,1.1) forwards}"
                   "@keyframes fade{from{opacity:0}to{opacity:1}}")

    out = [f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" viewBox="0 0 {W} {H}">',
           "<style>", *css, "</style>"]

    g = GAP / 2
    last_delay = 0.0
    # painter's order: back (small i+j) to front
    for i, j, count, lvl, d in sorted(cells, key=lambda c: (c[0] + c[1], c[0])):
        h = MIN_H + (MAX_H - MIN_H) * (count / max_count) if max_count and count else MIN_H
        # footprint corners (with gap), on the ground plane
        a = iso(i + g, j + g)          # back corner
        b = iso(i + 1 - g, j + g)      # right corner
        c = iso(i + 1 - g, j + 1 - g)  # front corner
        e = iso(i + g, j + 1 - g)      # left corner
        pts = [(x + ox, y + oy) for x, y in (a, b, c, e)]
        (ax, ay), (bx, by), (cx, cy), (ex, ey) = pts
        delay = (i + j) * 0.035
        last_delay = max(last_delay, delay)
        anim = "" if STATIC else f' class="c" style="transform-origin:{cx:.2f}px {cy:.2f}px;animation-delay:{delay:.3f}s"'
        top = f"{ax:.2f},{ay - h:.2f} {bx:.2f},{by - h:.2f} {cx:.2f},{cy - h:.2f} {ex:.2f},{ey - h:.2f}"
        left = f"{ex:.2f},{ey - h:.2f} {cx:.2f},{cy - h:.2f} {cx:.2f},{cy:.2f} {ex:.2f},{ey:.2f}"
        right = f"{cx:.2f},{cy - h:.2f} {bx:.2f},{by - h:.2f} {bx:.2f},{by:.2f} {cx:.2f},{cy:.2f}"
        out.append(
            f'<g{anim}><title>{count} on {d.isoformat()}</title>'
            f'<polygon class="l{lvl}" points="{left}"/>'
            f'<polygon class="r{lvl}" points="{right}"/>'
            f'<polygon class="t{lvl}" points="{top}"/></g>'
        )

    if STATS:
        sx = W - stats_w + 10
        sy = MARGIN + 10
        fade = "" if STATIC else f' style="opacity:0;animation:fade .6s ease-out {last_delay + 0.3:.2f}s forwards"'
        best_date = dt.date.fromisoformat(best["date"]).strftime("%b %-d, %Y")
        cur_end = last.strftime("%b %-d")
        rows = [
            ("Contributions", f'{data["total"]:,}', "total", f'{first.strftime("%b %-d, %Y")} – {last.strftime("%b %-d, %Y")}'),
            ("Busiest day", f'{best["count"]}', "contributions", best_date),
            ("Longest streak", f'{data["longest_streak"]}', "days", ""),
            ("Current streak", f'{data["current_streak"]}', "days", f"ending {cur_end}" if data["current_streak"] else ""),
        ]
        out.append(f"<g{fade}>")
        y = sy
        for head, val, unit, sub in rows:
            out.append(f'<text class="h" x="{sx}" y="{y}">{head}</text>')
            out.append(f'<text class="v" x="{sx}" y="{y + 26}">{val}<tspan class="u"> {unit}</tspan></text>')
            if sub:
                out.append(f'<text class="d" x="{sx}" y="{y + 42}">{sub}</text>')
            y += 66
            if head != rows[-1][0]:
                out.append(f'<line class="rule" x1="{sx}" y1="{y - 14}" x2="{W - MARGIN}" y2="{y - 14}" opacity=".6"/>')
        out.append("</g>")

    out.append("</svg>")
    OUT.write_text("\n".join(out), encoding="utf-8")
    print(f"wrote {OUT} ({W}x{H}, {len(cells)} cubes, max {max_count})")


if __name__ == "__main__":
    main()
