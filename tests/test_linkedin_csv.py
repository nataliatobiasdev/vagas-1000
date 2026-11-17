"""Planilha da captura do LinkedIn (formato do Claude no Chrome) entra na aba LinkedIn com aderência, senioridade e contrato."""
import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from scraper import dashboard, db, importer  # noqa: E402
from scraper.filtering import score_job  # noqa: E402

SAMPLE = ROOT / "tests" / "fixtures" / "linkedin_salesforce_sample.csv"


class LinkedinCsvTests(unittest.TestCase):
    def test_columns_of_the_capture_map_to_the_linkedin_tab(self):
        jobs = importer.parse_file(SAMPLE)
        self.assertEqual(len(jobs), 3)
        fits = [j.metadata.get("aderência (planilha)") for j in jobs]
        self.assertEqual(fits, ["Alta", "Média", "Baixa"])                       # a coluna aderencia_salesforce
        self.assertTrue(all(j.metadata.get("senioridade") for j in jobs))        # criterio_senioridade
        self.assertTrue(all(j.commitment == "Tempo integral" for j in jobs))     # tipo_contrato
        self.assertTrue(all(j.description for j in jobs))
        self.assertEqual(jobs[0].source, "linkedin")
        self.assertIn("origem_busca", jobs[0].metadata)                          # o que não tem coluna própria vai a metadados

    def test_import_marks_new_jobs_on_the_day_and_shows_them_in_the_linkedin_tab(self):
        with tempfile.TemporaryDirectory() as tmp:
            conn = db.connect(Path(tmp) / "t.db")
            try:
                jobs = importer.parse_file(SAMPLE)
                profile = json.loads((ROOT / "config" / "profile.json").read_text(encoding="utf-8"))
                for j in jobs:
                    score_job(j, profile)                                        # o mesmo caminho do run_import
                res = db.save_import(conn, jobs, [{"company_id": "linkedin", "name": "LinkedIn (importado)", "adapter": "importado",
                                                   "board_url": "", "composite_score": None}])
                self.assertEqual(res["novas"], 3)
                self.assertEqual(conn.execute("SELECT COUNT(*) FROM job_events WHERE kind='entrou'").fetchone()[0], 3)
                data = dashboard.collect(conn)
                li = [j for j in data["jobs"] if j["li"]]
                self.assertEqual(len(li), 3)
                self.assertEqual(sorted(j["li"]["fit"] for j in li), ["Alta", "Baixa", "Média"])
            finally:
                conn.close()


if __name__ == "__main__":
    unittest.main()
