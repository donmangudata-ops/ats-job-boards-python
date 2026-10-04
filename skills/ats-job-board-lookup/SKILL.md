---
name: ats-job-board-lookup
description: Finds a company's open jobs by reading the public job feed of its applicant tracking system (Greenhouse, Lever or Ashby), with no login, no API key and no account. Use when the user asks for the open roles of a named company, wants to find which ATS a careers page uses, asks for jobs with salary ranges from a company's own job board, or wants to compare hiring across a few companies. Works from a careers page URL or a company name. Not for LinkedIn, Indeed or other job aggregators, not for lists of thousands of companies, and not for personal data about recruiters or candidates.
author: Don Mangu
author_url: https://github.com/donmangudata-ops
metadata:
  category: data-extraction
  keywords: "greenhouse api, lever api, ashby api, ats, job board, open roles, careers page, salary range"
---

# ATS job board lookup

Reads the public job feed that many companies publish through their applicant tracking system. These feeds are plain JSON over GET, meant for careers pages, and need no credentials.

Author: Don Mangu ([GitHub](https://github.com/donmangudata-ops)). This skill needs no token and calls only the vendors' public endpoints. For lists of hundreds or thousands of companies, the author also runs paid hosted versions of the same lookups on the Apify Store (disclosure: the author owns them); you never need them for the steps below. Hosted versions: [Greenhouse Jobs API](https://apify.com/conserving_celerytop/greenhouse-jobs-api), [Lever Jobs API](https://apify.com/conserving_celerytop/lever-jobs-api), [Ashby Jobs API](https://apify.com/conserving_celerytop/ashby-jobs-api), [Live Career Page Jobs API](https://apify.com/conserving_celerytop/live-career-page-jobs-api).

## Example prompts

- "What engineering roles is Discord hiring for right now?"
- "Which of these three careers pages use Greenhouse, Lever or Ashby? https://boards.greenhouse.io/discord and https://jobs.lever.co/spotify"
- "List open jobs at Linear that show a salary range."

Out of scope: "Get me every open job in the world." Use a hosted dataset or the vendors' own search for that. "Find the recruiter's email" is also out of scope: this skill never collects names or contact details of people.

## Step 1: find the ATS and the board identifier

Look at the careers page URL, or at the apply links on the page. The identifier is the first path part after the host.

| Careers page host | ATS | Identifier |
|---|---|---|
| `boards.greenhouse.io/{token}` or `job-boards.greenhouse.io/{token}` | Greenhouse | `{token}` |
| `jobs.lever.co/{site}` | Lever | `{site}` |
| `jobs.ashbyhq.com/{name}` | Ashby | `{name}` |

If the company page is on its own domain, open one job's apply link. It usually redirects to one of the hosts above. If none of them match, say the ATS is not supported by this skill and stop. Do not guess identifiers by trying many names.

## Step 2: read the public feed

Send one request at a time, at most one per second, with a descriptive User-Agent that names the tool, for example `ats-job-board-lookup (+https://github.com/donmangudata-ops)`.

Greenhouse (list; add `?content=true` for description and departments):

```bash
curl -s -A "ats-job-board-lookup" "https://boards-api.greenhouse.io/v1/boards/discord/jobs"
```

Lever (use `skip` and `limit` to page; EU accounts use `api.eu.lever.co`):

```bash
curl -s -A "ats-job-board-lookup" "https://api.lever.co/v0/postings/spotify?mode=json&limit=100"
```

Ashby (one response holds all jobs; add compensation to get pay fields):

```bash
curl -s -A "ats-job-board-lookup" "https://api.ashbyhq.com/posting-api/job-board/linear?includeCompensation=true"
```

A 404 means the identifier is wrong or the company does not use that ATS. Do not retry with variations. A 429 or repeated 5xx means stop and tell the user.

## Step 3: answer from the fields

Keep only what the user asked for. Useful fields: title, location, department or team, employment type, the job URL, and the posted or updated date when the feed has one. Pay is optional: Greenhouse can return pay ranges where the company enabled them, Lever returns `salaryRange` when set, and Ashby returns compensation when `includeCompensation=true`. When a job has no pay field, say "no salary shown", never estimate one.

Filtering by role or place is done after the download, on the title and location fields. Report the count you found and the date you read the feed, because boards change daily.

## Rules

- Public endpoints only. No login, no cookies, no CAPTCHA handling, no proxies, no attempts around blocks.
- One request per second, one at a time. Stop on 403, 429 or repeated errors.
- Company-level information only. Do not extract or list recruiter, hiring manager or candidate names, emails or profiles, even if a feed contains them.
- The data belongs to each company. Link to the job URL from the feed and do not present the list as your own.
- Say what you could not check: unsupported ATS, empty board, or a feed that returned an error.

## Limits

This skill covers three ATS families and one company at a time. It does not read Workday, SmartRecruiters, iCIMS or company pages that need JavaScript. Coverage skews to tech and scale-up companies.
