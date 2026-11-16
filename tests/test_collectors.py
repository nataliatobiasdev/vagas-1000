import unittest

from scraper.collectors import _dedupe_by_title, _filter_by_location, _filter_by_title, _filter_by_title_exclude
from scraper.models import Job


def J(title, location=""):
    return Job(company_id="x", company_name="X", source="test", title=title, location=location)


class TitleFilterTests(unittest.TestCase):
    def test_filters_by_regex(self):
        jobs = [J("Software Engineer"), J("Analista de Crédito"),
                J("Pessoa Desenvolvedora Salesforce Sênior"), J("Account Executive")]
        cfg = {"company_id": "x", "title_include": "engineer|desenvolvedor|salesforce"}
        kept = _filter_by_title(jobs, cfg)
        self.assertEqual([j.title for j in kept],
                         ["Software Engineer", "Pessoa Desenvolvedora Salesforce Sênior"])

    def test_no_filter_keeps_all(self):
        jobs = [J("Analista de Crédito"), J("Account Executive")]
        self.assertEqual(len(_filter_by_title(jobs, {"company_id": "x"})), 2)

    def test_exclude_and_location(self):
        jobs = [J("Senior Security Engineer", "Brazil, Remote"),
                J("Junior Software Engineer", "Brazil, Remote"),
                J("Senior Software Engineer", "Remote - USA")]
        cfg = {"company_id": "x", "title_exclude": "junior",
               "location_include": "brazil|latam"}
        kept = _filter_by_title_exclude(_filter_by_location(jobs, cfg), cfg)
        self.assertEqual([j.title for j in kept], ["Senior Security Engineer"])

    def test_dedupe_prefers_brazil(self):
        jobs = [J("Data Engineer II", "Latin America"),
                J("Data Engineer II", "Brazil"),
                J("Data Engineer II", "Mexico, Remote"),
                J("Mobile Engineer", "Brazil")]
        kept = _dedupe_by_title(jobs, {"company_id": "x", "dedupe_by_title": True})
        self.assertEqual(len(kept), 2)
        by_title = {j.title: j.location for j in kept}
        self.assertEqual(by_title["Data Engineer II"], "Brazil")


if __name__ == "__main__":
    unittest.main()
