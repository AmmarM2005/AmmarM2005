#!/usr/bin/env python3
"""
generate_stats.py

Pulls contribution + language data from the GitHub GraphQL API using only
the standard library (no deps to break in CI) and draws four SVGs in the
same visual language as the portrait:

  stats.svg   - hero total + weekly sparkline (columns, not a line — daily
                contribution counts are sparse/discrete, a line would imply
                values that never existed)
  streak.svg  - current + longest streak, with date ranges
  langs.svg   - top languages by bytes and by repo count
  year.svg    - one character per day for the last 365 days, using the
                portrait's own 13-char brightness ramp

Determinism:
  - the contribution window is pinned to whole UTC days (today-364 at
    00:00:00Z through today at 23:59:59Z), so re-runs minutes apart don't
    shift day-to-week bucketing and produce a diff every night
  - repos are filtered to privacy: PUBLIC so the numbers don't depend on
    whether the token running the script can see private repos

Env vars required: GITHUB_TOKEN, GH_LOGIN
"""

import json
import os
import sys
import urllib.request
from datetime import datetime, timedelta, timezone

RAMP = " .`:-=+*cs#%@"
API_URL = "https://api.github.com/graphql"

QUERY = """
query($login: String!, $from: DateTime!, $to: DateTime!) {
  user(login: $login) {
    contributionsCollection(from: $from, to: $to) {
      contributionCalendar {
        totalContributions
        weeks {
          contributionDays { date contributionCount }
        }
      }
    }
    repositories(first: 100, privacy: PUBLIC, isFork: false,
                  ownerAffiliations: OWNER, orderBy: {field: UPDATED_AT, direction: DESC}) {
      nodes {
        name
        languages(first: 10, orderBy: {field: SIZE, direction: DESC}) {
          edges { size node { name color } }
        }
      }
    }
  }
}
"""


def gql(token: str, login: str, dt_from: str, dt_to: str) -> dict:
    body = json.dumps({
        "query": QUERY,
        "variables": {"login": login, "from": dt_from, "to": dt_to},
    }).encode()
    req = urllib.request.Request(
        API_URL,
        data=body,
        headers={
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
            "User-Agent": login,
        },
    )
    with urllib.request.urlopen(req) as resp:
        payload = json.loads(resp.read())
    if "errors" in payload:
        raise RuntimeError(payload["errors"])
    return payload["data"]["user"]


def flatten_days(calendar: dict) -> list[dict]:
    days = []
    for week in calendar["weeks"]:
        days.extend(week["contributionDays"])
    return days


def compute_streaks(days: list[dict]) -> dict:
    today = datetime.now(timezone.utc).date()
    counts = {d["date"]: d["contributionCount"] for d in days}

    # current streak: walk backwards from today (or yesterday if today is 0
    # and still "in progress")
    cur = 0
    cursor = today
    while True:
        key = cursor.isoformat()
        if counts.get(key, 0) > 0:
            cur += 1
            cursor -= timedelta(days=1)
        else:
            if cursor == today:
                cursor -= timedelta(days=1)
                continue
            break
    cur_end = today

    # longest streak over the window
    longest = 0
    longest_end = None
    run = 0
    for d in days:
        if d["contributionCount"] > 0:
            run += 1
            if run > longest:
                longest = run
                longest_end = d["date"]
        else:
            run = 0

    return {
        "current": cur,
        "current_end": cur_end.isoformat(),
        "longest": longest,
        "longest_end": longest_end,
    }


def compute_languages(repos: list[dict]) -> list[dict]:
    totals: dict[str, dict] = {}
    for repo in repos:
        seen_in_repo = set()
        for edge in repo["languages"]["edges"]:
            name = edge["node"]["name"]
            color = edge["node"]["color"] or "#57606a"
            size = edge["size"]
            entry = totals.setdefault(name, {"bytes": 0, "repos": 0, "color": color})
            entry["bytes"] += size
            if name not in seen_in_repo:
                entry["repos"] += 1
                seen_in_repo.add(name)
    ranked = sorted(totals.items(), key=lambda kv: kv[1]["bytes"], reverse=True)
    return [{"name": n, **v} for n, v in ranked[:6]]


# ---------------------------------------------------------------- SVG helpers

def svg_wrap(width: int, height: int, body: str, label: str) -> str:
    return (
        f'<svg viewBox="0 0 {width} {height}" width="{width}" '
        f'xmlns="http://www.w3.org/2000/svg" role="img" aria-label="{label}">'
        f'{body}</svg>'
    )


def hero_svg(total: int, days: list[dict]) -> str:
    weeks: list[int] = []
    for i in range(0, len(days), 7):
        weeks.append(sum(d["contributionCount"] for d in days[i:i + 7]))
    weeks = weeks[-26:]  # last ~26 weeks for a compact sparkline
    w, h = 460, 140
    bar_w = (w - 20) / max(len(weeks), 1)
    max_v = max(weeks) or 1
    bars = []
    for i, v in enumerate(weeks):
        bh = (v / max_v) * 60
        x = 10 + i * bar_w
        y = 90 - bh
        bars.append(f'<rect x="{x:.1f}" y="{y:.1f}" width="{bar_w * 0.7:.1f}" '
                     f'height="{bh:.1f}" fill="#39d353" rx="1"/>')
    body = (
        f'<text x="10" y="30" font-family="ui-monospace,monospace" font-size="26" '
        f'fill="#24292f">{total:,}</text>'
        f'<text x="10" y="46" font-family="ui-monospace,monospace" font-size="11" '
        f'fill="#57606a">contributions, last 365 days</text>'
        + "".join(bars)
    )
    return svg_wrap(w, h, body, "contribution total and weekly sparkline")


def streak_svg(streaks: dict) -> str:
    w, h = 460, 90
    body = (
        f'<text x="10" y="28" font-family="ui-monospace,monospace" font-size="20" '
        f'fill="#24292f">current streak: {streaks["current"]}d</text>'
        f'<text x="10" y="46" font-family="ui-monospace,monospace" font-size="11" '
        f'fill="#57606a">through {streaks["current_end"]}</text>'
        f'<text x="10" y="68" font-family="ui-monospace,monospace" font-size="20" '
        f'fill="#24292f">longest streak: {streaks["longest"]}d</text>'
        f'<text x="10" y="84" font-family="ui-monospace,monospace" font-size="11" '
        f'fill="#57606a">ending {streaks["longest_end"]}</text>'
    )
    return svg_wrap(w, h, body, "current and longest contribution streak")


def langs_svg(langs: list[dict]) -> str:
    w = 460
    row_h = 22
    h = 20 + row_h * len(langs)
    total_bytes = sum(l["bytes"] for l in langs) or 1
    rows = []
    for i, l in enumerate(langs):
        y = 20 + i * row_h
        pct = l["bytes"] / total_bytes * 100
        bar_w = pct / 100 * 260
        rows.append(
            f'<text x="10" y="{y}" font-family="ui-monospace,monospace" font-size="12" '
            f'fill="#24292f">{l["name"]}</text>'
            f'<rect x="120" y="{y - 10}" width="260" height="10" fill="#21262d" rx="2"/>'
            f'<rect x="120" y="{y - 10}" width="{bar_w:.1f}" height="10" '
            f'fill="{l["color"]}" rx="2"/>'
            f'<text x="390" y="{y}" font-family="ui-monospace,monospace" font-size="11" '
            f'fill="#57606a">{pct:.0f}%</text>'
        )
    return svg_wrap(w, h, "".join(rows), "top languages by bytes")


def year_svg(days: list[dict]) -> str:
    """One character per day, 7 rows (Sun-Sat) x ~53 cols, using the ramp."""
    counts = [d["contributionCount"] for d in days]
    max_v = max(counts) if counts else 1
    max_v = max_v or 1
    n = len(RAMP) - 1
    cell = 8
    cols = (len(days) + 6) // 7
    w = cols * cell + 10
    h = 7 * cell + 10
    glyphs = []
    for i, d in enumerate(days):
        col = i // 7
        row = i % 7
        idx = min(n, int((d["contributionCount"] / max_v) * n)) if max_v else 0
        ch = RAMP[idx]
        x = 5 + col * cell
        y = 5 + row * cell + cell * 0.8
        glyphs.append(
            f'<text x="{x}" y="{y:.1f}" font-family="ui-monospace,monospace" '
            f'font-size="{cell}" fill="#39d353">{ch}</text>'
        )
    return svg_wrap(w, h, "".join(glyphs), "contributions per day, last year")


def main():
    token = os.environ["GITHUB_TOKEN"]
    login = os.environ["GH_LOGIN"]

    now = datetime.now(timezone.utc)
    today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    dt_from = (today_start - timedelta(days=364)).isoformat().replace("+00:00", "Z")
    dt_to = today_start.replace(hour=23, minute=59, second=59).isoformat().replace("+00:00", "Z")

    user = gql(token, login, dt_from, dt_to)
    calendar = user["contributionsCollection"]["contributionCalendar"]
    days = flatten_days(calendar)
    total = calendar["totalContributions"]
    streaks = compute_streaks(days)
    langs = compute_languages(user["repositories"]["nodes"])

    with open("stats.svg", "w") as f:
        f.write(hero_svg(total, days))
    with open("streak.svg", "w") as f:
        f.write(streak_svg(streaks))
    with open("langs.svg", "w") as f:
        f.write(langs_svg(langs))
    with open("year.svg", "w") as f:
        f.write(year_svg(days))

    print(f"total={total} current_streak={streaks['current']} "
          f"longest_streak={streaks['longest']} langs={[l['name'] for l in langs]}")


if __name__ == "__main__":
    main()

