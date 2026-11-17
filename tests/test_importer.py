"""Importação de vagas de fora (captura do LinkedIn, planilha): formatos, campos, datas e idempotência."""
import json
import tempfile
import unittest
from datetime import datetime
from pathlib import Path
from unittest import mock

from scraper import dashboard, db, importer, paths

BASE = datetime(2026, 11, 16, 12, 0)

SHEET = {
    "fonte": "LinkedIn", "capturado_em": "2026-11-16",
    "vagas": [
        {"#": 1, "Vaga": "Desenvolvedor Salesforce Sênior", "Empresa": "Acme", "Aderência": "Alta", "Local": "São Paulo, SP",
         "Modelo / contrato": "Híbrido (2 dias) · CLT", "Publicada": "há 3 dias", "Candidaturas": "53 cliques",
         "Senioridade": "Sênior", "Requisitos / stack": "Apex, LWC, Flows e integrações REST",
         "Salário / benefícios": "R$ 14K/mês CLT + benefícios", "Observações": "Candidatura simplificada",
         "Link": "https://www.linkedin.com/jobs/view/4490000001"},
        {"#": 2, "Vaga": "Analista Salesforce", "Empresa": "Beta", "Aderência": "Baixa", "Local": "Brasil",
         "Modelo / contrato": "Remoto · integral", "Publicada": "há 10 h", "Candidaturas": 28,
         "Requisitos / stack": "—", "Salário / benefícios": "VA/VR, saúde e odonto", "Observações": "—",
         "Link": '=HYPERLINK("https://www.linkedin.com/jobs/view/4490000002","abrir")'},
        {"#": 3, "Vaga": "", "Empresa": "Sem título"},                       # linha sem título: ignorada
    ],
}


def write(tmp, name, content):
    p = Path(tmp) / name
    p.write_text(content if isinstance(content, str) else json.dumps(content, ensure_ascii=False), encoding="utf-8")
    return p


class ParseTests(unittest.TestCase):
    def test_sheet_columns_become_the_standard_record(self):
        with tempfile.TemporaryDirectory() as tmp:
            jobs = importer.parse_file(write(tmp, "v.json", SHEET))
        self.assertEqual(len(jobs), 2)
        a, b = jobs
        self.assertEqual((a.source, a.job_id, a.company_name), ("linkedin", "4490000001", "Acme"))
        self.assertEqual((a.workplace_type, a.commitment), ("hybrid", "CLT"))
        self.assertEqual(a.description, "Apex, LWC, Flows e integrações REST")
        self.assertEqual(a.posted_at, "2026-11-13")                          # "há 3 dias" a partir de 16/11
        self.assertIn("R$ 14K", a.salary_text)
        self.assertEqual(a.metadata["aderência (planilha)"], "Alta")
        self.assertEqual(a.metadata["candidaturas"], "53 cliques")
        self.assertEqual(a.raw["import"]["Vaga"], "Desenvolvedor Salesforce Sênior")   # linha original guardada
        # benefícios sem valor em dinheiro viram seção, não salário; link de planilha (=HYPERLINK) vira URL
        self.assertEqual(b.salary_text, "")
        self.assertEqual([s["title"] for s in b.sections], ["Benefícios"])
        self.assertEqual(b.url, "https://www.linkedin.com/jobs/view/4490000002")
        self.assertEqual((b.posted_at, b.workplace_type, b.description), ("2026-11-16", "remote", ""))
        self.assertEqual(b.metadata["candidaturas"], "28")
        self.assertNotIn("", b.metadata)                                       # coluna "#" não vira metadado

    def test_english_columns_csv_and_markdown(self):
        csv_text = "title,company,location,url,posted\nGo Dev,Acme,Brazil,https://www.linkedin.com/jobs/view/4490000003,2026-11-10\n"
        md = "| Cargo | Empresa | Link |\n| --- | --- | --- |\n| Dev Python | Beta | https://www.linkedin.com/jobs/view/4490000004 |\n"
        with tempfile.TemporaryDirectory() as tmp:
            c = importer.parse_file(write(tmp, "v.csv", csv_text))
            m = importer.parse_file(write(tmp, "v.md", md))
        self.assertEqual((c[0].title, c[0].job_id, c[0].posted_at), ("Go Dev", "4490000003", "2026-11-10"))
        self.assertEqual((m[0].title, m[0].company_name, m[0].job_id), ("Dev Python", "Beta", "4490000004"))

    def test_relative_dates(self):
        f = lambda s: importer.parse_posted(s, BASE)                           # noqa: E731
        self.assertEqual(f("há 43 min"), "2026-11-16")
        self.assertEqual(f("há 10 h"), "2026-11-16")
        self.assertEqual(f("ontem"), "2026-11-15")
        self.assertEqual(f("há 2 semanas"), "2026-11-02")
        self.assertEqual(f("3 days ago"), "2026-11-13")
        self.assertEqual(f("10/11/2026"), "2026-11-10")
        self.assertEqual(f("quando der"), "")

    def test_job_without_linkedin_id_gets_a_stable_fingerprint(self):
        row = {"Vaga": "Dev", "Empresa": "Acme", "Local": "SP"}
        a, b = importer.to_job(row), importer.to_job(dict(row))
        self.assertEqual(a.job_id, b.job_id)
        self.assertEqual(len(a.job_id), 12)

    def test_clear_errors_for_bad_files(self):
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaises(ValueError):
                importer.parse_file(write(tmp, "vazio.json", ""))
            with self.assertRaises(ValueError):
                importer.parse_file(write(tmp, "ruim.json", "{nao e json"))
            with self.assertRaises(ValueError):
                importer.parse_file(write(tmp, "sem.json", {"jobs": [{"foo": 1}]}))


class RunImportTests(unittest.TestCase):
    def test_import_is_idempotent_keeps_old_jobs_open_and_shows_up_in_the_panel(self):
        from scraper.models import Job
        with tempfile.TemporaryDirectory() as tmp:
            home = Path(tmp) / "home"
            (home / "config").mkdir(parents=True)
            (home / "config" / "profile.json").write_text(
                (Path(__file__).resolve().parent.parent / "config" / "profile.json").read_text(encoding="utf-8"), encoding="utf-8")
            with mock.patch.object(paths, "HOME", home), mock.patch.object(paths, "DATA", home / "data"), \
                    mock.patch.object(paths, "OUT", home / "out"), mock.patch.object(paths, "CONFIG", home / "config"), \
                    mock.patch.object(db, "DEFAULT_DB", home / "data" / "vagas.db"):
                conn = db.connect()
                db.save_run(conn, [Job(company_id="acme", company_name="Acme", source="greenhouse", title="Antiga", job_id="9",
                                       url="u", description="d")], {"acme": {"ok": True, "count": 1}})
                conn.close()
                f = write(tmp, "v.json", SHEET)
                r1 = importer.run_import(f)
                r2 = importer.run_import(f)
                self.assertEqual((r1["lidas"], r1["novas"]), (2, 2))
                self.assertEqual((r2["novas"], r2["atualizadas"]), (0, 2))
                conn = db.connect()
                self.assertEqual(conn.execute("SELECT status FROM jobs WHERE job_key='acme:9'").fetchone()[0], "open")
                self.assertEqual(conn.execute("SELECT versions FROM jobs WHERE source='linkedin' LIMIT 1").fetchone()[0], 1)
                data = dashboard.collect(conn)
                src = next(c for c in data["companies"] if c["company_id"] == "linkedin")
                conn.close()
                self.assertEqual((src["ok"], src["count"], src["imported"]), (True, 2, True))
                self.assertTrue((home / "out" / "dashboard.html").exists())


if __name__ == "__main__":
    unittest.main()
