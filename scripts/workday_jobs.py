"""Read the job list of a Workday career site (myworkdayjobs.com) and write one CSV.

Workday has no documented public API. This script calls the JSON endpoint that the
career site itself uses:
    POST https://<tenant>.<wdN>.myworkdayjobs.com/wday/cxs/<tenant>/<site>/jobs
It checks robots.txt first and stops if the path is disallowed. The endpoint can change
without notice.

Examples:
    python scripts/workday_jobs.py https://nvidia.wd5.myworkdayjobs.com/NVIDIAExternalCareerSite --pages 3
    python scripts/workday_jobs.py https://nvidia.wd5.myworkdayjobs.com/NVIDIAExternalCareerSite \
        --pages 17 --facet jobFamilyGroup=0c40f6bd1d8f10ae43ffcac5bbec7e90
"""
import argparse
import csv
import os
import re
import sys
import time
from datetime import date, timedelta
from urllib.parse import urlparse
from urllib.robotparser import RobotFileParser

import requests

UA = os.environ.get(
    "JOBS_USER_AGENT",
    "ats-job-boards-python/1.0 (+https://github.com/donmangudata-ops/ats-job-boards-python)",
)
PAGE = 20      # Workday answers HTTP 400 for a larger limit
CAP = 2000     # offsets from 2000 on repeat the first page


def split_url(career_url):
    u = urlparse(career_url)
    parts = [p for p in u.path.split("/") if p and not re.fullmatch(r"[a-z]{2}-[A-Z]{2}", p)]
    if not u.netloc or not parts:
        sys.exit("Expected a link like https://<tenant>.wd5.myworkdayjobs.com/<SiteName>")
    return u.netloc, u.netloc.split(".")[0], parts[0]


def allowed(host, api_url, session):
    # Workday answers HTTP 406 to the JSON Accept header, so ask for robots.txt with its own header
    r = session.get(f"https://{host}/robots.txt", headers={"Accept": "*/*"}, timeout=20)
    if r.status_code == 404:
        return True   # no robots.txt, so no rules
    if r.status_code != 200:
        return False  # anything else: do not proceed
    rp = RobotFileParser()
    rp.parse(r.text.splitlines())
    return rp.can_fetch("*", api_url)


def parse_posted(text, today):
    t = (text or "").lower()
    if "today" in t:
        return today, "exact"
    if "yesterday" in t:
        return today - timedelta(days=1), "exact"
    m = re.search(r"(\d+)(\+)?\s*days?\s+ago", t)
    if m:
        d = today - timedelta(days=int(m.group(1)))
        return d, ("on_or_before" if m.group(2) else "exact")
    return None, "unknown"


def read_site(career_url, max_pages=5, delay=1.0, facets=None):
    host, tenant, site = split_url(career_url)
    api = f"https://{host}/wday/cxs/{tenant}/{site}/jobs"
    s = requests.Session()
    s.headers.update({"User-Agent": UA, "Accept": "application/json"})
    try:
        ok = allowed(host, api, s)
    except requests.RequestException as e:
        sys.exit(f"Could not read robots.txt on {host} ({e.__class__.__name__}), not fetching")
    if not ok:
        sys.exit("robots.txt disallows or could not be read, not fetching " + api)
    today, rows, seen, total, offset = date.today(), [], set(), None, 0
    while offset // PAGE < max_pages:
        body = {"appliedFacets": facets or {}, "limit": PAGE, "offset": offset, "searchText": ""}
        for wait in (5, 15, None):
            r = s.post(api, json=body, timeout=30)
            if r.status_code not in (429, 500, 502, 503) or wait is None:
                break
            time.sleep(wait)
        if r.status_code in (400, 404, 422):
            sys.exit(f"Workday answered HTTP {r.status_code} for {api}. Check the tenant and site name in the link.")
        r.raise_for_status()
        data = r.json()
        if total is None:  # only the first page carries the total
            total = data["total"]
            sums = [sum(v.get("count", 0) for v in f["values"])
                    for f in data.get("facets", []) if f["values"] and "count" in f["values"][0]]
            print(f"{tenant}: total={total}, largest facet sum={max(sums, default=0)}")
        fresh = [j for j in data["jobPostings"] if j["externalPath"] not in seen]
        if not fresh:
            break  # empty page, or the list wrapped around
        for j in fresh:
            seen.add(j["externalPath"])
            d, quality = parse_posted(j.get("postedOn"), today)
            rows.append({"title": j["title"], "location": j.get("locationsText", ""),
                         "posted_text": j.get("postedOn", ""), "posted_date": d,
                         "date_quality": quality,
                         "job_id": (j.get("bulletFields") or [""])[0],
                         "url": f"https://{host}/{site}{j['externalPath']}"})
        offset += PAGE
        if offset >= min(total, CAP):
            break
        time.sleep(delay)
    return rows


def main():
    ap = argparse.ArgumentParser(description="Workday career site job list to CSV.")
    ap.add_argument("url", help="career site link, e.g. https://nvidia.wd5.myworkdayjobs.com/NVIDIAExternalCareerSite")
    ap.add_argument("--pages", type=int, default=5, help="pages of 20 jobs to read (default 5)")
    ap.add_argument("--facet", action="append", default=[], metavar="NAME=ID",
                    help="filter by a facet from the first response, e.g. jobFamilyGroup=<id> (repeatable)")
    ap.add_argument("--out", default="workday_jobs.csv", help="output CSV path")
    ap.add_argument("--delay", type=float, default=1.0, help="seconds between pages")
    args = ap.parse_args()

    facets = {}
    for item in args.facet:
        name, _, value = item.partition("=")
        if not value:
            sys.exit(f"--facet needs NAME=ID, got {item!r}")
        facets.setdefault(name, []).append(value)

    rows = read_site(args.url, args.pages, args.delay, facets or None)
    if not rows:
        print("0 rows, no file written")
        return
    with open(args.out, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=rows[0].keys())
        w.writeheader()
        w.writerows(rows)
    print(len(rows), "rows written ->", args.out)


if __name__ == "__main__":
    main()
