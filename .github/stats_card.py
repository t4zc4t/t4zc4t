"""Builds the activity card (dark + light) from the GitHub GraphQL API."""
import json, os, sys, urllib.request
from datetime import date, datetime, timedelta, timezone

LOGIN = os.environ.get("PROFILE_USER", "t4zc4t")
OUT = sys.argv[1] if len(sys.argv) > 1 else "dist"
# notebooks and generated html inflate byte counts, so they stay out of the language bar
SKIP_LANGS = {"Jupyter Notebook", "HTML"}

THEMES = {
    "dark": dict(bg="#0f0c0c", line="#2a1f1f", ink="#ede6da", muted="#9c8b74", accent="#d7263d", track="#1d1616",
                 langs=["#d7263d", "#c8a97e", "#6f9fa0", "#e08a6a", "#8e7f9e", "#7d7064"]),
    "light": dict(bg="#fbf7ef", line="#e0cba6", ink="#2a211b", muted="#7a6a55", accent="#a51c2a", track="#efe6d6",
                  langs=["#a51c2a", "#a8824d", "#3f7273", "#c0603d", "#6b5a80", "#8b7d6b"]),
}


def gql(query, variables):
    req = urllib.request.Request(
        "https://api.github.com/graphql",
        data=json.dumps({"query": query, "variables": variables}).encode(),
        headers={"Authorization": f"bearer {os.environ['GITHUB_TOKEN']}", "User-Agent": "profile-card"},
    )
    with urllib.request.urlopen(req, timeout=30) as r:
        body = json.load(r)
    if "errors" in body:
        raise SystemExit(body["errors"])
    return body["data"]


MAIN = """
query($login: String!) {
  user(login: $login) {
    createdAt
    pullRequests { totalCount }
    repositories(first: 100, ownerAffiliations: OWNER, isFork: false, privacy: PUBLIC) {
      totalCount
      nodes { stargazerCount languages(first: 10, orderBy: {field: SIZE, direction: DESC}) { edges { size node { name } } } }
    }
  }
}"""

YEAR = """
query($login: String!, $from: DateTime!, $to: DateTime!) {
  user(login: $login) {
    contributionsCollection(from: $from, to: $to) {
      totalCommitContributions
      contributionCalendar { weeks { contributionDays { date contributionCount } } }
    }
  }
}"""


def collect():
    u = gql(MAIN, {"login": LOGIN})["user"]
    today = datetime.now(timezone.utc).date()
    start = datetime.fromisoformat(u["createdAt"].replace("Z", "+00:00")).date()

    days, commits_year = {}, 0
    y = start.year
    while y <= today.year:
        frm = max(date(y, 1, 1), start)
        to = min(date(y, 12, 31), today)
        c = gql(YEAR, {"login": LOGIN, "from": f"{frm}T00:00:00Z", "to": f"{to}T23:59:59Z"})["user"]["contributionsCollection"]
        if y == today.year:
            commits_year = c["totalCommitContributions"]
        for w in c["contributionCalendar"]["weeks"]:
            for d in w["contributionDays"]:
                days[d["date"]] = d["contributionCount"]
        y += 1

    # streaks: today with no activity yet doesn't break the current one
    run = longest = 0
    d = start
    while d <= today:
        run = run + 1 if days.get(str(d), 0) else 0
        longest = max(longest, run)
        d += timedelta(days=1)
    cur, d = 0, today
    if not days.get(str(d), 0):
        d -= timedelta(days=1)
    while days.get(str(d), 0):
        cur += 1
        d -= timedelta(days=1)

    year_total = sum(v for k, v in days.items() if k >= str(today - timedelta(days=364)))

    sizes = {}
    stars = 0
    for r in u["repositories"]["nodes"]:
        stars += r["stargazerCount"]
        for e in r["languages"]["edges"]:
            n = e["node"]["name"]
            if n not in SKIP_LANGS:
                sizes[n] = sizes.get(n, 0) + e["size"]

    return dict(
        year=today.year, commits=commits_year, contributions=year_total, prs=u["pullRequests"]["totalCount"],
        repos=u["repositories"]["totalCount"], stars=stars, current=cur, longest=longest,
        langs=sorted(sizes.items(), key=lambda x: -x[1]), updated=today.strftime("%d %b %Y"),
    )


def esc(s):
    return str(s).replace("&", "&amp;").replace("<", "&lt;")


def render(s, t):
    serif = "Georgia, 'Times New Roman', 'Noto Serif', serif"
    metrics = [
        (f"{s['contributions']:,}", "CONTRIBUTIONS"),
        (f"{s['commits']:,}", f"COMMITS {s['year']}"),
        (f"{s['repos']}", "REPOSITORIES"),
        (f"{s['prs']}", "PULL REQUESTS"),
    ]
    out = []
    for i, (v, label) in enumerate(metrics):
        x = 40 + i * 150
        out.append(f'<g class="m" style="animation-delay:{i * .12:.2f}s"><text x="{x}" y="86" class="v">{v}</text>'
                   f'<text x="{x}" y="110" class="l">{label}</text></g>')

    # streak block
    out.append(f'<line x1="652" y1="40" x2="652" y2="118" stroke="{t["line"]}"/>')
    out.append(f'<g class="m" style="animation-delay:.5s"><text x="680" y="86" class="v a">{s["current"]}</text>'
               f'<text x="680" y="110" class="l">DAY STREAK</text></g>')
    out.append(f'<g class="m" style="animation-delay:.62s"><text x="790" y="86" class="v">{s["longest"]}</text>'
               f'<text x="790" y="110" class="l">LONGEST</text></g>')

    # language bar
    total = sum(v for _, v in s["langs"]) or 1
    top = s["langs"][:5]
    rest = total - sum(v for _, v in top)
    parts = top + ([("Other", rest)] if rest > 0 else [])
    x, bar, legend, lx = 40, [], [], 40
    for i, (name, v) in enumerate(parts):
        w = 820 * v / total
        col = t["langs"][i % len(t["langs"])]
        bar.append(f'<rect x="{x:.1f}" y="146" width="{max(w, 1):.1f}" height="8" fill="{col}"/>')
        x += w
        pct = f"{100 * v / total:.1f}%"
        legend.append(f'<circle cx="{lx + 4}" cy="180" r="4" fill="{col}"/>'
                      f'<text x="{lx + 14}" y="184" class="g">{esc(name)} <tspan class="p">{pct}</tspan></text>')
        lx += 14 + 8.2 * len(name) + 8 * len(pct) + 22

    return f'''<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 900 214" width="900" height="214" role="img" aria-label="GitHub activity for {LOGIN}">
<title>Activity</title>
<defs><clipPath id="bar"><rect x="40" y="146" width="820" height="8" rx="4"/></clipPath></defs>
<style>
  .v {{ font: 600 34px {serif}; fill: {t["ink"]}; }}
  .a {{ fill: {t["accent"]}; }}
  .l {{ font: 600 10.5px 'Segoe UI', Inter, Arial, sans-serif; letter-spacing: 1.6px; fill: {t["muted"]}; }}
  .g {{ font: 13px {serif}; fill: {t["ink"]}; }}
  .p {{ fill: {t["muted"]}; }}
  .u {{ font: italic 11px {serif}; fill: {t["muted"]}; }}
  .m {{ animation: up .6s cubic-bezier(.2,.8,.2,1) both; }}
  .grow {{ transform-origin: 40px 0; animation: grow 1.2s cubic-bezier(.6,0,.2,1) .4s both; }}
  @keyframes up {{ from {{ opacity: 0; transform: translateY(8px); }} }}
  @keyframes grow {{ from {{ transform: scaleX(0); }} }}
  @media (prefers-reduced-motion: reduce) {{ .m, .grow {{ animation: none; }} }}
</style>
<rect x=".5" y=".5" width="899" height="213" rx="12" fill="{t["bg"]}" stroke="{t["line"]}"/>
<rect x="0" y="24" width="4" height="40" fill="{t["accent"]}"/>
<text x="860" y="34" text-anchor="end" class="u">past 12 months · updated {s["updated"]}</text>
{"".join(out)}
<rect x="40" y="146" width="820" height="8" rx="4" fill="{t["track"]}"/>
<g clip-path="url(#bar)"><g class="grow">{"".join(bar)}</g></g>
{"".join(legend)}
</svg>
'''


if __name__ == "__main__":
    if os.environ.get("CARD_SAMPLE"):
        stats = json.load(open(os.environ["CARD_SAMPLE"]))
    else:
        stats = collect()
    os.makedirs(OUT, exist_ok=True)
    for name, theme in THEMES.items():
        with open(f"{OUT}/activity-{name}.svg", "w") as f:
            f.write(render(stats, theme))
    print(json.dumps({k: v for k, v in stats.items() if k != "langs"}))
