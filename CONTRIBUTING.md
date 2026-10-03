# Contributing

Small fixes are welcome: a broken endpoint, a wrong field, a typo, a test.

## Ground rules

- **Public endpoints only.** No login, no scraping behind authentication, no way around a block.
- **Stay polite.** One board at a time, with a pause. A change that sends requests in parallel will not be merged.
- **No promotion in issues or pull requests.** Keep them about the code.
- **No new dependencies** unless they are clearly worth it. The scripts need only `requests`.
- **Plain text.** No em dashes or en dashes in docs and comments, short sentences.

## Before you open a pull request

```bash
pip install -r requirements.txt
python -m unittest discover -s tests -v
```

If you changed what a script reads, also run it once against a live public board and say in the pull request what you ran and what you saw. Boards change daily, so give the date.

## Good first issues

- Lever EU instance (`api.eu.lever.co`, listed in Lever's README). It needs a tester with an EU board.
- Greenhouse boards on `job-boards.eu.greenhouse.io`.
- A whole-word option for `--title`.
- An optional `--annualize` for Ashby salaries that keeps the original columns.

## Reporting a bug

Open an issue with the command you ran, the board name, the date and the last lines of output. Please do not post anything that identifies a candidate or a private person. These scripts read job postings only.
