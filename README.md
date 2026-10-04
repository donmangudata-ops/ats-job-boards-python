# ats-job-boards-python

Four small Python scripts that read open jobs from the public job board endpoints of **Greenhouse**, **Lever**, **Ashby** and **Workday**. Give each script a few company names, get one CSV back. No API key, no account, one dependency (`requests`).

| Script | Reads | Good for |
|---|---|---|
| [`scripts/greenhouse_jobs.py`](scripts/greenhouse_jobs.py) | Greenhouse Job Board API | many boards to one CSV, departments, offices, pay ranges, title filter |
| [`scripts/lever_jobs.py`](scripts/lever_jobs.py) | Lever postings API | merges the copies Lever creates for each hiring city, optional ranking by your words |
| [`scripts/ashby_jobs.py`](scripts/ashby_jobs.py) | Ashby job posting API | salary ranges, workplace type, title filter |
| [`scripts/workday_jobs.py`](scripts/workday_jobs.py) | Workday career site JSON | paging past the 2,000 job ceiling, "Posted 3 Days Ago" turned into a date |

Each script is one file that you can copy on its own.

## Quick start

Tested on Python 3.11.

```bash
git clone https://github.com/donmangudata-ops/ats-job-boards-python.git
cd ats-job-boards-python
pip install -r requirements.txt

python scripts/greenhouse_jobs.py dropbox figma stripe --title engineer --pay
python scripts/ashby_jobs.py ramp ashby replit --title engineer --salary-only
python scripts/lever_jobs.py spotify outreach nium --want "research scientist,personalization"
python scripts/workday_jobs.py https://nvidia.wd5.myworkdayjobs.com/NVIDIAExternalCareerSite --pages 3
```

Each command prints one status line per board and writes a CSV (`greenhouse_jobs.csv`, `ashby_jobs.csv`, `lever_jobs.csv`, `workday_jobs.csv`). Use `--out path.csv` to choose another file and `--help` for all options.

### Where to find the name a script needs

| ATS | Link on the company's careers page | What to pass |
|---|---|---|
| Greenhouse | `boards.greenhouse.io/dropbox` or `job-boards.greenhouse.io/dropbox` | `dropbox` |
| Lever | `jobs.lever.co/spotify` | `spotify` |
| Ashby | `jobs.ashbyhq.com/ramp` | `ramp` |
| Workday | `https://nvidia.wd5.myworkdayjobs.com/NVIDIAExternalCareerSite` | the whole link |

A name that does not exist is reported as `not_found`. A board that exists but has no open jobs is reported as `ok, 0 jobs`, so the two cases look different.

### Set your own User-Agent

The scripts send a User-Agent that names this repo. If you run them regularly, set one that tells the site owner how to reach you:

```bash
export JOBS_USER_AGENT="my-job-reader/1.0 (contact: you@yourdomain.example)"
```

## What the endpoints are

| ATS | Endpoint | Key needed | Documented by the vendor |
|---|---|---|---|
| Greenhouse | `GET https://boards-api.greenhouse.io/v1/boards/{token}/jobs?content=true` | No | Yes. The [docs](https://developers.greenhouse.io/job-board.html) say "Job Board data is publicly available, so authentication is not required for any GET endpoints." |
| Lever | `GET https://api.lever.co/v0/postings/{site}?mode=json` | No for reading | Yes, in the [postings-api README](https://github.com/lever/postings-api). A key is needed only to post applications. |
| Ashby | `GET https://api.ashbyhq.com/posting-api/job-board/{board}?includeCompensation=true` | No | Yes, [public job posting API](https://developers.ashbyhq.com/docs/public-job-posting-api) |
| Workday | `POST https://{tenant}.{wdN}.myworkdayjobs.com/wday/cxs/{tenant}/{site}/jobs` | No | **No.** It is the JSON the career site loads for itself, so it can change without notice. |

The Greenhouse page I read states no rate limit and no terms for the API. Read each site's terms and the terms of the company whose jobs you collect. Robots.txt is not a licence.

## What each script does

**Greenhouse.** One request per board. `--pay` adds `pay_transparency=true` to the same request, so pay costs nothing extra. One job can carry several ranges for different regions, and the script writes all of them into one `pay` cell. `--title` is a substring match.

**Ashby.** One request per board with compensation. The script reads the `Salary` component only, so equity and bonus never end up in `salary_min`. It keeps `salary_currency` and `salary_interval` next to the numbers, because boards mix currencies and a few jobs are paid per month. `--salary-only` drops jobs without a salary.

**Lever.** Reads every board, then merges postings that share a company, a title and a team (Lever lists a role once per city). Each merged row keeps all locations, a `copies` count and the link of the newest copy. Pay ranges are widened across copies that share a currency and an interval. With `--want` the rows are ranked by a score: a word in the title adds 3, in the team name 2, in the description 1, then one point each for remote, a pay range and a posting under 14 days old. The weights are my own choice, not anything Lever defines.

**Workday.** Checks `robots.txt` on the tenant first and stops if the path is disallowed. Pages hold 20 jobs, because 21 and 50 both returned HTTP 400. The list stops at 2,000 even when the site has more, so the script stops when a page repeats. To get under the ceiling, pass a facet from the first response, for example the Sales category on NVIDIA:

```bash
python scripts/workday_jobs.py https://nvidia.wd5.myworkdayjobs.com/NVIDIAExternalCareerSite \
    --pages 17 --facet jobFamilyGroup=0c40f6bd1d8f10ae43ffcac5bbec7e90
```

The list rows carry only text such as "Posted 4 Days Ago". The script subtracts the number from today's date and marks "30+" rows as `on_or_before`, because that value is a lower bound.

## What I measured

All runs on October 3, 2026 against live public boards. These are counts of that moment, not constants.

| Check | Result |
|---|---|
| Greenhouse, `dropbox figma stripe` | 39, 162 and 715 open jobs, 916 rows in one CSV |
| Greenhouse, `--title engineer --pay` | 200 rows, 31 with a pay range (Dropbox 4 of 4, Figma 27 of 31, Stripe 0 of 165) |
| Ashby, `ramp ashby replit linear notion cursor deel` | 590 jobs, 276 with a salary. Linear, Notion and Cursor published none. Deel answered with an empty list. |
| Ashby, `--title engineer --salary-only` on Ramp, Ashby, Replit | 101 rows |
| Lever, `spotify outreach nium zoox` | 362 postings became 349 rows after merging 13 repeats |
| Workday, NVIDIA | `total` reported as 2,000, facet counts add up to 2,679 |
| Workday, NVIDIA Sales facet | `total` 328, as the facet count said |
| Workday, Salesforce | `total` 1,525, facet sum 1,539 |
| Made-up names | `not_found` on Greenhouse, Lever and Ashby, HTTP 404 message on Workday |

The pay numbers are a reminder that many boards publish no pay at all. A zero means "not published on this board", not "unpaid".

To check the scripts yourself:

```bash
python -m unittest discover -s tests -v          # offline, no network
python scripts/greenhouse_jobs.py dropbox        # live smoke test
```

## Limits

- **You bring the boards.** None of these endpoints searches all companies by keyword.
- **Published jobs only.** Applications and candidates sit behind each vendor's authenticated API.
- **One board at a time.** The scripts pause between boards (`--delay`). Ashby answers are large: one board with compensation was about 2.7 MB (2,656,325 bytes on October 3, 2026), because each job carries its description twice.
- **Workday is undocumented.** It may break, and some tenants may block it.
- **Lever EU.** Lever has an EU instance at `api.eu.lever.co` (listed in its README). `lever_jobs.py` calls only the global host, so an EU company shows as `not_found`. I could not test the EU host from my setup, so I did not add it.
- **Greenhouse EU.** Boards on `job-boards.eu.greenhouse.io` are untested.
- **Titles.** `--title` matches substrings, so `engineer` also matches "Engineering Manager". In my Ashby data 198 of 590 titles contain the letters and 167 contain the whole word.
- **Snapshots.** Jobs open and close all day.

## Honest comparison with the hosted option

These scripts are free and fine for a handful of boards. They get tiresome when the list grows. I also run paid Apify Actors for the same job, so here is where each one fits.

| | These scripts | Hosted Actors (paid, made by me) |
|---|---|---|
| Cost | Free | Pay per company. Store API on October 3, 2026: $0.10 per company on the Free plan for the Greenhouse, Lever, Ashby and Workday Actors, up to 1,000 jobs included, less on paid Apify plans |
| Input | Board names, one ATS per script | Board links, company websites or plain names (per the Store page) |
| Many companies | You maintain the list and the retries | One run for the whole list |
| "What changed since yesterday" | Not included. Save the CSVs and compare them yourself | An only-new-jobs mode (per the Store page) |
| Account | None | Apify account and API token |
| Control and cost of a mistake | Runs on your machine | A company name that is not on the ATS is still charged (per the Store page) |

Per-job Actors from other authors can be cheaper than a per-company price when boards are small. At 20 open jobs per company, $0.10 per company is $5 per 1,000 jobs, while per-job Actors that charge $0.002 to $0.004 per job cost $2 to $4 per 1,000 jobs. My own per-company price pays off on large boards. If your list is small or your boards are small, use the scripts here or someone else's per-job Actor.

**Hosted Actors (paid, same author as this repo): <https://apify.com/conserving_celerytop>**

I have not run the Actors for this repo. Their prices and features above come from their Store pages and the public Apify API.

## Longer write-ups

The scripts come from these guides, which explain the traps in the data (mixed currencies, typos in salaries, Workday's date text) in more detail. Each guide has a disclosure at the top.

- [Greenhouse Jobs API: Get Every Open Job in Python](https://donmangudata-ops.github.io/greenhouse-jobs-api-python/)
- [Ashby Job Board API: Jobs and Salaries in Python](https://donmangudata-ops.github.io/ashby-job-board-api-python/)
- [Lever Postings API: Pull Open Jobs With Python](https://donmangudata-ops.github.io/lever-postings-api-python/)
- [Workday Jobs API: Pull Open Jobs From Career Sites](https://donmangudata-ops.github.io/workday-jobs-api-python/)

## Not affiliated

Greenhouse, Lever, Ashby and Workday are trademarks of their owners. This repo is not affiliated with or endorsed by any of them. The scripts read only job postings that companies publish on public career sites, with no login.

## Contributing and license

See [CONTRIBUTING.md](CONTRIBUTING.md). MIT license, see [LICENSE](LICENSE). Made by Don Mangu.
