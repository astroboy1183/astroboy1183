#!/usr/bin/env python3
"""Rebuild README.md from template.md + profile.yaml + live GitHub data.

The README is a BUILD ARTIFACT — edit profile.yaml (facts) or template.md
(skeleton), never README.md. Runs every morning via
.github/workflows/update-now.yml, after the agent fleet's 06:00 wave.

Three tiers of content, three failure rules:
  - curated facts (profile.yaml)      → inserted verbatim; can't fail
  - derived structure (projects table,
    fleet count)                      → API-fed with yaml fallbacks; if a
                                        whole section can't build, ABORT
                                        and keep yesterday's README —
                                        stale beats wrong on a page with
                                        my name on it
  - live activity (the 🔄 Now block)  → individual lines degrade (omit),
                                        never abort

A rendered page with any '{{' left in it also aborts.
"""

import json
import re
import subprocess
import sys
import urllib.request
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent
README = ROOT / "README.md"
TEMPLATE = ROOT / "template.md"
PROFILE = ROOT / "profile.yaml"
RESUME = ROOT / "resume.yaml"

USER = "astroboy1183"
DSA_REPOS = ["Data-Structures-and-Algorithms", "Leetcode-Problems"]
SCHEDULER_RAW = f"repos/{USER}/fleet-scheduler/contents/worker.js"
AUDIT_REPORT = f"repos/{USER}/repo-audit/contents/report/report.json"
FLEET_WATCH = [
    "weather-report", "mail-digest", "news-briefing", "cricket-scores",
    "tech-news", "finance-tracker", "eng-blogs", "repo-review",
]


def gh(args, raw=False):
    """gh api (GET); parsed JSON (or raw text); None on any failure."""
    try:
        out = subprocess.run(
            ["gh", "api", "-X", "GET"] + args,
            capture_output=True, text=True, timeout=60,
        ).stdout
        if not out:
            return None
        return out if raw else json.loads(out)
    except Exception:
        return None


# --- derived: fleet count (from the scheduler's own SCHEDULE) -----------------

def fleet_count(profile):
    """Unique repos in fleet-scheduler's SCHEDULE + the unscheduled agents.
    Falls back to counting the watch-list if the fetch fails — the count
    must never silently become 0."""
    src = gh([SCHEDULER_RAW, "-H", "Accept: application/vnd.github.raw"], raw=True)
    extras = profile.get("unscheduled_agents", [])
    if src:
        repos = set(re.findall(r'repo:\s*"([^"]+)"', src))
        if repos:
            return len(repos) + len(extras)
    return len(FLEET_WATCH) + 1 + len(extras)  # +1: papers (weekly) not in watch list


# --- derived: the projects table -----------------------------------------------

def projects_table(profile):
    """Table rows from repo metadata, ordered by the repo-audit scores.

    Descriptions: the repo's own GitHub description, else the yaml
    fallback. Ordering: audit score desc (unscored last, yaml order).
    Returns None only when NOTHING could be built — the abort signal."""
    entries = profile.get("projects", [])
    if not entries:
        return None
    scores = {}
    report = gh([AUDIT_REPORT, "-H", "Accept: application/vnd.github.raw"], raw=True)
    if report:
        try:
            for row in json.loads(report).get("repos", []):
                if row.get("score"):
                    scores[row["name"]] = row["score"]
        except ValueError:
            pass  # unreadable report → keep yaml order

    rows, fetched_any = [], False
    for i, entry in enumerate(entries):
        name = entry["repo"]
        meta = gh([f"repos/{USER}/{name}"])
        if isinstance(meta, dict) and "name" in meta:
            fetched_any = True
            desc = (meta.get("description") or "").strip() or entry.get("fallback", "")
            lang = meta.get("language") or ""
        else:
            desc = entry.get("fallback", "")
            lang = ""
        if lang:
            desc = f"{desc} ({lang})"
        rows.append((scores.get(name, -i), name, desc))
    if not fetched_any:
        return None  # GitHub fully unreachable → abort, keep yesterday's page

    rows.sort(key=lambda r: -r[0] if r[0] > 0 else 1000 - r[0])
    lines = ["| Project | What it is |", "|---|---|"]
    for _, name, desc in rows:
        lines.append(f"| [{name}](https://github.com/{USER}/{name}) | {desc} |")
    return "\n".join(lines)


# --- live: the 🔄 Now block ------------------------------------------------------

def dsa_streak():
    days = set()
    for repo in DSA_REPOS:
        since = (datetime.now(timezone.utc) - timedelta(days=45)).isoformat()
        commits = gh([f"repos/{USER}/{repo}/commits", "-f", f"since={since}",
                      "-f", "per_page=100"])
        if not isinstance(commits, list):
            continue
        for c in commits:
            if isinstance(c, dict):
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
    """Commit-search: my own authored commits this week (bot commits are
    authored by github-actions, so they never count)."""
    week = (date.today() - timedelta(days=7)).isoformat()
    res = gh([
        "search/commits",
        "-f", f"q=author:{USER} committer-date:>={week}",
        "-f", "sort=committer-date", "-f", "order=desc", "-f", "per_page=50",
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
    y = (date.today() - timedelta(days=1)).isoformat()
    green = 0
    for repo in FLEET_WATCH:
        runs = gh([f"repos/{USER}/{repo}/actions/runs",
                   "-f", f"created={y}..{y}", "-f", "per_page=20"])
        if not isinstance(runs, dict):
            return None
        green += any(
            r.get("conclusion") == "success"
            and r.get("event") in ("schedule", "workflow_dispatch")
            for r in runs.get("workflow_runs", [])
        )
    return green


def now_block():
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
        lines.append(f"🤖 agent fleet: **{green}/{len(FLEET_WATCH)} green** yesterday")
    stamp = datetime.now(timezone.utc).strftime("%d %b %Y")
    lines.append(f"<sub>last updated {stamp} — automatically</sub>")
    return "<!--NOW-START-->\n" + "\n\n".join(lines) + "\n<!--NOW-END-->"


# --- derived: career sections (from resume.yaml + live Credly) ----------------

def credly_badges(user):
    """[{name, year}] from a PUBLIC Credly profile — the zero-touch cert
    source: pass an exam, the badge appears, the README follows.
    [] on any failure; the resume.yaml baseline always stands."""
    if not user:
        return []
    try:
        req = urllib.request.Request(
            f"https://www.credly.com/users/{user}/badges.json",
            headers={"User-Agent": "profile-readme-builder/1.0"},
        )
        with urllib.request.urlopen(req, timeout=20) as resp:
            data = json.load(resp)
        out = []
        for b in data.get("data", []):
            name = (b.get("badge_template") or {}).get("name", "").strip()
            issued = (b.get("issued_at") or "")[:4]
            if name and issued.isdigit():
                out.append({"name": name, "year": int(issued)})
        return out
    except Exception:
        return []


def merged_certifications(resume):
    """resume.yaml baseline ∪ live Credly badges, deduped by normalized
    name, newest first."""
    certs = {c["name"].strip().casefold(): dict(c)
             for c in resume.get("certifications", [])}
    for badge in credly_badges(resume.get("credly_user")):
        certs.setdefault(badge["name"].strip().casefold(), badge)
    return sorted(certs.values(), key=lambda c: (-c["year"], c["name"]))


def certifications_line(certs):
    return "**Certifications:** " + " ·\n".join(
        f"{c['name']} ({c['year']})" for c in certs
    )


def experience_block(resume):
    lines = []
    for job in resume.get("work", []):
        role = job.get("role", "")
        head = f"**{job['org']}**" + (f" — {role}" if role else "")
        if job.get("current"):
            head += " *(current)*"
        lines.append(f"- {head}: {job['note']}")
    parts = ["\n".join(lines)]
    if resume.get("publication"):
        parts.append(resume["publication"].strip())
    if resume.get("experience_footer"):
        parts.append(resume["experience_footer"].strip())
    return "\n\n".join(parts)


def about_slots(resume):
    cur = resume.get("current", {})
    return {
        "CURRENT_ROLE": cur.get("role", "data engineer"),
        "CURRENT_COMPANY_LINK":
            f"**[{cur.get('company', '?')}]({cur.get('company_url', '')})**",
        "CURRENT_FOCUS": cur.get("focus", ""),
        "YEARS": resume.get("years_experience", ""),
    }


# --- assembly --------------------------------------------------------------------

def build():
    profile = yaml.safe_load(PROFILE.read_text())
    resume = yaml.safe_load(RESUME.read_text())
    template = TEMPLATE.read_text()

    table = projects_table(profile)
    if table is None:
        sys.exit("ABORT: projects table could not be built — keeping yesterday's README")

    certs = merged_certifications(resume)
    if not certs:
        sys.exit("ABORT: certification list came out empty — keeping yesterday's README")

    count = fleet_count(profile)
    values = {
        "CREDIBILITY": profile["credibility"].strip(),
        "ABOUT": profile["about"].strip(),
        "CERTIFICATIONS": certifications_line(certs),
        "EXPERIENCE": experience_block(resume),
        "PROJECTS_TABLE": table,
        "CURRENTLY_BUILDING": profile["currently_building"].strip(),
        "FLEET": profile["fleet"].strip(),
        "LEARNING": profile["learning"].strip(),
        "NOW": now_block(),
    }
    page = template
    for key, val in values.items():
        page = page.replace("{{" + key + "}}", val)
    page = page.replace("{{FLEET_COUNT}}", str(count))
    page = page.replace("{{CERT_COUNT}}", str(len(certs)))
    for slot, val in about_slots(resume).items():
        page = page.replace("{{" + slot + "}}", val)

    leftover = re.findall(r"{{\w+}}", page)
    if leftover:
        sys.exit(f"ABORT: unrendered placeholders {leftover} — keeping yesterday's README")
    return page


def main():
    page = build()
    if README.read_text() != page:
        README.write_text(page)
        print("README rebuilt")
    else:
        print("no change")


if __name__ == "__main__":
    main()