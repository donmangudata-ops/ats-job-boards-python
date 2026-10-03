"""Read open jobs from public Greenhouse job boards and write one CSV.

Uses Greenhouse's public Job Board API (GET, no key):
https://developers.greenhouse.io/job-board.html

Examples:
    python scripts/greenhouse_jobs.py dropbox figma stripe
    python scripts/greenhouse_jobs.py dropbox figma --title engineer --pay
"""
import argparse
import csv
import os
import time

import requests

API = "https://boards-api.greenhouse.io/v1/boards/{token}"
USER_AGENT = os.environ.get(
    "JOBS_USER_AGENT",
    "ats-job-boards-python/1.0 (+https://github.com/donmangudata-ops/ats-job-boards-python)",
)
session = requests.Session()
session.headers["User-Agent"] = USER_AGENT


def board_jobs(token, pay=False, retries=3):
    """Return (jobs, status). status is 'ok', 'not_found' or 'error: ...'."""
    url = API.format(token=token) + "/jobs"
    params = {"content": "true"}
    if pay:
        params["pay_transparency"] = "true"  # pay ranges come back in the same list call
    status = "error"
    for attempt in range(retries):
        try:
            r = session.get(url, params=params, timeout=30)
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


def pay_ranges(job):
    """Read the ranges already in the list response. Often an empty list."""
    out = []
    for p in job.get("pay_input_ranges") or []:
        out.append({
            "min": p["min_cents"] / 100 if p.get("min_cents") is not None else None,
            "max": p["max_cents"] / 100 if p.get("max_cents") is not None else None,
            "currency": p.get("currency_type"),
            "label": p.get("title"),
        })
    return out


def flatten(token, job):
    return {
        "board": token,
        "job_id": job["id"],
        "title": job["title"],
        "location": (job.get("location") or {}).get("name", ""),
        "departments": " > ".join(d["name"] for d in job.get("departments", [])),
        "offices": "; ".join(o["name"] for o in job.get("offices", [])),
        "first_published": job.get("first_published", ""),
        "updated_at": job.get("updated_at", ""),
        "url": job["absolute_url"],
    }


def pay_text(job):
    parts = []
    for r in pay_ranges(job):
        if r["min"] is not None and r["max"] is not None:
            label = (r["label"] or "range").rstrip(":")
            parts.append(f'{label}: {r["min"]:.0f}-{r["max"]:.0f} {r["currency"]}')
    return "; ".join(parts)


def main():
    ap = argparse.ArgumentParser(description="Greenhouse public boards to CSV.")
    ap.add_argument("boards", nargs="*", default=["dropbox"], help="board tokens, e.g. dropbox figma")
    ap.add_argument("--title", action="append", default=[],
                    help="keep jobs whose title contains this text (substring, repeatable)")
    ap.add_argument("--pay", action="store_true", help="add a pay column from pay_transparency")
    ap.add_argument("--out", default="greenhouse_jobs.csv", help="output CSV path")
    ap.add_argument("--delay", type=float, default=1.0, help="seconds between boards")
    args = ap.parse_args()

    words = [w.lower() for w in args.title]
    rows, report = [], []
    for t in args.boards:
        jobs, status = board_jobs(t, args.pay)
        report.append((t, status, len(jobs)))
        for j in jobs:
            if words and not any(w in j["title"].lower() for w in words):
                continue
            row = flatten(t, j)
            if args.pay:
                row["pay"] = pay_text(j)
            rows.append(row)
        time.sleep(args.delay)  # one board at a time, politely
    if rows:
        with open(args.out, "w", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(f, fieldnames=list(rows[0]))
            w.writeheader()
            w.writerows(rows)
    for t, status, n in report:
        print(f"{t}: {status}, {n} jobs on the board")
    print("rows written:", len(rows), "->", args.out if rows else "(no file)")


if __name__ == "__main__":
    main()
