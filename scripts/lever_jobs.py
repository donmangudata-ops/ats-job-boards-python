"""Read open jobs from public Lever job boards, merge repeats and rank them.

Uses Lever's public postings API (GET, no key):
https://github.com/lever/postings-api

Lever often lists one role once per hiring city. This script merges those copies
(same company, title and team) and can rank rows against words you care about.

Examples:
    python scripts/lever_jobs.py spotify outreach nium
    python scripts/lever_jobs.py spotify outreach --want "research scientist,personalization"
"""
import argparse
import csv
import os
import re
import time
from collections import defaultdict
from datetime import datetime, timezone

import requests

API = "https://api.lever.co/v0/postings/{site}"
session = requests.Session()
USER_AGENT = os.environ.get(
    "JOBS_USER_AGENT",
    "ats-job-boards-python/1.0 (+https://github.com/donmangudata-ops/ats-job-boards-python)",
)
session.headers["User-Agent"] = USER_AGENT


def fetch_board(site, retries=3):
    """Return (postings, status). status is 'ok', 'not_found' or 'error: ...'."""
    status = "error"
    for attempt in range(retries):
        try:
            r = session.get(API.format(site=site), params={"mode": "json"}, timeout=60)
        except requests.RequestException as e:
            status = f"error: {e.__class__.__name__}"
        else:
            if r.status_code == 404:
                return [], "not_found"
            if r.status_code == 200:
                data = r.json()
                return (data if isinstance(data, list) else []), "ok"
            status = f"error: HTTP {r.status_code}"
            if r.status_code == 429 and r.headers.get("Retry-After", "").isdigit():
                time.sleep(int(r.headers["Retry-After"]))
        time.sleep(2 ** attempt)
    return [], status


def norm(text):
    return re.sub(r"\s+", " ", text or "").strip().lower()


def dedupe(postings):
    """Merge postings of one company that share a title and a team.
    Lever lists a role once per hiring location, each with its own id."""
    groups = defaultdict(list)
    for p in postings:
        c = p.get("categories") or {}
        groups[(p["site"], norm(p["text"]), norm(c.get("team")))].append(p)
    merged = []
    for group in groups.values():
        group.sort(key=lambda p: p["createdAt"], reverse=True)  # newest first
        best = dict(group[0])
        places = []
        for p in group:
            c = p.get("categories") or {}
            for place in c.get("allLocations") or [c.get("location")]:
                if place and place not in places:
                    places.append(place)
        best["places"] = places
        # pay: widen the range over copies that share the newest copy's currency and interval
        base = group[0].get("salaryRange")
        same = [p["salaryRange"] for p in group if p.get("salaryRange")
                and p["salaryRange"].get("currency") == (base or {}).get("currency")
                and p["salaryRange"].get("interval") == (base or {}).get("interval")]
        best["pay"] = None if not base else {
            "min": min(r["min"] for r in same), "max": max(r["max"] for r in same),
            "currency": base.get("currency"), "interval": base.get("interval")}
        best["copies"] = len(group)
        best["urls"] = [p["hostedUrl"] for p in group]
        merged.append(best)
    return merged


def score(p, wanted, now_ms):
    """Heuristic. The weights are my own choice, not anything Lever defines."""
    c = p.get("categories") or {}
    title, team = p["text"].lower(), (c.get("team") or "").lower()
    body = (p.get("descriptionPlain") or "").lower()
    pts = 0
    for w in wanted:
        pat = r"\b" + re.escape(w) + r"\b"
        if re.search(pat, title):
            pts += 3
        if re.search(pat, team):
            pts += 2
        if re.search(pat, body):
            pts += 1
    if pts == 0 and wanted:
        return 0  # no match, so no bonus points either
    if p.get("workplaceType") == "remote":
        pts += 1
    if p.get("salaryRange"):
        pts += 1
    if now_ms - p["createdAt"] <= 14 * 86400 * 1000:
        pts += 1
    return pts


def main():
    ap = argparse.ArgumentParser(description="Lever public boards to one merged, ranked CSV.")
    ap.add_argument("sites", nargs="+", help="Lever site names, e.g. spotify outreach")
    ap.add_argument("--want", default="", help="comma separated words to rank by, e.g. 'python,data'")
    ap.add_argument("--out", default="lever_jobs.csv", help="output CSV path")
    ap.add_argument("--delay", type=float, default=1.5, help="seconds between boards")
    args = ap.parse_args()

    wanted = [w.strip().lower() for w in args.want.split(",") if w.strip()]
    allp, report = [], []
    for site in args.sites:
        postings, status = fetch_board(site)
        for p in postings:
            p["site"] = site
        report.append((site, status, len(postings)))
        allp += postings
        time.sleep(args.delay)  # one board at a time, with a pause
    now_ms = int(datetime.now(timezone.utc).timestamp() * 1000)
    rows = dedupe(allp)
    for p in rows:
        p["score"] = score(p, wanted, now_ms)
    rows.sort(key=lambda p: (-p["score"], -p["createdAt"]))
    if rows:
        with open(args.out, "w", newline="", encoding="utf-8") as f:
            w = csv.writer(f)
            w.writerow(["rank", "score", "board", "title", "team", "workplace", "locations",
                        "copies", "salary_min", "salary_max", "currency", "interval", "posted", "url"])
            for i, p in enumerate(rows, 1):
                c, s = p.get("categories") or {}, p.get("pay") or {}
                posted = datetime.fromtimestamp(p["createdAt"] / 1000, timezone.utc).date()
                w.writerow([i, p["score"], p["site"], p["text"].strip(), c.get("team") or "",
                            p.get("workplaceType") or "", "; ".join(p["places"]), p["copies"],
                            s.get("min", ""), s.get("max", ""), s.get("currency", ""), s.get("interval", ""),
                            posted, p["urls"][0]])
    for site, status, n in report:
        print(f"{site}: {status}, {n} postings")
    print(f"postings: {len(allp)}, after dedupe: {len(rows)}, merged away: {len(allp) - len(rows)}")
    for p in rows[:5]:
        print(p["score"], p["site"], "|", p["text"].strip(), "|", "; ".join(p["places"]))


if __name__ == "__main__":
    main()
