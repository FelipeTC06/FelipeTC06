"""Render data/contributions.json as an animated heatmap SVG.

Cells slide in diagonally, line by line (CSS keyframes that play once).
Includes month labels, weekday labels, a Less→More legend and a footer with
total contributions and streaks.

Usage:
    python scripts/render_heatmap_svg.py [input.json] [output.svg]
Env:
    STATIC=1  no animation
"""
import datetime as dt
import json
import os
import sys
from pathlib import Path

SRC = Path(sys.argv[1]) if len(sys.argv) > 1 else Path("data/contributions.json")
OUT = Path(sys.argv[2]) if len(sys.argv) > 2 else Path("contrib-heatmap.svg")
STATIC = os.environ.get("STATIC") == "1"

CELL = 13
GAP = 3
PITCH = CELL + GAP
LEFT = 34          # room for weekday labels
TOP = 22           # room for month labels
COLORS = ["#161b22", "#0e4429", "#006d32", "#26a641", "#39d353"]
COLORS_LIGHT = ["#ebedf0", "#9be9a8", "#40c463", "#30a14e", "#216e39"]
MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]


def main() -> None:
    data = json.loads(SRC.read_text(encoding="utf-8"))
    days = data["days"]
    first = dt.date.fromisoformat(days[0]["date"])
    # GitHub's grid starts on a Sunday
    start = first - dt.timedelta(days=(first.weekday() + 1) % 7)
    by_date = {d["date"]: d for d in days}
    last = dt.date.fromisoformat(days[-1]["date"])
    weeks = (last - start).days // 7 + 1

    W = LEFT + weeks * PITCH + 6
    grid_h = 7 * PITCH
    H = TOP + grid_h + 44

    out = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" viewBox="0 0 {W} {H}">',
        "<style>",
        "text{font-family:-apple-system,'Segoe UI',Helvetica,Arial,sans-serif;font-size:10px;fill:#8b949e}",
        ".foot{font-size:11px;fill:#c9d1d9}.num{fill:#39d353;font-weight:700}",
    ]
    for i, (c, cl) in enumerate(zip(COLORS, COLORS_LIGHT)):
        out.append(f".l{i}{{fill:{c}}}")
    out.append("@media (prefers-color-scheme:light){"
               + "".join(f".l{i}{{fill:{cl}}}" for i, cl in enumerate(COLORS_LIGHT))
               + "text{fill:#57606a}.foot{fill:#24292f}.num{fill:#1a7f37}}")
    if not STATIC:
        out.append("@keyframes drop{from{opacity:0;transform:translate(-6px,-6px)}to{opacity:1;transform:none}}"
                   ".c{opacity:0;animation:drop .35s ease-out forwards}"
                   "@keyframes fade{from{opacity:0}to{opacity:1}}"
                   ".f{opacity:0;animation:fade .6s ease-out 2.4s forwards}")
    out.append("</style>")

    # weekday labels (Mon, Wed, Fri like GitHub)
    for row, label in [(1, "Mon"), (3, "Wed"), (5, "Fri")]:
        out.append(f'<text x="0" y="{TOP + row * PITCH + CELL - 3}">{label}</text>')

    # month labels: when the month changes between weeks
    seen_month = None
    for w in range(weeks):
        d = start + dt.timedelta(weeks=w)
        if d.month != seen_month:
            seen_month = d.month
            if w == 0 and (start + dt.timedelta(weeks=1)).month != d.month:
                continue  # avoid a cramped label at the very left edge
            out.append(f'<text x="{LEFT + w * PITCH}" y="{TOP - 8}">{MONTHS[d.month - 1]}</text>')

    for w in range(weeks):
        for row in range(7):
            d = start + dt.timedelta(weeks=w, days=row)
            key = d.isoformat()
            if key not in by_date:
                continue
            lvl = by_date[key]["level"]
            x = LEFT + w * PITCH
            y = TOP + row * PITCH
            cls = f"l{lvl}" + ("" if STATIC else " c")
            delay = "" if STATIC else f' style="animation-delay:{(w + row) * 0.035:.3f}s"'
            out.append(f'<rect class="{cls}" x="{x}" y="{y}" width="{CELL}" height="{CELL}" rx="2"{delay}>'
                       f'<title>{by_date[key]["count"]} on {key}</title></rect>')

    # footer
    fy = TOP + grid_h + 28
    f = "" if STATIC else ' class="f"'
    out.append(
        f'<g{f}><text class="foot" x="{LEFT}" y="{fy}">'
        f'<tspan class="num">{data["total"]:,}</tspan> contributions in the last year'
        f'   ·   current streak <tspan class="num">{data["current_streak"]}</tspan>d'
        f'   ·   longest <tspan class="num">{data["longest_streak"]}</tspan>d</text>'
    )
    lx = W - 6 - 5 * PITCH - 64
    out.append(f'<text x="{lx - 28}" y="{fy}">Less</text>')
    for i in range(5):
        out.append(f'<rect class="l{i}" x="{lx + i * PITCH}" y="{fy - 10}" width="{CELL}" height="{CELL}" rx="2"/>')
    out.append(f'<text x="{lx + 5 * PITCH + 2}" y="{fy}">More</text></g>')
    out.append("</svg>")

    OUT.write_text("\n".join(out), encoding="utf-8")
    print(f"wrote {OUT} ({W}x{H}, {weeks} weeks)")


if __name__ == "__main__":
    main()
