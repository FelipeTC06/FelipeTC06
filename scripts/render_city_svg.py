"""Render data/contributions.json as a "city": one building per day.

Oblique projection drawn with plain shapes (front face, lit top, shaded
side). Weeks run left to right, weekdays run front (Sunday) to back
(Saturday). Building height is the square root of the day's count.
Buildings rise in a wave from the front row to the back, then a leader
line points at the busiest day. CSS keyframes only, no JavaScript, so it
animates inside GitHub's <img>.

Usage:
    python scripts/render_city_svg.py [input.json] [output.svg]
Env:
    STATIC=1  final frame, no animation
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

CELL = 11          # building footprint width
GAP = 3
PITCH = CELL + GAP
DX, DY = 7, 5      # depth offset per row (back = up and to the right)
MAX_H = 120        # height of the busiest day
MIN_H = 1.5        # slab for empty days
LEFT = 24
BOTTOM_PAD = 56    # room for month labels + footer
TOP_PAD = 46       # room for the busiest-day callout

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


def main() -> None:
    data = json.loads(SRC.read_text(encoding="utf-8"))
    days = data["days"]
    by_date = {d["date"]: d for d in days}
    first = dt.date.fromisoformat(days[0]["date"])
    last = dt.date.fromisoformat(days[-1]["date"])
    start = first - dt.timedelta(days=(first.weekday() + 1) % 7)  # back to Sunday
    weeks = (last - start).days // 7 + 1
    max_count = max((d["count"] for d in days), default=0)
    best = data.get("best_day") or max(days, key=lambda d: d["count"])
    scale = MAX_H / math.sqrt(max_count) if max_count else 0

    base_y = TOP_PAD + MAX_H + 6 * DY           # ground line of the front row
    W = LEFT + weeks * PITCH + 6 * DX + CELL + 24
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
    rise_total = 0.0
    if not STATIC:
        css.append("@keyframes rise{from{transform:scaleY(0)}to{transform:scaleY(1)}}"
                   ".b{transform:scaleY(0);animation:rise .7s cubic-bezier(.2,.9,.3,1.15) forwards}"
                   "@keyframes fade{from{opacity:0}to{opacity:1}}")

    out = [f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" viewBox="0 0 {W} {H}">',
           "<style>", *css, "</style>"]

    # ground lines for each row, back to front, so the city sits on something
    for row in range(6, -1, -1):
        x0 = LEFT + row * DX
        y = base_y - row * DY + 0.5
        n = sum(1 for w in range(weeks) if (start + dt.timedelta(weeks=w, days=row)).isoformat() in by_date)
        out.append(f'<line class="ground" x1="{x0}" y1="{y}" x2="{x0 + n * PITCH - GAP}" y2="{y}" opacity=".5"/>')

    best_top = None
    delays = []
    # draw back rows first, then left to right inside a row
    for row in range(6, -1, -1):
        for w in range(weeks):
            d = start + dt.timedelta(weeks=w, days=row)
            rec = by_date.get(d.isoformat())
            if rec is None:
                continue
            count, lvl = rec["count"], rec["level"]
            h = max(MIN_H, math.sqrt(count) * scale) if count else MIN_H
            x = LEFT + w * PITCH + row * DX
            y = base_y - row * DY          # ground y for this building
            top = y - h
            delay = row * 0.16 + w * 0.012
            delays.append(delay)
            anim = "" if STATIC else f' class="b" style="transform-origin:{x}px {y}px;animation-delay:{delay:.3f}s"'
            out.append(
                f'<g{anim}>'
                f'<title>{count} on {d.isoformat()}</title>'
                f'<rect class="f{lvl}" x="{x}" y="{top:.2f}" width="{CELL}" height="{h:.2f}"/>'
                f'<polygon class="t{lvl}" points="{x},{top:.2f} {x + CELL},{top:.2f} '
                f'{x + CELL + DX},{top - DY:.2f} {x + DX},{top - DY:.2f}"/>'
                f'<polygon class="s{lvl}" points="{x + CELL},{top:.2f} {x + CELL + DX},{top - DY:.2f} '
                f'{x + CELL + DX},{y - DY:.2f} {x + CELL},{y:.2f}"/>'
                f'</g>'
            )
            if d.isoformat() == best["date"] and count > 0:
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

    # callout for the busiest day
    if best_top:
        bx, by = best_top
        when = dt.date.fromisoformat(best["date"]).strftime("%-d %b %Y")
        label = f'{best["count"]} contribution{"s" if best["count"] != 1 else ""} · {when}'
        ty = 18
        # keep the label inside the canvas
        tx = min(max(bx + 24, 80), W - 170)
        anchor = "start"
        fade = "" if STATIC else f' style="opacity:0;animation:fade .6s ease-out {rise_total + 0.2:.2f}s forwards"'
        out.append(
            f'<g{fade}><polyline class="lead" points="{bx:.1f},{by:.1f} {bx:.1f},{ty + 8} {tx - 6:.1f},{ty + 8}"/>'
            f'<circle class="dot" cx="{bx:.1f}" cy="{by:.1f}" r="2.5"/>'
            f'<text class="call" x="{tx:.1f}" y="{ty + 4}" text-anchor="{anchor}">{label}</text></g>'
        )

    # footer
    fy = base_y + 40
    fade = "" if STATIC else f' style="opacity:0;animation:fade .6s ease-out {rise_total:.2f}s forwards"'
    out.append(
        f'<g{fade}><text class="foot" x="{LEFT}" y="{fy}">'
        f'<tspan class="num">{data["total"]:,}</tspan> contributions in the last year'
        f'   ·   current streak <tspan class="num">{data["current_streak"]}</tspan>d'
        f'   ·   longest <tspan class="num">{data["longest_streak"]}</tspan>d</text></g>'
    )
    out.append("</svg>")
    OUT.write_text("\n".join(out), encoding="utf-8")
    print(f"wrote {OUT} ({W}x{H}, {weeks} weeks, max {max_count})")


if __name__ == "__main__":
    main()
