#!/usr/bin/env python3
"""Render a self-hosted contribution-streak card as SVG.

Computes total contributions, current streak and longest streak from the
GitHub GraphQL contribution calendar (walked year by year from account
creation). No third-party service, no dependencies. Writes SVG to stdout;
exits non-zero printing nothing on any failure so the workflow's validate
step keeps the previous snapshot.

Env: GH_USERNAME (default: vanshdev0101), GITHUB_TOKEN (or GH_TOKEN).
"""
import json
import os
import sys
import urllib.request
from datetime import date, datetime, timedelta, timezone

USER = os.environ.get("GH_USERNAME", "vanshdev0101")
TOKEN = os.environ.get("GITHUB_TOKEN") or os.environ.get("GH_TOKEN")


def graphql(query, variables):
    body = json.dumps({"query": query, "variables": variables}).encode()
    req = urllib.request.Request(
        "https://api.github.com/graphql",
        data=body,
        headers={
            "Authorization": f"bearer {TOKEN}",
            "Content-Type": "application/json",
            "User-Agent": f"{USER}-profile-streak-card",
        },
    )
    with urllib.request.urlopen(req, timeout=30) as resp:
        payload = json.load(resp)
    if payload.get("errors"):
        raise RuntimeError(payload["errors"])
    return payload["data"]


def created_at():
    data = graphql("query($login:String!){user(login:$login){createdAt}}", {"login": USER})
    return datetime.fromisoformat(data["user"]["createdAt"].replace("Z", "+00:00"))


def day_counts(start_dt):
    """dict: date -> contributionCount, from account creation to today."""
    q = """
    query($login:String!,$from:DateTime!,$to:DateTime!){
      user(login:$login){
        contributionsCollection(from:$from,to:$to){
          contributionCalendar{ weeks{ contributionDays{ date contributionCount } } }
        }
      }
    }"""
    counts = {}
    now = datetime.now(timezone.utc)
    cur = start_dt
    while cur < now:
        nxt = min(cur.replace(year=cur.year + 1), now)
        data = graphql(q, {
            "login": USER,
            "from": cur.isoformat(),
            "to": nxt.isoformat(),
        })
        weeks = data["user"]["contributionsCollection"]["contributionCalendar"]["weeks"]
        for wk in weeks:
            for d in wk["contributionDays"]:
                counts[date.fromisoformat(d["date"])] = d["contributionCount"]
        cur = nxt
    return counts


def fmt(d):
    return f"{d.strftime('%b')} {d.day}"


def compute(counts):
    days = sorted(counts)
    total = sum(counts.values())

    # longest streak
    longest = 0
    long_start = long_end = None
    run = 0
    run_start = None
    for d in days:
        if counts[d] > 0:
            run = run + 1 if run else 1
            run_start = run_start or d
            if run > longest:
                longest, long_start, long_end = run, run_start, d
        else:
            run = 0
            run_start = None

    # current streak: walk back from today; today may be 0 and not break it
    today = date.today()
    cur = today if counts.get(today, 0) > 0 else today - timedelta(days=1)
    current = 0
    cur_start = None
    while counts.get(cur, 0) > 0:
        current += 1
        cur_start = cur
        cur -= timedelta(days=1)

    if current and cur_start != today:
        cur_range = f"{fmt(cur_start)} - {fmt(today)}"
    else:
        cur_range = fmt(today)

    long_range = f"{fmt(long_start)} - {fmt(long_end)}" if longest else fmt(today)
    return total, current, cur_range, longest, long_range


TEMPLATE = """<svg xmlns='http://www.w3.org/2000/svg' xmlns:xlink='http://www.w3.org/1999/xlink'
                style='isolation: isolate' viewBox='0 0 495 195' width='495px' height='195px' direction='ltr'>
        <style>
            @keyframes currstreak {{
                0% {{ font-size: 3px; opacity: 0.2; }}
                80% {{ font-size: 34px; opacity: 1; }}
                100% {{ font-size: 28px; opacity: 1; }}
            }}
            @keyframes fadein {{
                0% {{ opacity: 0; }}
                100% {{ opacity: 1; }}
            }}
        </style>
        <defs>
            <clipPath id='outer_rectangle'>
                <rect width='495' height='195' rx='8'/>
            </clipPath>
            <mask id='mask_out_ring_behind_fire'>
                <rect width='495' height='195' fill='white'/>
                <ellipse id='mask-ellipse' cx='247.5' cy='32' rx='13' ry='18' fill='black'/>
            </mask>
        </defs>
        <g clip-path='url(#outer_rectangle)'>
            <g style='isolation: isolate'>
                <rect stroke='#000000' stroke-opacity='0' fill='#2d353b' rx='8' x='0.5' y='0.5' width='494' height='194'/>
            </g>
            <g style='isolation: isolate'>
                <line x1='165' y1='28' x2='165' y2='170' vector-effect='non-scaling-stroke' stroke-width='1' stroke='#475258' stroke-linejoin='miter' stroke-linecap='square' stroke-miterlimit='3'/>
                <line x1='330' y1='28' x2='330' y2='170' vector-effect='non-scaling-stroke' stroke-width='1' stroke='#475258' stroke-linejoin='miter' stroke-linecap='square' stroke-miterlimit='3'/>
            </g>
            <g style='isolation: isolate'>
                <g transform='translate(82.5, 48)'>
                    <text x='0' y='32' text-anchor='middle' fill='#d3c6aa' font-family='"Segoe UI", Ubuntu, sans-serif' font-weight='700' font-size='28px' style='opacity: 0; animation: fadein 0.5s linear forwards 0.6s'>{total}</text>
                </g>
                <g transform='translate(82.5, 84)'>
                    <text x='0' y='32' text-anchor='middle' fill='#859289' font-family='"Segoe UI", Ubuntu, sans-serif' font-weight='400' font-size='14px' style='opacity: 0; animation: fadein 0.5s linear forwards 0.7s'>Total Contributions</text>
                </g>
                <g transform='translate(82.5, 114)'>
                    <text x='0' y='32' text-anchor='middle' fill='#859289' font-family='"Segoe UI", Ubuntu, sans-serif' font-weight='400' font-size='12px' style='opacity: 0; animation: fadein 0.5s linear forwards 0.8s'>{total_range}</text>
                </g>
            </g>
            <g style='isolation: isolate'>
                <g transform='translate(247.5, 108)'>
                    <text x='0' y='32' text-anchor='middle' fill='#a7c080' font-family='"Segoe UI", Ubuntu, sans-serif' font-weight='700' font-size='14px' style='opacity: 0; animation: fadein 0.5s linear forwards 0.9s'>Current Streak</text>
                </g>
                <g transform='translate(247.5, 145)'>
                    <text x='0' y='21' text-anchor='middle' fill='#859289' font-family='"Segoe UI", Ubuntu, sans-serif' font-weight='400' font-size='12px' style='opacity: 0; animation: fadein 0.5s linear forwards 0.9s'>{cur_range}</text>
                </g>
                <g mask='url(#mask_out_ring_behind_fire)'>
                    <circle cx='247.5' cy='71' r='40' fill='none' stroke='#a7c080' stroke-width='5' style='opacity: 0; animation: fadein 0.5s linear forwards 0.4s'></circle>
                </g>
                <g transform='translate(247.5, 19.5)' stroke-opacity='0' style='opacity: 0; animation: fadein 0.5s linear forwards 0.6s'>
                    <path d='M -12 -0.5 L 15 -0.5 L 15 23.5 L -12 23.5 L -12 -0.5 Z' fill='none'/>
                    <path d='M 1.5 0.67 C 1.5 0.67 2.24 3.32 2.24 5.47 C 2.24 7.53 0.89 9.2 -1.17 9.2 C -3.23 9.2 -4.79 7.53 -4.79 5.47 L -4.76 5.11 C -6.78 7.51 -8 10.62 -8 13.99 C -8 18.41 -4.42 22 0 22 C 4.42 22 8 18.41 8 13.99 C 8 8.6 5.41 3.79 1.5 0.67 Z M -0.29 19 C -2.07 19 -3.51 17.6 -3.51 15.86 C -3.51 14.24 -2.46 13.1 -0.7 12.74 C 1.07 12.38 2.9 11.53 3.92 10.16 C 4.31 11.45 4.51 12.81 4.51 14.2 C 4.51 16.85 2.36 19 -0.29 19 Z' fill='#e67e80' stroke-opacity='0'/>
                </g>
                <g transform='translate(247.5, 48)'>
                    <text x='0' y='32' text-anchor='middle' fill='#d3c6aa' font-family='"Segoe UI", Ubuntu, sans-serif' font-weight='700' font-size='28px' style='animation: currstreak 0.6s linear forwards'>{current}</text>
                </g>
            </g>
            <g style='isolation: isolate'>
                <g transform='translate(412.5, 48)'>
                    <text x='0' y='32' text-anchor='middle' fill='#d3c6aa' font-family='"Segoe UI", Ubuntu, sans-serif' font-weight='700' font-size='28px' style='opacity: 0; animation: fadein 0.5s linear forwards 1.2s'>{longest}</text>
                </g>
                <g transform='translate(412.5, 84)'>
                    <text x='0' y='32' text-anchor='middle' fill='#859289' font-family='"Segoe UI", Ubuntu, sans-serif' font-weight='400' font-size='14px' style='opacity: 0; animation: fadein 0.5s linear forwards 1.3s'>Longest Streak</text>
                </g>
                <g transform='translate(412.5, 114)'>
                    <text x='0' y='32' text-anchor='middle' fill='#859289' font-family='"Segoe UI", Ubuntu, sans-serif' font-weight='400' font-size='12px' style='opacity: 0; animation: fadein 0.5s linear forwards 1.4s'>{long_range}</text>
                </g>
            </g>
        </g>
    </svg>
"""


def main():
    if not TOKEN:
        print("missing GITHUB_TOKEN/GH_TOKEN", file=sys.stderr)
        return 1
    try:
        counts = day_counts(created_at())
        if not counts:
            raise RuntimeError("no contribution days returned")
        total, current, cur_range, longest, long_range = compute(counts)
        sys.stdout.write(TEMPLATE.format(
            total=total,
            total_range="Present" if not counts else f"{fmt(min(counts))} - Present",
            current=current,
            cur_range=cur_range,
            longest=longest,
            long_range=long_range,
        ))
    except Exception as exc:  # noqa: BLE001 - fail closed, keep old snapshot
        print(f"streak card generation failed: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
