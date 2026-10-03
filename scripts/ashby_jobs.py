"""Read open jobs and salary ranges from public Ashby job boards and write one CSV.

Uses Ashby's public job posting API (GET, no key):
https://developers.ashbyhq.com/docs/public-job-posting-api

Examples:
    python scripts/ashby_jobs.py ramp ashby linear
    python scripts/ashby_jobs.py ramp ashby replit --title engineer --salary-only
"""
import argparse
import csv
import os
import time

import requests

API = "https://api.ashbyhq.com/posting-api/job-board/{board}"
USER_AGENT = os.environ.get(
    "JOBS_USER_AGENT",
    "ats-job-boards-python/1.0 (+https://github.com/donmangudata-ops/ats-job-boards-python)",
)
session = requests.Session()
session.headers["User-Agent"] = USER_AGENT


def board_jobs(board, retries=3):
    """Return (jobs, status). status is 'ok', 'not_found' or 'error: ...'."""
    status = "error"
    for attempt in range(retries):
        try:
            r = session.get(API.format(board=board), params={"includeCompensation": "true"}, timeout=60)
        except requests.RequestException as e:
            status = f"error: {e.__class__.__name__}"
        else:
            if r.status_code == 404:
                return [], "not_found"
            if r.status_code == 200:
                return r.json().get("jobs", []), "ok"
            status = f"error: HTTP {r.status_code}"
        time.sleep(2 ** attempt)
    return [], status


def salary(job):
    """First Salary component of the pay summary, or None. Equity and bonus are skipped."""
    for c in (job.get("compensation") or {}).get("summaryComponents", []):
        if c.get("compensationType") == "Salary" and c.get("minValue") is not None:
            return c
    return None


def flatten(board, job):
    pay = salary(job) or {}
    places = [job.get("location") or ""]
    places += [s.get("location") or "" for s in job.get("secondaryLocations", [])]
    return {
        "board": board,
        "job_id": job["id"],
        "title": job["title"].strip(),  # some titles start with a space
        "department": job.get("department") or "",
        "team": job.get("team") or "",
        "employment_type": job.get("employmentType") or "",
        "workplace_type": job.get("workplaceType") or "",
        "locations": "; ".join(p for p in places if p),
        "published_at": job.get("publishedAt") or "",
        "salary_min": pay.get("minValue", ""),
        "salary_max": pay.get("maxValue", ""),
        "salary_currency": pay.get("currencyCode") or "",
        "salary_interval": pay.get("interval") or "",
        "url": job["jobUrl"],
    }


def main():
    ap = argparse.ArgumentParser(description="Ashby public boards to CSV.")
    ap.add_argument("boards", nargs="*", default=["ashby"], help="board names, e.g. ramp linear")
    ap.add_argument("--title", action="append", default=[],
                    help="keep jobs whose title contains this text (substring, repeatable)")
    ap.add_argument("--salary-only", action="store_true", help="drop jobs without a salary")
    ap.add_argument("--out", default="ashby_jobs.csv", help="output CSV path")
    ap.add_argument("--delay", type=float, default=1.0, help="seconds between boards")
    args = ap.parse_args()

    words = [w.lower() for w in args.title]
    rows, report = [], []
    for board in args.boards:
        jobs, status = board_jobs(board)
        report.append((board, status, len(jobs), sum(1 for j in jobs if salary(j))))
        for j in jobs:
            if words and not any(w in j["title"].lower() for w in words):
                continue
            if args.salary_only and not salary(j):
                continue
            rows.append(flatten(board, j))
        time.sleep(args.delay)  # one board at a time
    if rows:
        with open(args.out, "w", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(f, fieldnames=list(rows[0]))
            w.writeheader()
            w.writerows(rows)
    for board, status, n, with_pay in report:
        print(f"{board}: {status}, {n} jobs, {with_pay} with a salary")
    print("rows written:", len(rows), "->", args.out if rows else "(no file)")


if __name__ == "__main__":
    main()
