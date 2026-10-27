"""Render the neofetch-style info card (info-card.svg).

Edit PROFILE below to change the text. Lines fade and slide in on a short
stagger (CSS keyframes inside the SVG, no JavaScript).

Usage:
    python scripts/make_info_card.py [output.svg]
Env:
    STATIC=1  render the final frame without animation
"""
import os
import sys
from pathlib import Path
from xml.sax.saxutils import escape

OUT = Path(sys.argv[1]) if len(sys.argv) > 1 else Path("info-card.svg")
STATIC = os.environ.get("STATIC") == "1"

USER = "felipe"
HOST = "github"

# key -> list of lines (keep each line under ~52 chars)
PROFILE = [
    ("Name",       ["Felipe Torres Cresto"]),
    ("Now",        ["AI Engineer · LLM agents, MCP, RAG, evals"]),
    ("Prev",       ["Full-stack (Angular + Node) for US banks,",
                    "remote since 2021"]),
    ("Stack",      ["TypeScript · Node/NestJS · Angular · Python",
                    "PostgreSQL + pgvector · Kafka · Prisma"]),
    ("Highlights", ["MCP server (OAuth 2.1) + MCP client",
                    "multi-provider LLM gateway (cost/latency)",
                    "RAG on pgvector · golden-set + LLM-as-judge evals"]),
    ("Daily",      ["Claude Code · Codex · Cursor"]),
    ("Langs",      ["Português · English · Français"]),
    ("Likes",      ["sports, surf, shipping things that feel fast"]),
    ("Contact",    ["felipe.t.cresto@gmail.com",
                    "linkedin.com/in/felipe-torres-cresto"]),
]

W = 490
PAD_X = 18
TOP = 44            # below the title bar
LINE_H = 17
KEY_W = 92
FONT = 12.5
BAR_H = 30

PALETTE = ["#ff7b72", "#ffa657", "#d2a8ff", "#79c0ff", "#56d364",
           "#f778ba", "#a5d6ff", "#ffdf5d"]


def main() -> None:
    rows = []  # (key or None, value, colour)
    for i, (key, lines) in enumerate(PROFILE):
        colour = PALETTE[i % len(PALETTE)]
        for j, line in enumerate(lines):
            rows.append((key if j == 0 else None, line, colour))

    n_lines = len(rows) + 3  # prompt line, separator, swatches
    H = TOP + n_lines * LINE_H + 22

    out = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" viewBox="0 0 {W} {H}">',
        "<style>",
        "text{font-family:'JetBrains Mono','Fira Code','SFMono-Regular',Consolas,'Courier New',monospace;"
        f"font-size:{FONT}px;fill:#c9d1d9;white-space:pre}}",
        ".k{font-weight:700}.dim{fill:#8b949e}.pr{fill:#56d364}.at{fill:#8b949e}.hn{fill:#79c0ff}",
        ".card{fill:#0d1117;stroke:#30363d}.bar{fill:#161b22}",
        "@media (prefers-color-scheme:light){.card{fill:#ffffff;stroke:#d0d7de}.bar{fill:#f6f8fa}"
        "text{fill:#24292f}.dim,.at{fill:#57606a}.pr{fill:#1a7f37}.hn{fill:#0969da}}",
    ]
    if not STATIC:
        out.append(
            "@keyframes in{from{opacity:0;transform:translateX(-8px)}to{opacity:1;transform:translateX(0)}}"
            ".ln{opacity:0;animation:in .45s ease-out forwards}"
        )
    out += [
        "</style>",
        f'<rect class="card" x=".5" y=".5" width="{W - 1}" height="{H - 1}" rx="8"/>',
        f'<path class="bar" d="M.5 8.5a8 8 0 0 1 8-8h{W - 17}a8 8 0 0 1 8 8v{BAR_H - 8}H.5z"/>',
        '<circle cx="16" cy="15" r="5" fill="#ff5f56"/>',
        '<circle cx="32" cy="15" r="5" fill="#ffbd2e"/>',
        '<circle cx="48" cy="15" r="5" fill="#27c93f"/>',
        f'<text class="dim" x="{W / 2}" y="19.5" text-anchor="middle">{USER}@{HOST}: ~</text>',
    ]

    def ln(i: int) -> str:
        return "" if STATIC else f' class="ln" style="animation-delay:{0.12 + i * 0.07:.2f}s"'

    y = TOP
    i = 0
    out.append(
        f'<g{ln(i)}><text x="{PAD_X}" y="{y}">'
        f'<tspan class="pr">{USER}</tspan><tspan class="at">@</tspan><tspan class="hn">{HOST}</tspan>'
        f'<tspan class="dim"> ~ $ </tspan>neofetch</text></g>'
    )
    i += 1
    y += LINE_H
    out.append(f'<g{ln(i)}><line x1="{PAD_X}" y1="{y - 4}" x2="{W - PAD_X}" y2="{y - 4}" '
               f'stroke="#30363d" stroke-width="1"/></g>')
    i += 1
    y += LINE_H

    for key, value, colour in rows:
        g = f"<g{ln(i)}>"
        if key:
            g += f'<text class="k" x="{PAD_X}" y="{y}" fill="{colour}" style="fill:{colour}">{escape(key)}</text>'
            g += f'<text class="dim" x="{PAD_X + KEY_W - 14}" y="{y}">:</text>'
        g += f'<text x="{PAD_X + KEY_W}" y="{y}">{escape(value)}</text></g>'
        out.append(g)
        i += 1
        y += LINE_H

    # colour swatches, like neofetch's footer
    y += 6
    sw = f"<g{ln(i)}>"
    for k, c in enumerate(PALETTE):
        sw += f'<rect x="{PAD_X + KEY_W + k * 22}" y="{y - 10}" width="18" height="12" rx="2" fill="{c}"/>'
    sw += "</g>"
    out.append(sw)
    out.append("</svg>")

    OUT.write_text("\n".join(out), encoding="utf-8")
    print(f"wrote {OUT} ({W}x{H})")


if __name__ == "__main__":
    main()
