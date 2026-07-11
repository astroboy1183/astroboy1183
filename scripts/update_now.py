#!/usr/bin/env python3
"""Refresh the 🔄 Now section of the profile README.

Runs daily via .github/workflows/update-now.yml (06:15 IST, after the
agent fleet's 06:00 wave). Everything here is PUBLIC data read through
the GitHub API — my own activity and my agents' run results — rewritten
between the NOW-START/NOW-END markers. If any lookup fails its line is
simply omitted; the section degrades, the workflow never breaks.
"""

import json
import re
import subprocess
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

README = Path(__file__).resolve().parent.parent / "README.md"
USER = "astroboy1183"
DSA_REPOS = ["Data-Structures-and-Algorithms", "Leetcode-Problems"]
FLEET = [
    "weather-report", "mail-digest", "news-briefing", "cricket-scores",
    "tech-news", "finance-tracker", "eng-blogs", "repo-review",
]


def gh(args):
    """gh api (GET), parsed JSON; None on any failure (lines degrade).

    -X GET matters: gh api switches to POST whenever -f fields are
    present. Non-list replies (error objects) are treated as failures
    by the callers that expect lists."""
    try:
        out = subprocess.run(
            ["gh", "api", "-X", "GET"] + args,
            capture_output=True, text=True, timeout=60,
        ).stdout
        return json.loads(out) if out else None
    except Exception:
        return None


def dsa_streak():
    """Consecutive days (ending today or yesterday) with a commit in any
    DSA repo."""
    days = set()
    for repo in DSA_REPOS:
        since = (datetime.now(timezone.utc) - timedelta(days=45)).isoformat()
        commits = gh([f"repos/{USER}/{repo}/commits", "-f", f"since={since}",
                      "-f", "per_page=100"])
        if not isinstance(commits, list):
            continue  # empty repo / API error — the other repo still counts
        for c in commits:
            stamp = (c.get("commit", {}).get("author", {}) or {}).get("date", "")
            if stamp:
                days.add(stamp[:10])
    if not days:
        return 0
    day = date.today()
    if day.isoformat() not in days:  # today's practice may not be pushed yet
        day -= timedelta(days=1)
    streak = 0
    while day.isoformat() in days:
        streak += 1
        day -= timedelta(days=1)
    return streak


def recent_activity():
    """(commits in the last 7 days, repos touched, last commit subject+repo)
    via the commit-search API — the events feed no longer carries commit
    payloads. author:me naturally excludes the agents' bot commits."""
    week = (date.today() - timedelta(days=7)).isoformat()
    res = gh([
        "search/commits",
        "-f", f"q=author:{USER} committer-date:>={week}",
        "-f", "sort=committer-date", "-f", "order=desc",
        "-f", "per_page=50",
    ])
    if not isinstance(res, dict):
        return 0, 0, None
    items = res.get("items", [])
    repos = {i.get("repository", {}).get("name", "") for i in items} - {""}
    last = None
    for i in items:
        msg = (i.get("commit", {}).get("message", "") or "").splitlines()[0]
        if msg and msg != "Now: daily refresh":
            last = (msg[:60], i.get("repository", {}).get("name", ""))
            break
    return res.get("total_count", 0), len(repos), last


def fleet_green():
    """How many fleet agents had a successful scheduled run yesterday."""
    y = (date.today() - timedelta(days=1)).isoformat()
    green = 0
    for repo in FLEET:
        runs = gh([f"repos/{USER}/{repo}/actions/runs",
                   "-f", f"created={y}..{y}", "-f", "per_page=20"])
        if not isinstance(runs, dict):
            return None  # API trouble → omit the line rather than lie
        ok = any(
            r.get("conclusion") == "success"
            and r.get("event") in ("schedule", "workflow_dispatch")
            for r in runs.get("workflow_runs", [])
        )
        green += ok
    return green


def build_lines():
    lines = []
    streak = dsa_streak()
    if streak:
        lines.append(f"🧩 **DSA streak: {streak} day{'s' if streak != 1 else ''}**")
    commits, repos, last = recent_activity()
    if commits:
        lines.append(f"⚙️ **{commits} commits** across {repos} repos this week")
    if last:
        subject, repo = last
        lines.append(f'🚢 last shipped: *"{subject}"* in `{repo}`')
    green = fleet_green()
    if green is not None:
        lines.append(f"🤖 agent fleet: **{green}/{len(FLEET)} green** yesterday")
    stamp = datetime.now(timezone.utc).strftime("%d %b %Y")
    lines.append(f"<sub>last updated {stamp} — automatically</sub>")
    return lines


def main():
    text = README.read_text()
    block = "\n\n".join(build_lines())
    new = re.sub(
        r"<!--NOW-START-->.*?<!--NOW-END-->",
        f"<!--NOW-START-->\n{block}\n<!--NOW-END-->",
        text,
        flags=re.S,
    )
    if new != text:
        README.write_text(new)
        print("README updated")
    else:
        print("no change")


if __name__ == "__main__":
    main()