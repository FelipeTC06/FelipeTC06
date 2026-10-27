"""Fetch the last year of contributions for a GitHub user.

Preferred source: the GraphQL API (`contributionsCollection.contributionCalendar`),
authenticated with a token in $CONTRIB_TOKEN (falls back to $GITHUB_TOKEN).
When the token belongs to the profile owner, the calendar includes private
contributions. Only per-day totals are stored: date, count and level. No
repository names, commit messages or any other private detail ever leave
the API response.

Fallback (no token): scrape the public HTML fragment at
https://github.com/users/<user>/contributions, which only includes private
contributions if "Include private contributions on my profile" is enabled.

Usage:
    python scripts/fetch_contributions.py [username] [output.json]
"""
import datetime as dt
import json
import os
import re
import sys
from pathlib import Path

import requests

USER = sys.argv[1] if len(sys.argv) > 1 else "FelipeTC06"
OUT = Path(sys.argv[2]) if len(sys.argv) > 2 else Path("data/contributions.json")
TOKEN = os.environ.get("CONTRIB_TOKEN") or os.environ.get("GITHUB_TOKEN")

LEVELS = {"NONE": 0, "FIRST_QUARTILE": 1, "SECOND_QUARTILE": 2,
          "THIRD_QUARTILE": 3, "FOURTH_QUARTILE": 4}

QUERY = """
query($login: String!) {
  user(login: $login) {
    contributionsCollection {
      contributionCalendar {
        totalContributions
        weeks { contributionDays { date contributionCount contributionLevel } }
      }
    }
  }
}
"""


def fetch_graphql() -> tuple[list[dict], str]:
    r = requests.post(
        "https://api.github.com/graphql",
        json={"query": QUERY, "variables": {"login": USER}},
        headers={"Authorization": f"bearer {TOKEN}", "User-Agent": "profile-readme-refresh"},
        timeout=30,
    )
    r.raise_for_status()
    body = r.json()
    if "errors" in body:
        raise RuntimeError(body["errors"])
    cal = body["data"]["user"]["contributionsCollection"]["contributionCalendar"]
    days = [
        {"date": d["date"], "count": d["contributionCount"], "level": LEVELS.get(d["contributionLevel"], 0)}
        for w in cal["weeks"] for d in w["contributionDays"]
    ]
    return days, "graphql"


COUNT_RE = re.compile(r"^\s*(No|\d[\d,]*)\s+contribution")


def fetch_html() -> tuple[list[dict], str]:
    from bs4 import BeautifulSoup

    html = requests.get(f"https://github.com/users/{USER}/contributions",
                        headers={"User-Agent": "profile-readme-refresh"}, timeout=30).text
    soup = BeautifulSoup(html, "html.parser")
    tips = {t["for"]: t.get_text(" ", strip=True) for t in soup.select("tool-tip[for]")}
    days = []
    for td in soup.select("td.ContributionCalendar-day[data-date]"):
        level = int(td.get("data-level", "0"))
        m = COUNT_RE.match(tips.get(td.get("id", ""), td.get_text(" ", strip=True)))
        if m:
            count = 0 if m.group(1) == "No" else int(m.group(1).replace(",", ""))
        else:
            count = {0: 0, 1: 1, 2: 4, 3: 8, 4: 12}[level]
        days.append({"date": td["data-date"], "count": count, "level": level})
    if not days:
        raise SystemExit("no contribution cells found: GitHub markup may have changed")
    return days, "html"


def streaks(days: list[dict]) -> tuple[int, int]:
    longest = cur = 0
    for d in days:
        cur = cur + 1 if d["count"] > 0 else 0
        longest = max(longest, cur)
    current = 0
    tail = days[::-1]
    if tail and tail[0]["count"] == 0:
        tail = tail[1:]  # today may still be empty
    for d in tail:
        if d["count"] > 0:
            current += 1
        else:
            break
    return current, longest


def main() -> None:
    if TOKEN:
        try:
            days, source = fetch_graphql()
        except Exception as exc:  # token without access, API hiccup...
            print(f"GraphQL failed ({exc}); falling back to public HTML")
            days, source = fetch_html()
    else:
        days, source = fetch_html()

    days.sort(key=lambda d: d["date"])
    current, longest = streaks(days)
    best = max(days, key=lambda d: d["count"])
    data = {
        "user": USER,
        "source": source,
        "fetched_at": dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "total": sum(d["count"] for d in days),
        "best_day": {"date": best["date"], "count": best["count"]},
        "current_streak": current,
        "longest_streak": longest,
        "days": days,
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(data, indent=1), encoding="utf-8")
    print(f"wrote {OUT} from {source}: {len(days)} days, {data['total']} contributions, "
          f"best {best['count']} on {best['date']}, streak {current} (longest {longest})")


if __name__ == "__main__":
    main()
