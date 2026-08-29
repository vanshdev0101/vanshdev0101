#!/usr/bin/env python3
"""Render a self-hosted commit-activity area chart as SVG.

Pulls the last 30 days of the GitHub contribution calendar via the GraphQL
API and draws it. No third-party service, no dependencies. Writes SVG to
stdout; exits non-zero (printing nothing) on any failure so the workflow's
validate step keeps the previous snapshot.

Env: GH_USERNAME (default: vanshdev0101), GITHUB_TOKEN (or GH_TOKEN).
"""
import json
import os
import sys
import urllib.request
from datetime import date

USER = os.environ.get("GH_USERNAME", "vanshdev0101")
TOKEN = os.environ.get("GITHUB_TOKEN") or os.environ.get("GH_TOKEN")
DAYS = 30

# Everforest, matched to the existing card
BG = "#2D353B"
LINE = "#A7C080"
AREA = "#A7C080"
POINT = "#E67E80"
TEXT = "#D3C6AA"
MUTED = "#859289"
TITLE = "#A7C080"
GRID = "#475258"

W, H = 1200, 420
PAD_L, PAD_R, PAD_T, PAD_B = 64, 40, 80, 56
PLOT_W = W - PAD_L - PAD_R
PLOT_H = H - PAD_T - PAD_B
BASE_Y = PAD_T + PLOT_H


def fetch_days():
    query = """
    query($login:String!){
      user(login:$login){
        contributionsCollection{
          contributionCalendar{
            weeks{ contributionDays{ date contributionCount } }
          }
        }
      }
    }"""
    body = json.dumps({"query": query, "variables": {"login": USER}}).encode()
    req = urllib.request.Request(
        "https://api.github.com/graphql",
        data=body,
        headers={
            "Authorization": f"bearer {TOKEN}",
            "Content-Type": "application/json",
            "User-Agent": f"{USER}-profile-activity-graph",
        },
    )
    with urllib.request.urlopen(req, timeout=30) as resp:
        payload = json.load(resp)
    if payload.get("errors"):
        raise RuntimeError(payload["errors"])
    weeks = payload["data"]["user"]["contributionsCollection"][
        "contributionCalendar"
    ]["weeks"]
    days = [d for wk in weeks for d in wk["contributionDays"]]
    days.sort(key=lambda d: d["date"])
    return days[-DAYS:]


def x(i, n):
    return PAD_L + (PLOT_W * i / (n - 1) if n > 1 else 0)


def y(count, cap):
    return BASE_Y - (PLOT_H * count / cap if cap else 0)


def render(days):
    counts = [d["contributionCount"] for d in days]
    total = sum(counts)
    cap = max(counts + [1])
    n = len(days)

    pts = [(x(i, n), y(c, cap)) for i, c in enumerate(counts)]
    line = " ".join(f"{px:.1f},{py:.1f}" for px, py in pts)
    area = f"{PAD_L:.1f},{BASE_Y:.1f} " + line + f" {PAD_L + PLOT_W:.1f},{BASE_Y:.1f}"

    # y gridlines / labels at 0, 50%, 100% of cap
    grid = []
    for frac in (0.0, 0.5, 1.0):
        gy = BASE_Y - PLOT_H * frac
        val = round(cap * frac)
        grid.append(
            f'<line x1="{PAD_L}" y1="{gy:.1f}" x2="{PAD_L + PLOT_W}" y2="{gy:.1f}" '
            f'stroke="{GRID}" stroke-width="1" stroke-dasharray="4 4"/>'
            f'<text x="{PAD_L - 12}" y="{gy + 5:.1f}" fill="{MUTED}" '
            f'font-size="15" text-anchor="end">{val}</text>'
        )

    # ~5 date labels along x
    xlabels = []
    step = max(1, (n - 1) // 4)
    for i in range(0, n, step):
        d = date.fromisoformat(days[i]["date"])
        xlabels.append(
            f'<text x="{x(i, n):.1f}" y="{BASE_Y + 28:.1f}" fill="{MUTED}" '
            f'font-size="15" text-anchor="middle">{d.strftime("%b %d")}</text>'
        )

    dots = "".join(
        f'<circle cx="{px:.1f}" cy="{py:.1f}" r="3.5" fill="{POINT}"/>'
        for px, py in pts
    )

    font = "600 18px 'Segoe UI', Ubuntu, 'JetBrains Mono', Sans-Serif"
    return f"""<svg width="{W}" height="{H}" viewBox="0 0 {W} {H}" fill="none" xmlns="http://www.w3.org/2000/svg" font-family="{font}">
  <!-- self-hosted activity graph. Contributions over the last {DAYS} days. -->
  <rect x="0" y="0" width="100%" height="100%" fill="{BG}"/>
  <linearGradient id="fill" x1="0" y1="0" x2="0" y2="1">
    <stop offset="0" stop-color="{AREA}" stop-opacity="0.45"/>
    <stop offset="1" stop-color="{AREA}" stop-opacity="0.02"/>
  </linearGradient>
  <text x="{PAD_L}" y="42" fill="{TITLE}" font-size="22" font-weight="700">commit activity</text>
  <text x="{W - PAD_R}" y="42" fill="{MUTED}" font-size="16" text-anchor="end">last {DAYS} days &#183; {total} contributions</text>
  {''.join(grid)}
  <polygon points="{area}" fill="url(#fill)"/>
  <polyline points="{line}" fill="none" stroke="{LINE}" stroke-width="2.5" stroke-linejoin="round" stroke-linecap="round"/>
  {dots}
  {''.join(xlabels)}
</svg>
"""


def main():
    if not TOKEN:
        print("missing GITHUB_TOKEN/GH_TOKEN", file=sys.stderr)
        return 1
    try:
        days = fetch_days()
        if not days:
            raise RuntimeError("no contribution days returned")
        sys.stdout.write(render(days))
    except Exception as exc:  # noqa: BLE001 - fail closed, keep old snapshot
        print(f"activity graph generation failed: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
