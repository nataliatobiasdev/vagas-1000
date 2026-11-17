"""Indicadores do alto da tela Início e fontes do painel quando uma fonte (a Lever) fica fora do ar."""
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from scraper import dashboard, db, stats  # noqa: E402
from scraper.models import Job  # noqa: E402


def job(cid: str, n: int, verdict: str = "BLOCKED") -> Job:
    j = Job(company_id=cid, company_name=cid.upper(), source="greenhouse", title=f"Vaga {cid} {n}",
            url=f"https://x/{cid}/{n}", job_id=f"{cid}-{n}")
    j.verdict, j.score = verdict, 50.0
    return j


COMPANIES = [{"company_id": c, "name": c.upper(), "adapter": "greenhouse_api", "board_url": f"https://x/{c}"}
             for c in ("ok1", "lever1", "lever2")]


class BoardStatsTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.conn = db.connect(Path(self.tmp.name) / "t.db")
        self.addCleanup(self.conn.close)
        # execução 1: tudo certo (ok1: 3 vagas, 1 elegível; lever1: 2 vagas, 1 elegível; lever2: 1 vaga)
        jobs = ([job("ok1", 1, "ELIGIBLE"), job("ok1", 2), job("ok1", 3)] + [job("lever1", 1, "ELIGIBLE"), job("lever1", 2)]
                + [job("lever2", 1)])
        ok = lambda n: {"ok": True, "count": n}                                   # noqa: E731
        db.save_run(self.conn, jobs, {"ok1": ok(3), "lever1": ok(2), "lever2": ok(1)}, COMPANIES, "2026-11-17T06:00:00")

    def partial_run_failed(self):
        """Execução 2: a Lever caiu; só ok1 respondeu (as vagas das duas fontes da Lever seguem abertas, não verificadas)."""
        jobs = [job("ok1", 1, "ELIGIBLE"), job("ok1", 2), job("ok1", 3)]
        err = {"ok": False, "error": "HTTPError: HTTP Error 500"}
        db.save_run(self.conn, jobs, {"ok1": {"ok": True, "count": 3}, "lever1": err, "lever2": err}, COMPANIES,
                    "2026-11-17T08:00:00")

    def test_everything_confirmed_when_no_source_failed(self):
        c = stats.board_counts(self.conn)
        self.assertEqual((c["open_confirmed"], c["eligible_confirmed"], c["failing_ids"]), (6, 2, []))
        self.assertEqual((c["unverified_open"], c["open_total"]), (0, 6))

    def test_jobs_of_failed_sources_are_kept_but_counted_apart(self):
        """O alto da tela mostrava 1.201/262 (banco todo) e a busca dizia 1110/219: agora os cartões trazem o confirmado."""
        self.partial_run_failed()
        c = stats.board_counts(self.conn)
        self.assertEqual((c["open_total"], c["eligible_total"]), (6, 2))           # nada foi fechado nem apagado
        self.assertEqual((c["open_confirmed"], c["eligible_confirmed"]), (3, 1))    # o que a última leitura confirmou
        self.assertEqual((c["unverified_open"], c["unverified_eligible"]), (3, 1))
        self.assertEqual(sorted(c["failing_ids"]), ["lever1", "lever2"])

    def test_retrying_only_the_failed_sources_does_not_make_the_others_look_unread(self):
        """Refazer só as que falharam grava uma execução parcial: ok1 não pode virar 'sem leitura' nem lever1 sumir."""
        self.partial_run_failed()
        db.save_run(self.conn, [job("lever1", 1, "ELIGIBLE"), job("lever1", 2)],
                    {"lever1": {"ok": True, "count": 2}, "lever2": {"ok": False, "error": "HTTPError: 502"}},
                    COMPANIES, "2026-11-17T08:30:00")
        c = stats.board_counts(self.conn)
        self.assertEqual(c["failing_ids"], ["lever2"])                              # lever1 voltou; lever2 segue fora
        self.assertEqual((c["open_confirmed"], c["unverified_open"]), (5, 1))
        companies = {x["company_id"]: x for x in dashboard.collect(self.conn)["companies"]}
        self.assertTrue(companies["ok1"]["ok"])                                    # antes virava None ("sem leitura")
        self.assertTrue(companies["lever1"]["ok"])
        self.assertFalse(companies["lever2"]["ok"])

    def test_a_run_where_every_source_failed_is_not_recorded(self):
        before = self.conn.execute("select count(*) from runs").fetchone()[0]
        err = {"ok": False, "error": "x"}
        run_id = db.save_run(self.conn, [], {"lever1": err, "lever2": err}, COMPANIES, "2026-11-17T09:00:00")
        self.assertEqual(run_id, 0)
        self.assertEqual(self.conn.execute("select count(*) from runs").fetchone()[0], before)


class WindowRetryTests(unittest.TestCase):
    def test_window_has_the_retry_button_wired_to_the_failed_sources(self):
        app = (ROOT / "app.py").read_text(encoding="utf-8")
        self.assertIn('CBtn(self, "retry", "Refazer com erro", self.start_retry', app)
        self.assertIn('["--only", *only]', app)                                       # refaz só as fontes que falharam
        self.assertIn("stats.board_counts(con)", app)

    def test_panel_summary_mentions_sources_without_reading(self):
        html = (ROOT / "scraper" / "templates" / "dashboard.html").read_text(encoding="utf-8")
        self.assertIn("sem leitura na última execução (guardadas, não verificadas)", html)


if __name__ == "__main__":
    unittest.main()
