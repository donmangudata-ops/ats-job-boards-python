"""Offline checks for the pure functions. No network. Fixtures are made up.

Run from the repo root:  python -m unittest discover -s tests -v
"""
import os
import sys
import unittest
from datetime import date

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scripts"))

import ashby_jobs  # noqa: E402
import greenhouse_jobs  # noqa: E402
import lever_jobs  # noqa: E402
import workday_jobs  # noqa: E402


class GreenhouseTests(unittest.TestCase):
    def test_pay_ranges_convert_cents(self):
        job = {"pay_input_ranges": [
            {"min_cents": 20270000, "max_cents": 27430000, "currency_type": "USD", "title": "US Zone 2:"}]}
        r = greenhouse_jobs.pay_ranges(job)
        self.assertEqual(r[0]["min"], 202700.0)
        self.assertEqual(r[0]["max"], 274300.0)
        self.assertEqual(greenhouse_jobs.pay_text(job), "US Zone 2: 202700-274300 USD")

    def test_no_pay_is_empty(self):
        self.assertEqual(greenhouse_jobs.pay_ranges({}), [])
        self.assertEqual(greenhouse_jobs.pay_text({"pay_input_ranges": None}), "")

    def test_flatten_joins_departments(self):
        job = {"id": 1, "title": "Engineer", "absolute_url": "https://x",
               "departments": [{"name": "A"}, {"name": "B"}], "offices": [{"name": "Remote"}]}
        row = greenhouse_jobs.flatten("acme", job)
        self.assertEqual(row["departments"], "A > B")
        self.assertEqual(row["offices"], "Remote")
        self.assertEqual(row["location"], "")


class AshbyTests(unittest.TestCase):
    def job(self, comps):
        return {"id": "1", "title": " Engineer", "jobUrl": "https://x",
                "location": "NYC", "secondaryLocations": [{"location": "Remote"}],
                "compensation": {"summaryComponents": comps}}

    def test_salary_skips_equity(self):
        comps = [{"compensationType": "EquityPercentage", "minValue": 1, "maxValue": 2},
                 {"compensationType": "Salary", "minValue": 100, "maxValue": 200,
                  "currencyCode": "USD", "interval": "1 YEAR"}]
        self.assertEqual(ashby_jobs.salary(self.job(comps))["minValue"], 100)

    def test_flatten_strips_title_and_joins_places(self):
        row = ashby_jobs.flatten("acme", self.job([]))
        self.assertEqual(row["title"], "Engineer")
        self.assertEqual(row["locations"], "NYC; Remote")
        self.assertEqual(row["salary_min"], "")

    def test_job_without_compensation(self):
        self.assertIsNone(ashby_jobs.salary({"id": "1"}))


class LeverTests(unittest.TestCase):
    def posting(self, pid, city, created, site="acme", low=None):
        p = {"id": pid, "site": site, "text": "Data Engineer", "createdAt": created,
             "hostedUrl": f"https://jobs.lever.co/{site}/{pid}",
             "categories": {"team": "Data", "location": city, "allLocations": [city]}}
        if low is not None:
            p["salaryRange"] = {"min": low, "max": low + 10, "currency": "USD", "interval": "per-year-salary"}
        return p

    def test_copies_in_one_company_merge(self):
        rows = lever_jobs.dedupe([self.posting("a", "London", 2), self.posting("b", "Paris", 1)])
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["copies"], 2)
        self.assertEqual(rows[0]["places"], ["London", "Paris"])

    def test_two_companies_never_merge(self):
        rows = lever_jobs.dedupe([self.posting("a", "London", 2, site="one"),
                                  self.posting("b", "London", 1, site="two")])
        self.assertEqual(len(rows), 2)

    def test_pay_widens_over_copies(self):
        rows = lever_jobs.dedupe([self.posting("a", "London", 2, low=100), self.posting("b", "Paris", 1, low=90)])
        self.assertEqual((rows[0]["pay"]["min"], rows[0]["pay"]["max"]), (90, 110))

    def test_score_whole_words_only(self):
        p = {"text": "Database Admin", "categories": {"team": ""}, "descriptionPlain": "", "createdAt": 0}
        self.assertEqual(lever_jobs.score(p, ["data"], now_ms=10 ** 15), 0)
        p["text"] = "Data Admin"
        self.assertEqual(lever_jobs.score(p, ["data"], now_ms=10 ** 15), 3)


class WorkdayTests(unittest.TestCase):
    today = date(2026, 10, 3)

    def test_parse_posted(self):
        f = workday_jobs.parse_posted
        self.assertEqual(f("Posted Today", self.today), (self.today, "exact"))
        self.assertEqual(f("Posted Yesterday", self.today), (date(2026, 10, 2), "exact"))
        self.assertEqual(f("Posted 30 Days Ago", self.today), (date(2026, 9, 3), "exact"))
        self.assertEqual(f("Posted 30+ Days Ago", self.today), (date(2026, 9, 3), "on_or_before"))
        self.assertEqual(f("", self.today), (None, "unknown"))

    def test_split_url_ignores_locale(self):
        host, tenant, site = workday_jobs.split_url("https://acme.wd5.myworkdayjobs.com/en-US/Careers")
        self.assertEqual((host, tenant, site), ("acme.wd5.myworkdayjobs.com", "acme", "Careers"))


if __name__ == "__main__":
    unittest.main()
