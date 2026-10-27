"""Render data/contributions.json as a "city" of buildings.

Oblique projection drawn with plain shapes (front face, lit top, shaded
side). Building height is the square root of the count. Buildings rise in
a wave, then (optionally) a leader line points at the busiest one. CSS
keyframes only, no JavaScript, so it animates inside GitHub's <img>.

Modes (env GROUP):
    day   one building per day: weeks left to right, weekdays front (Sun)
          to back (Sat); wave rises front row to back.
    week  one building per week (default): a single skyline, wave rises
          left to right.

Env:
    GROUP   day | week (default week)
    LEGEND  1 to draw the busiest-day callout and the footer line (default 0)
    STATIC  1 for the final frame, no animation

Usage:
    python scripts/render_city_svg.py [input.json] [output.svg]
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
GROUP = os.environ.get("GROUP", "week")
LEGEND = os.environ.get("LEGEND", "0") == "1"

MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]

# (front, top, side) per level: dark theme / light theme
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

if GROUP == "week":
    CELL, GAP, DX, DY, MAX_H, ROWS = 11, 4, 9, 6, 120, 1
else:
    CELL, GAP, DX, DY, MAX_H, ROWS = 11, 3, 7, 5, 120, 7
PITCH = CELL + GAP
MIN_H = 1.5
LEFT = 24
TOP_PAD = 46 if LEGEND else 16
BOTTOM_PAD = 56 if LEGEND else 30


def level_for(count: int, thresholds: list[int]) -> int:
    if count == 0:
        return 0
    for i, t in enumerate(thresholds):
        if count <= t:
            return i + 1
    return 4


def main() -> None:
    data = json.loads(SRC.read_text(encoding="utf-8"))
    days = data["days"]
    by_date = {d["date"]: d for d in days}
    first = dt.date.fromisoformat(days[0]["date"])
    last = dt.date.fromisoformat(days[-1]["date"])
    start = first - dt.timedelta(days=(first.weekday() + 1) % 7)  # back to Sunday
    weeks = (last - start).days // 7 + 1

    # cells: (col, row, count, level, label_date)
    cells = []
    if GROUP == "week":
        totals = []
        for w in range(weeks):
            ds = [by_date.get((start + dt.timedelta(weeks=w, days=r)).isoformat()) for r in range(7)]
            totals.append(sum(d["count"] for d in ds if d))
        nonzero = sorted(t for t in totals if t)
        thr = [nonzero[min(len(nonzero) - 1, int(len(nonzero) * p))] for p in (0.25, 0.5, 0.75)] if nonzero else [0, 0, 0]
        for w, t in enumerate(totals):
            cells.append((w, 0, t, level_for(t, thr), start + dt.timedelta(weeks=w)))
    else:
        for w in range(weeks):
            for r in range(7):
                d = start + dt.timedelta(weeks=w, days=r)
                rec = by_date.get(d.isoformat())
                if rec:
                    cells.append((w, r, rec["count"], rec["level"], d))

    max_count = max((c[2] for c in cells), default=0)
    scale = MAX_H / math.sqrt(max_count) if max_count else 0
    best = max(cells, key=lambda c: c[2]) if cells else None

    base_y = TOP_PAD + MAX_H + (ROWS - 1) * DY
    W = LEFT + weeks * PITCH + (ROWS - 1) * DX + CELL + 24
    H = base_y + BOTTOM_PAD

    css = [
        "text{font-family:-apple-system,'Segoe UI',Helvetica,Arial,sans-serif;font-size:10px;fill:#8b949e}",
        ".foot{font-size:11px;fill:#c9d1d9}.num{fill:#39d353;font-weight:700}",
        ".call{font-size:11px;fill:#c9d1d9;font-weight:600}.lead{stroke:#8b949e;fill:none;stroke-width:1}",
        ".dot{fill:#39d353}.ground{stroke:#30363d;stroke-width:1}",
    ]
    for i, (f, t, s) in enumerate(DARK):
        css.append(f".f{i}{{fill:{f}}}.t{i}{{fill:{t}}}.s{i}{{fill:{s}}}")
    css.append("@media (prefers-color-scheme:light){"
               + "".join(f".f{i}{{fill:{f}}}.t{i}{{fill:{t}}}.s{i}{{fill:{s}}}" for i, (f, t, s) in enumerate(LIGHT))
               + "text{fill:#57606a}.foot,.call{fill:#24292f}.num,.dot{fill:#1a7f37}"
               + ".lead{stroke:#57606a}.ground{stroke:#d0d7de}}")
    if not STATIC:
        css.append("@keyframes rise{from{transform:scaleY(0)}to{transform:scaleY(1)}}"
                   ".b{transform:scaleY(0);animation:rise .7s cubic-bezier(.2,.9,.3,1.15) forwards}"
                   "@keyframes fade{from{opacity:0}to{opacity:1}}")

    out = [f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" viewBox="0 0 {W} {H}">',
           "<style>", *css, "</style>"]

    # ground line per row (back to front)
    for row in range(ROWS - 1, -1, -1):
        n = sum(1 for c in cells if c[1] == row)
        x0 = LEFT + row * DX
        y = base_y - row * DY + 0.5
        out.append(f'<line class="ground" x1="{x0}" y1="{y}" x2="{x0 + n * PITCH - GAP}" y2="{y}" opacity=".5"/>')

    best_top = None
    delays = []
    for row in range(ROWS - 1, -1, -1):          # back rows first
        for col, r, count, lvl, when in (c for c in cells if c[1] == row):
            h = max(MIN_H, math.sqrt(count) * scale) if count else MIN_H
            x = LEFT + col * PITCH + row * DX
            y = base_y - row * DY
            top = y - h
            delay = (row * 0.16 + col * 0.012) if GROUP == "day" else col * 0.045
            delays.append(delay)
            anim = "" if STATIC else f' class="b" style="transform-origin:{x}px {y}px;animation-delay:{delay:.3f}s"'
            title = f"{count} commits, week of {when.isoformat()}" if GROUP == "week" else f"{count} on {when.isoformat()}"
            out.append(
                f'<g{anim}><title>{title}</title>'
                f'<rect class="f{lvl}" x="{x}" y="{top:.2f}" width="{CELL}" height="{h:.2f}"/>'
                f'<polygon class="t{lvl}" points="{x},{top:.2f} {x + CELL},{top:.2f} '
                f'{x + CELL + DX},{top - DY:.2f} {x + DX},{top - DY:.2f}"/>'
                f'<polygon class="s{lvl}" points="{x + CELL},{top:.2f} {x + CELL + DX},{top - DY:.2f} '
                f'{x + CELL + DX},{y - DY:.2f} {x + CELL},{y:.2f}"/></g>'
            )
            if best and (col, r) == (best[0], best[1]) and count > 0:
                best_top = (x + CELL / 2 + DX / 2, top - DY / 2)
    rise_total = (max(delays) + 0.7) if delays else 0

    # month labels along the front edge
    seen = None
    for w in range(weeks):
        d = start + dt.timedelta(weeks=w)
        if d.month != seen:
            seen = d.month
            if w == 0 and (start + dt.timedelta(weeks=1)).month != d.month:
                continue
            out.append(f'<text x="{LEFT + w * PITCH}" y="{base_y + 16}">{MONTHS[d.month - 1]}</text>')

    if LEGEND and best_top:
        bx, by = best_top
        when = best[4]
        if GROUP == "week":
            label = f'{best[2]} commits · week of {when.strftime("%-d %b %Y")}'
        else:
            label = f'{best[2]} contributions · {when.strftime("%-d %b %Y")}'
        ty = 18
        tx = min(max(bx + 24, 80), W - 190)
        fade = "" if STATIC else f' style="opacity:0;animation:fade .6s ease-out {rise_total + 0.2:.2f}s forwards"'
        out.append(
            f'<g{fade}><polyline class="lead" points="{bx:.1f},{by:.1f} {bx:.1f},{ty + 8} {tx - 6:.1f},{ty + 8}"/>'
            f'<circle class="dot" cx="{bx:.1f}" cy="{by:.1f}" r="2.5"/>'
            f'<text class="call" x="{tx:.1f}" y="{ty + 4}">{label}</text></g>'
        )
    if LEGEND:
        fy = base_y + 40
        fade = "" if STATIC else f' style="opacity:0;animation:fade .6s ease-out {rise_total:.2f}s forwards"'
        out.append(
            f'<g{fade}><text class="foot" x="{LEFT}" y="{fy}">'
            f'<tspan class="num">{data["total"]:,}</tspan> commits in the last year'
            f'   ·   current streak <tspan class="num">{data["current_streak"]}</tspan>d'
            f'   ·   longest <tspan class="num">{data["longest_streak"]}</tspan>d</text></g>'
        )
    out.append("</svg>")
    OUT.write_text("\n".join(out), encoding="utf-8")
    print(f"wrote {OUT} ({W}x{H}, {weeks} weeks, group={GROUP}, max {max_count})")


if __name__ == "__main__":
    main()
