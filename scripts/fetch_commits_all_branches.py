"""Count the user's commits on EVERY branch of every repository they own.

GitHub's contribution calendar only counts commits on the default branch.
This script walks each repository's branches through the GraphQL API,
collects commits authored by the user in the last year, de-duplicates them
by commit id (a commit on three branches counts once) and buckets them by
day. Only per-day totals are written: no repository names, branch names,
messages or ids leave this script.

Needs $CONTRIB_TOKEN (classic PAT with `repo`, or fine-grained with
Contents: read on all repos). Without it, falls back to
fetch_contributions.py (the public calendar).

Usage:
    python scripts/fetch_commits_all_branches.py [username] [output.json]
"""
import datetime as dt
import json
import os
import subprocess
import sys
import time
from pathlib import Path

import requests

USER = sys.argv[1] if len(sys.argv) > 1 else "FelipeTC06"
OUT = Path(sys.argv[2]) if len(sys.argv) > 2 else Path("data/contributions.json")
TOKEN = os.environ.get("CONTRIB_TOKEN")
API = "https://api.github.com/graphql"

Q_VIEWER = "query { viewer { id login } }"

Q_REPOS = """
query($after: String) {
  viewer {
    repositories(first: 50, after: $after, affiliations: [OWNER, COLLABORATOR, ORGANIZATION_MEMBER],
                 ownerAffiliations: [OWNER, COLLABORATOR, ORGANIZATION_MEMBER], isFork: false) {
      pageInfo { hasNextPage endCursor }
      nodes { nameWithOwner isEmpty pushedAt }
    }
  }
}
"""

Q_BRANCHES = """
query($owner: String!, $name: String!, $after: String) {
  repository(owner: $owner, name: $name) {
    refs(refPrefix: "refs/heads/", first: 100, after: $after) {
      pageInfo { hasNextPage endCursor }
      nodes { name target { ... on Commit { committedDate } } }
    }
  }
}
"""

Q_HISTORY = """
query($owner: String!, $name: String!, $ref: String!, $since: GitTimestamp!, $author: ID!, $after: String) {
  repository(owner: $owner, name: $name) {
    ref(qualifiedName: $ref) {
      target {
        ... on Commit {
          history(first: 100, since: $since, author: {id: $author}, after: $after) {
            pageInfo { hasNextPage endCursor }
            nodes { oid authoredDate }
          }
        }
      }
    }
  }
}
"""


def gql(query: str, variables: dict | None = None) -> dict:
    for attempt in range(4):
        r = requests.post(API, json={"query": query, "variables": variables or {}},
                          headers={"Authorization": f"bearer {TOKEN}", "User-Agent": "profile-readme-refresh"},
                          timeout=60)
        if r.status_code in (502, 503) or (r.status_code == 403 and "rate limit" in r.text.lower()):
            time.sleep(5 * (attempt + 1))
            continue
        r.raise_for_status()
        body = r.json()
        if "errors" in body and not body.get("data"):
            raise RuntimeError(body["errors"])
        return body["data"]
    raise RuntimeError("GraphQL kept failing")


def main() -> None:
    if not TOKEN:
        print("CONTRIB_TOKEN not set; falling back to the public contribution calendar")
        subprocess.run([sys.executable, "scripts/fetch_contributions.py", USER, str(OUT)], check=True)
        return

    viewer = gql(Q_VIEWER)["viewer"]
    author_id = viewer["id"]
    today = dt.datetime.now(dt.timezone.utc).date()
    since_date = today - dt.timedelta(days=364)
    since = since_date.isoformat() + "T00:00:00Z"

    repos, after = [], None
    while True:
        page = gql(Q_REPOS, {"after": after})["viewer"]["repositories"]
        repos += [n for n in page["nodes"] if not n["isEmpty"]
                  and n["pushedAt"] and n["pushedAt"][:10] >= since_date.isoformat()]
        if not page["pageInfo"]["hasNextPage"]:
            break
        after = page["pageInfo"]["endCursor"]

    seen: set[str] = set()
    per_day: dict[str, int] = {}
    scanned_branches = 0
    for repo in repos:
        owner, name = repo["nameWithOwner"].split("/")
        branches, after = [], None
        while True:
            page = gql(Q_BRANCHES, {"owner": owner, "name": name, "after": after})["repository"]["refs"]
            branches += [b["name"] for b in page["nodes"]
                         if b["target"] and b["target"].get("committedDate", "")[:10] >= since_date.isoformat()]
            if not page["pageInfo"]["hasNextPage"]:
                break
            after = page["pageInfo"]["endCursor"]
        for branch in branches:
            scanned_branches += 1
            after = None
            while True:
                ref = gql(Q_HISTORY, {"owner": owner, "name": name, "ref": f"refs/heads/{branch}",
                                      "since": since, "author": author_id, "after": after})["repository"]["ref"]
                if not ref:
                    break
                hist = ref["target"]["history"]
                for c in hist["nodes"]:
                    if c["oid"] in seen:
                        continue
                    seen.add(c["oid"])
                    day = c["authoredDate"][:10]
                    per_day[day] = per_day.get(day, 0) + 1
                if not hist["pageInfo"]["hasNextPage"]:
                    break
                after = hist["pageInfo"]["endCursor"]

    days = []
    for i in range(365):
        d = (since_date + dt.timedelta(days=i)).isoformat()
        days.append({"date": d, "count": per_day.get(d, 0), "level": 0})

    # levels: quartiles of the non-zero days, like GitHub does
    nonzero = sorted(x["count"] for x in days if x["count"])
    if nonzero:
        q = [nonzero[int(len(nonzero) * p)] if len(nonzero) > 1 else nonzero[0] for p in (0.25, 0.5, 0.75)]
        for x in days:
            c = x["count"]
            x["level"] = 0 if c == 0 else 1 if c <= q[0] else 2 if c <= q[1] else 3 if c <= q[2] else 4

    longest = cur = 0
    for x in days:
        cur = cur + 1 if x["count"] else 0
        longest = max(longest, cur)
    current = 0
    tail = days[::-1]
    if tail and tail[0]["count"] == 0:
        tail = tail[1:]
    for x in tail:
        if x["count"]:
            current += 1
        else:
            break
    best = max(days, key=lambda x: x["count"])

    data = {
        "user": USER,
        "source": "commits-all-branches",
        "fetched_at": dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "total": len(seen),
        "best_day": {"date": best["date"], "count": best["count"]},
        "current_streak": current,
        "longest_streak": longest,
        "days": days,
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(data, indent=1), encoding="utf-8")
    print(f"wrote {OUT}: {len(seen)} unique commits across {len(repos)} repos / {scanned_branches} branches, "
          f"best {best['count']} on {best['date']}, streak {current} (longest {longest})")


if __name__ == "__main__":
    main()
