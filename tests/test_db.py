import json
import tempfile
import unittest
from pathlib import Path

from scraper import dashboard, db
from scraper.models import Job


def J(cid, jid, title, verdict="ELIGIBLE", score=80.0):
    return Job(company_id=cid, company_name=cid.upper(), source="lever", title=title, job_id=jid,
               url=f"https://x/{jid}", location="Brazil", verdict=verdict, score=score, techs=["GO"], reasons=["ok"])


class DbTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.conn = db.connect(Path(self.tmp.name) / "t.db")

    def tearDown(self):
        self.conn.close(); self.tmp.cleanup()

    def state(self, key):
        return self.conn.execute("SELECT status FROM jobs WHERE job_key=?", (key,)).fetchone()["status"]

    def test_new_and_closed_between_runs(self):
        ok = {"a": {"ok": True, "count": 2}}
        r1 = db.save_run(self.conn, [J("a", "1", "A"), J("a", "2", "B")], ok)
        r2 = db.save_run(self.conn, [J("a", "2", "B"), J("a", "3", "C")], {"a": {"ok": True, "count": 2}})
        run2 = self.conn.execute("SELECT * FROM runs WHERE run_id=?", (r2,)).fetchone()
        self.assertEqual((run2["new_count"], run2["closed_count"], run2["total"]), (1, 1, 2))
        self.assertEqual(self.state("a:1"), "closed")
        self.assertEqual(self.state("a:2"), "open")
        self.assertEqual(self.state("a:3"), "open")
        self.assertEqual(self.conn.execute("SELECT first_run_id FROM jobs WHERE job_key='a:3'").fetchone()[0], r2)
        self.assertLess(r1, r2)

    def test_failed_or_empty_company_never_closes_jobs(self):
        ok = {"a": {"ok": True, "count": 1}, "b": {"ok": True, "count": 1}}
        db.save_run(self.conn, [J("a", "1", "A"), J("b", "2", "B")], ok)
        db.save_run(self.conn, [J("b", "2", "B")],
                    {"a": {"ok": False, "count": 0, "error": "timeout"}, "b": {"ok": True, "count": 1}})
        self.assertEqual(self.state("a:1"), "open")
        db.save_run(self.conn, [J("b", "2", "B")],
                    {"a": {"ok": True, "count": 0}, "b": {"ok": True, "count": 1}})   # 0 vagas: suspeito, não encerra
        self.assertEqual(self.state("a:1"), "open")

    def test_all_failed_run_is_not_recorded(self):
        db.save_run(self.conn, [J("a", "1", "A")], {"a": {"ok": True, "count": 1}})
        r = db.save_run(self.conn, [], {"a": {"ok": False, "error": "x"}, "b": {"ok": False, "error": "y"}})
        self.assertEqual(r, 0)                                          # 0 = não gravada
        counts = {t: self.conn.execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0]
                  for t in ("runs", "run_companies", "day_summary")}
        self.assertEqual(counts, {"runs": 1, "run_companies": 1, "day_summary": 1})
        self.assertEqual(self.state("a:1"), "open")

    def test_job_reopens_and_only_the_net_change_is_recorded(self):
        """Fechar e reabrir no mesmo dia se anula; a nota 50 -> 90 vira UM evento (e não há mais linha por execução)."""
        db.save_run(self.conn, [J("a", "1", "A", score=50)], {"a": {"ok": True, "count": 1}})
        db.save_run(self.conn, [J("a", "2", "B")], {"a": {"ok": True, "count": 1}})     # a:1 encerra
        db.save_run(self.conn, [J("a", "1", "A", score=90)], {"a": {"ok": True, "count": 1}})  # volta
        self.assertEqual(self.state("a:1"), "open")
        ev = [tuple(r) for r in self.conn.execute(
            "SELECT job_key, kind, field, old, new FROM job_events WHERE job_key='a:1' ORDER BY kind, field")]
        self.assertEqual(ev, [("a:1", "mudou", "nota", "50", "90")])                   # sem 'saiu' nem 'voltou'
        self.assertEqual(self.conn.execute("SELECT COUNT(*) FROM job_snapshots").fetchone()[0], 0)

    def test_other_company_untouched_on_partial_run(self):
        db.save_run(self.conn, [J("a", "1", "A"), J("b", "9", "Z")], {"a": {"ok": True, "count": 1}, "b": {"ok": True, "count": 1}})
        db.save_run(self.conn, [J("a", "1", "A")], {"a": {"ok": True, "count": 1}})     # --only a
        self.assertEqual(self.state("b:9"), "open")

    def test_rescore_all_uses_current_profile(self):
        prof = json.loads((Path(__file__).parent.parent / "config" / "profile.json").read_text(encoding="utf-8"))
        j = J("a", "1", "Senior Salesforce Developer", verdict="MAYBE", score=1.0)
        db.save_run(self.conn, [j], {"a": {"ok": True, "count": 1}})
        self.assertEqual(db.rescore_all(self.conn, prof), 1)
        r = self.conn.execute("SELECT verdict, score, techs FROM jobs").fetchone()
        self.assertEqual(r["verdict"], "ELIGIBLE")
        self.assertIn("SALESFORCE", json.loads(r["techs"]))

    def test_dashboard_embeds_valid_json(self):
        db.save_run(self.conn, [J("a", "1", "Vaga </script> teste")], {"a": {"ok": True, "count": 1}})
        out = dashboard.build(self.conn, Path(self.tmp.name) / "d.html")
        html = out.read_text(encoding="utf-8")
        self.assertNotIn("/*__DATA__*/", html)
        self.assertNotIn("Vaga </script>", html)         # "</" escapado dentro do JSON embutido
        start = html.index("const DATA = ") + len("const DATA = ")
        data = json.JSONDecoder().raw_decode(html[start:])[0]
        self.assertEqual(data["jobs"][0]["title"], "Vaga </script> teste")

    def test_presenciais_report_groups_bahia(self):
        from scraper import reports
        job = Job(company_id="bydbrasil", company_name="BYD Brasil", source="gupy",
                  title="Inspetor(a) de Qualidade", location="Camaçari, BA",
                  workplace_type="onsite", url="https://x/1", score=40.0, verdict="MAYBE")
        db.save_run(self.conn, [job], {"bydbrasil": {"ok": True, "count": 1}})
        out = reports.build_presenciais(self.conn, Path(self.tmp.name) / "p.md")
        txt = out.read_text(encoding="utf-8")
        self.assertIn("Bahia (BA)", txt)
        self.assertIn("Camaçari, BA", txt)
        self.assertIn("BYD Brasil", txt)
        self.assertEqual(reports.estado("Camaçari, BA"), "BA")
        self.assertEqual(reports.estado("Brasil - BR"), "BR")


if __name__ == "__main__":
    unittest.main()
