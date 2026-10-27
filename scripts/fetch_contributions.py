"""Fetch the last year of contributions for a GitHub user.

Scrapes the public HTML fragment at
https://github.com/users/<user>/contributions (no token needed) and writes
data/contributions.json with one entry per day plus streak totals.

Usage:
    python scripts/fetch_contributions.py [username] [output.json]
"""
import datetime as dt
import json
import re
import sys
from pathlib import Path

import requests
from bs4 import BeautifulSoup

USER = sys.argv[1] if len(sys.argv) > 1 else "FelipeTC06"
OUT = Path(sys.argv[2]) if len(sys.argv) > 2 else Path("data/contributions.json")

URL = f"https://github.com/users/{USER}/contributions"
COUNT_RE = re.compile(r"^\s*(No|\d[\d,]*)\s+contribution")


def fetch() -> list[dict]:
    html = requests.get(URL, headers={"User-Agent": "profile-readme-refresh"}, timeout=30).text
    soup = BeautifulSoup(html, "html.parser")

    tips: dict[str, str] = {}
    for tip in soup.select("tool-tip[for]"):
        tips[tip["for"]] = tip.get_text(" ", strip=True)

    days = []
    for td in soup.select("td.ContributionCalendar-day[data-date]"):
        date = td["data-date"]
        level = int(td.get("data-level", "0"))
        text = tips.get(td.get("id", ""), td.get_text(" ", strip=True))
        m = COUNT_RE.match(text)
        if m:
            count = 0 if m.group(1) == "No" else int(m.group(1).replace(",", ""))
        else:
            count = {0: 0, 1: 1, 2: 4, 3: 8, 4: 12}[level]  # rough fallback
        days.append({"date": date, "count": count, "level": level})

    days.sort(key=lambda d: d["date"])
    if not days:
        raise SystemExit("no contribution cells found: GitHub markup may have changed")
    return days


def streaks(days: list[dict]) -> tuple[int, int]:
    longest = cur = 0
    for d in days:
        cur = cur + 1 if d["count"] > 0 else 0
        longest = max(longest, cur)
    # current streak: count back from the last day, allowing today to be empty
    current = 0
    tail = days[::-1]
    if tail and tail[0]["count"] == 0:
        tail = tail[1:]
    for d in tail:
        if d["count"] > 0:
            current += 1
        else:
            break
    return current, longest


def main() -> None:
    days = fetch()
    current, longest = streaks(days)
    data = {
        "user": USER,
        "fetched_at": dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "total": sum(d["count"] for d in days),
        "current_streak": current,
        "longest_streak": longest,
        "days": days,
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(data, indent=1), encoding="utf-8")
    print(f"wrote {OUT}: {len(days)} days, {data['total']} contributions, "
          f"streak {current} (longest {longest})")


if __name__ == "__main__":
    main()
