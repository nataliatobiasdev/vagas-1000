import json
import unittest
from pathlib import Path

from scraper import parsers
from scraper.filtering import score_job, detect_techs

FX = Path(__file__).parent / "fixtures"
PROFILE = json.loads((Path(__file__).parent.parent / "config" / "profile.json").read_text(encoding="utf-8"))


def fx(name: str) -> str:
    return (FX / name).read_text(encoding="utf-8")


class LeverTests(unittest.TestCase):
    def setUp(self):
        self.jobs = parsers.parse_lever_list(fx("lever_list.html"), "ciandt", "CI&T")

    def test_count_and_fields(self):
        self.assertEqual(len(self.jobs), 3)
        j = self.jobs[0]
        self.assertEqual(j.title, "[Job - 32701] Master .NET Specialist, Brazil")
        self.assertEqual(j.job_id, "f4ed1b87-7d43-4465-9d67-e1b3991eb0f7")
        self.assertEqual(j.location, "Brazil")
        self.assertEqual(j.area, "Prod_Aura")
        self.assertEqual(j.workplace_type, "remote")
        self.assertTrue(j.url.endswith("f4ed1b87-7d43-4465-9d67-e1b3991eb0f7"))  # link do título, não o /apply

    def test_detail(self):
        d = parsers.parse_lever_detail(fx("lever_detail.html"))
        self.assertIn("GraphQL", d["description"])
        self.assertEqual(d["workplace_type"], "remote")
        self.assertEqual(d["area"], "Prod_Aura")


class GreenhouseTests(unittest.TestCase):
    def test_list(self):
        jobs = parsers.parse_greenhouse_list(fx("greenhouse_list.html"), "zupinnovation", "Zup Innovation")
        self.assertEqual(len(jobs), 2)
        self.assertEqual(jobs[0].title, "Pessoa Desenvolvedora Salesforce Sênior")
        self.assertEqual(jobs[0].job_id, "8046178003")
        self.assertEqual(jobs[0].workplace_type, "remote")
        self.assertEqual(jobs[0].area, "Zup Innovation")

    def test_empty_state(self):
        self.assertTrue(parsers.greenhouse_is_empty(fx("greenhouse_empty.html")))
        self.assertFalse(parsers.greenhouse_is_empty(fx("greenhouse_list.html")))

    def test_detail(self):
        d = parsers.parse_greenhouse_detail(fx("greenhouse_detail.html"))
        self.assertIn("Apex", d["description"])
        self.assertEqual(d["location"], "Remoto")


class LeverApiTests(unittest.TestCase):
    def setUp(self):
        payload = json.loads(fx("lever_api.json"))
        self.jobs = parsers.parse_lever_api(payload, "acme", "ACME",
                                            {"location": "Brazil", "workplaceType": "remote"})

    def test_site_filters(self):
        self.assertEqual(len(self.jobs), 1)
        self.assertEqual(self.jobs[0].job_id, "abc-1")

    def test_fields(self):
        j = self.jobs[0]
        self.assertEqual(j.title, "Senior Salesforce Developer")
        self.assertEqual(j.location, "Brazil")
        self.assertEqual(j.area, "Prod")
        self.assertEqual(j.commitment, "Homeoffice")
        self.assertEqual(j.workplace_type, "remote")
        self.assertTrue(j.url.endswith("/abc-1"))

    def test_description_combines_body_additional_and_lists(self):
        d = self.jobs[0].description
        for token in ("Apex", "LWC", "AWS Lambda", "SOQL", "Go"):
            self.assertIn(token, d)


class AshbyApiTests(unittest.TestCase):
    def setUp(self):
        payload = json.loads(fx("ashby_api.json"))
        self.jobs = parsers.parse_ashby_api(payload, "acme", "ACME")

    def test_unlisted_is_skipped(self):
        self.assertEqual([j.job_id for j in self.jobs], ["as-1", "as-2"])

    def test_fields_and_secondary_location(self):
        j = self.jobs[0]
        self.assertEqual(j.title, "Staff Software Engineer")
        self.assertIn("São Paulo", j.location)
        self.assertIn("Remote - Brazil", j.location)
        self.assertEqual(j.workplace_type, "remote")
        self.assertEqual(j.area, "Engineer")
        self.assertEqual(j.commitment, "FullTime")
        self.assertIn("Go", j.description)


class GreenhouseApiTests(unittest.TestCase):
    def setUp(self):
        payload = json.loads(fx("greenhouse_api.json"))
        self.jobs = parsers.parse_greenhouse_api(payload, "acme", "ACME")

    def test_fields(self):
        self.assertEqual(len(self.jobs), 2)
        j = self.jobs[0]
        self.assertEqual(j.job_id, "111")
        self.assertIn("Salesforce", j.title)
        self.assertEqual(j.location, "São Paulo, Brazil")
        self.assertEqual(j.area, "CRM Engineering")
        self.assertEqual(j.commitment, "Full-time")
        self.assertTrue(j.url.endswith("/jobs/111"))

    def test_content_is_unescaped_and_text_only(self):
        d = self.jobs[0].description
        self.assertIn("Apex", d)
        self.assertIn("AWS Lambda", d)
        self.assertNotIn("<", d)

    def test_handles_null_metadata_and_no_departments(self):
        j = self.jobs[1]
        self.assertEqual(j.area, "")
        self.assertEqual(j.commitment, "")
        self.assertEqual(j.workplace_type, "remote")


class WorkdayTests(unittest.TestCase):
    def test_list(self):
        payload = json.loads(fx("workday_jobs.json"))
        jobs = parsers.parse_workday_jobs(payload, "salesforce", "Salesforce",
                                          "https://salesforce.wd12.myworkdayjobs.com/External_Career_Site")
        self.assertEqual(len(jobs), 2)
        j = jobs[0]
        self.assertEqual(j.title, "Technical Architect")
        self.assertEqual(j.location, "Brazil - Remote")
        self.assertEqual(j.workplace_type, "remote")
        self.assertEqual(j.job_id, "/job/Brazil---Remote/Technical-Architect_JR123")
        self.assertEqual(j.url, "https://salesforce.wd12.myworkdayjobs.com/External_Career_Site"
                                "/job/Brazil---Remote/Technical-Architect_JR123")

    def test_detail(self):
        d = parsers.parse_workday_detail(json.loads(fx("workday_detail.json")))
        self.assertIn("Apex", d["description"])
        self.assertIn("7+ years", d["description"])
        self.assertNotIn("<", d["description"])
        self.assertEqual(d["location"], "Brazil - Remote")


class GupyTests(unittest.TestCase):
    def test_list(self):
        jobs = parsers.parse_gupy_list(fx("gupy_list.html"), "acme", "ACME", "https://acme.gupy.io")
        self.assertEqual(len(jobs), 2)
        j = jobs[0]
        self.assertEqual(j.job_id, "111")
        self.assertEqual(j.title, "Pessoa Desenvolvedora Back-end Sênior")
        self.assertEqual(j.location, "São Paulo, SP")
        self.assertEqual(j.area, "Tecnologia")
        self.assertEqual(j.workplace_type, "remote")
        self.assertEqual(j.url, "https://acme.gupy.io/jobs/111")

    def test_detail(self):
        d = parsers.parse_gupy_detail(fx("gupy_detail.html"))
        self.assertIn("Go, AWS", d["description"])
        self.assertIn("Construir APIs", d["description"])
        self.assertIn("Inglês fluente", d["description"])
        self.assertNotIn("<", d["description"])


class StoneTests(unittest.TestCase):
    def setUp(self):
        self.jobs = parsers.parse_stone_list(fx("stone_list.html"), "stone", "Stone", "https://jornada.stone.com.br")

    def test_six_cards_wrapper_ignored_and_titles_deduped(self):
        self.assertEqual(len(self.jobs), 6)
        self.assertEqual(self.jobs[0].title, "SOFTWARE ENGINEER GO PL")
        self.assertEqual(self.jobs[1].title, "[Banking/Gerir] Sênior Software Engineer - Golang")

    def test_url_from_parent_anchor_and_id(self):
        j = self.jobs[1]
        self.assertEqual(j.url, "https://jornada.stone.com.br/times/tecnologia/oportunidades/8040600003")
        self.assertEqual(j.job_id, "8040600003")
        self.assertEqual(self.jobs[0].job_id, "8016039003")

    def test_location_area_workplace(self):
        self.assertEqual(self.jobs[1].location, "Brasil - BR")
        self.assertEqual(self.jobs[1].area, "Engenharia & Tecnologia")
        self.assertEqual(self.jobs[3].location, "Florianopolis - SC")
        self.assertEqual(self.jobs[3].workplace_type, "hybrid")

    def test_detail_description(self):
        d = parsers.parse_stone_detail(fx("stone_detail.html"))
        self.assertIn("Go, AWS", d["description"])
        self.assertNotIn("Designer", d["description"])      # "Outras vagas" fica de fora
        self.assertEqual(d["workplace_type"], "remote")


class FilterTests(unittest.TestCase):
    def _score(self, html, cid, name, fn):
        return [score_job(j, PROFILE) for j in fn(fx(html), cid, name)]

    def test_salesforce_senior_brazil_is_eligible(self):
        jobs = self._score("lever_list.html", "ciandt", "CI&T", parsers.parse_lever_list)
        sf = next(j for j in jobs if "Salesforce" in j.title)
        self.assertEqual(sf.verdict, "MAYBE")  # lista sem descrição não confirma requisitos
        self.assertIn("SALESFORCE", sf.techs)

    def test_intern_us_is_blocked(self):
        jobs = self._score("lever_list.html", "ciandt", "CI&T", parsers.parse_lever_list)
        intern = next(j for j in jobs if "Intern" in j.title)
        self.assertEqual(intern.verdict, "BLOCKED")

    def test_ordering_by_score(self):
        jobs = self._score("lever_list.html", "ciandt", "CI&T", parsers.parse_lever_list)
        sf = next(j for j in jobs if "Salesforce" in j.title)
        intern = next(j for j in jobs if "Intern" in j.title)
        self.assertGreater(sf.score, intern.score)

    def test_non_core_stack_is_not_eligible(self):
        from scraper.models import Job
        j = Job("c", "C", "lever", "Senior Developer (.NET), Brazil", location="Brazil",
                description="We build AI and API integration solutions with microservices.")
        score_job(j, PROFILE)
        self.assertEqual(j.verdict, "MAYBE")   # boilerplate de IA/integração não conta; .NET não é core

    def test_salesforce_title_beats_dotnet(self):
        from scraper.models import Job
        sf = score_job(Job("c", "C", "lever", "SR/Master Salesforce Architect, Brazil", location="Brazil"), PROFILE)
        net = score_job(Job("c", "C", "lever", "Tech Lead (.NET / Angular), Brazil", location="Brazil"), PROFILE)
        self.assertEqual(sf.verdict, "MAYBE")
        self.assertGreater(sf.score, net.score)

    def test_generic_techs_hidden_unless_in_title(self):
        from scraper.models import Job
        j = score_job(Job("c", "C", "lever", "Senior Go Developer", location="Brazil",
                          description="Helping enterprises with AI, API integration and GraphQL."), PROFILE)
        self.assertIn("GO", j.techs)
        self.assertNotIn("AI_GENAI", j.techs)
        self.assertNotIn("INTEGRATION_ARCH", j.techs)

    def test_tech_detection(self):
        self.assertIn("AWS", detect_techs("Experiência com AWS Lambda e Python"))
        self.assertIn("PYTHON", detect_techs("Experiência com AWS Lambda e Python"))
        self.assertNotIn("GO", detect_techs("Let's go to market"))

    def test_eligibility_remote_country(self):
        from scraper.filtering import classify_eligibility, is_brazil_location
        self.assertEqual(classify_eligibility("Remote - USA", "remote", PROFILE)[0], "BLOCKED")
        self.assertEqual(classify_eligibility("Poland, Remote", "remote", PROFILE)[0], "BLOCKED")
        self.assertEqual(classify_eligibility("Bogota / Colombia", "onsite", PROFILE)[0], "BLOCKED")
        self.assertEqual(classify_eligibility("Toronto", "hybrid", PROFILE)[0], "BLOCKED")
        self.assertEqual(classify_eligibility("Palo Alto / Miami", "onsite", PROFILE)[0], "BLOCKED")
        self.assertEqual(classify_eligibility("Remote - LATAM", "remote", PROFILE)[0], "ELIGIBLE")
        self.assertEqual(classify_eligibility("Brazil", "remote", PROFILE)[0], "ELIGIBLE")
        self.assertEqual(classify_eligibility("Remoto", "remote", PROFILE)[0], "MAYBE")
        self.assertEqual(classify_eligibility("LATAM", "", PROFILE)[0], "MAYBE")
        self.assertEqual(classify_eligibility("Global", "", PROFILE)[0], "MAYBE")
        self.assertEqual(classify_eligibility("Remote", "remote", PROFILE)[0], "MAYBE")
        self.assertTrue(is_brazil_location("São Paulo, SP"))
        self.assertTrue(is_brazil_location("Belo Horizonte, MG"))
        self.assertTrue(is_brazil_location("Remoto"))
        self.assertFalse(is_brazil_location("Latin America"))
        self.assertFalse(is_brazil_location("Remote - USA"))


if __name__ == "__main__":
    unittest.main()
