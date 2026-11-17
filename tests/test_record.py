"""Registro completo da vaga: campos extras, HTML limpo, histórico de versões e painel."""
import copy
import json
import re
import sqlite3
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from scraper import dashboard, db, parsers, richtext
from scraper.models import Job

FIX = Path(__file__).resolve().parent / "fixtures"


def load(name):
    return json.loads((FIX / name).read_text(encoding="utf-8"))


class RichTextTests(unittest.TestCase):
    def test_removes_scripts_styles_images_and_event_handlers(self):
        dirty = ('<p onclick="x()" style="color:red">Oi <b>mundo</b></p><script>alert(1)</script>'
                 '<img src="http://t.example/pixel.gif" alt="logo"><style>p{}</style>'
                 '<a href="javascript:alert(1)">ruim</a><a href="https://ok.example/x" onclick="y()">bom</a>')
        out = richtext.clean_html(dirty)
        for bad in ("script", "onclick", "style", "pixel", "javascript:"):
            self.assertNotIn(bad, out)
        self.assertIn("<b>mundo</b>", out)
        self.assertIn('href="https://ok.example/x"', out)
        self.assertIn('rel="noopener noreferrer"', out)
        self.assertIn("logo", out)                                   # a imagem vira o texto alternativo

    def test_unescapes_greenhouse_style_content(self):
        out = richtext.clean_html("&lt;h2&gt;Sobre&lt;/h2&gt;&lt;p&gt;Texto&lt;/p&gt;")
        self.assertIn("<h3>Sobre</h3>", out)
        self.assertIn("<p>Texto</p>", out)

    def test_html_to_text_keeps_paragraphs_and_bullets(self):
        t = richtext.html_to_text("<p>Um</p><ul><li>a</li><li>b</li></ul>")
        self.assertIn("Um", t)
        self.assertIn("• a", t)
        self.assertIn("• b", t)


class ParserRecordTests(unittest.TestCase):
    def test_greenhouse_keeps_dates_requisition_offices_salary_and_raw(self):
        payload = copy.deepcopy(load("greenhouse_api.json"))
        j0 = payload["jobs"][0]
        j0.update(first_published="2026-10-02T16:42:51-04:00", updated_at="2026-11-12T16:06:38-05:00",
                  requisition_id="REQ-9", offices=[{"name": "Bogota", "location": "Bogotá, Colombia"}],
                  pay_input_ranges=[{"min_cents": 8000000, "max_cents": 12000000, "currency_type": "USD", "blurb": ""}])
        job = parsers.parse_greenhouse_api(payload, "acme", "Acme")[0]
        self.assertEqual(job.posted_at, "2026-10-02T16:42:51-04:00")
        self.assertEqual(job.requisition_id, "REQ-9")
        self.assertIn("Bogotá, Colombia", job.locations)
        self.assertEqual((job.salary_min, job.salary_max, job.salary_currency), (80000.0, 120000.0, "USD"))
        self.assertIn("80.000", job.salary_text)
        self.assertEqual(job.raw["id"], j0["id"])                    # payload original guardado
        self.assertIn("<p>", job.description_html)

    def test_lever_keeps_sections_apply_url_team_and_created_at(self):
        job = parsers.parse_lever_api(load("lever_api.json"), "acme", "Acme")[0]
        self.assertTrue(job.apply_url or job.url)
        self.assertEqual(job.team, "Prod")
        self.assertTrue(any(s["title"] == "Requirements" for s in job.sections))
        self.assertEqual(job.raw["id"], "abc-1")

    def test_ashby_keeps_description_html_and_locations(self):
        job = parsers.parse_ashby_api(load("ashby_api.json"), "acme", "Acme")[0]
        self.assertIn("São Paulo", job.locations)
        self.assertIn("Remote - Brazil", job.locations)
        self.assertEqual(job.raw["id"], "as-1")

    def test_gupy_detail_builds_sections_steps_and_dates(self):
        nd = {"props": {"pageProps": {"job": {
            "name": "Dev", "description": "<p>Sobre</p>", "responsibilities": "<ul><li>Codar</li></ul>",
            "prerequisites": "<p>Python</p>", "publishedAt": "2026-10-29T14:04:18.410Z", "expiresAt": "2026-12-11",
            "code": "1-2", "jobSteps": [{"name": "Entrevista", "order": 2}, {"name": "Cadastro", "order": 0}],
            "workplaceType": "remote", "careerPage": {"name": "Acme"}}}}}
        html = f'<script id="__NEXT_DATA__" type="application/json">{json.dumps(nd)}</script>'
        d = parsers.parse_gupy_detail(html)
        titles = [s["title"] for s in d["sections"]]
        self.assertIn("Responsabilidades e atribuições", titles)
        steps = next(s for s in d["sections"] if s["title"].startswith("Etapas"))["html"]
        self.assertLess(steps.index("Cadastro"), steps.index("Entrevista"))    # na ordem do processo
        self.assertEqual((d["posted_at"], d["deadline"], d["requisition_id"]),
                         ("2026-10-29T14:04:18.410Z", "2026-12-11", "1-2"))

    def test_apply_detail_overrides_description_but_only_fills_gaps_elsewhere(self):
        j = Job(company_id="a", company_name="A", source="gupy", title="t", description="curta", posted_at="2026-01-01")
        parsers.apply_detail(j, {"description": "completa", "posted_at": "2026-02-02", "deadline": "2026-03-03",
                                 "metadata": {"k": 1}, "raw_detail": {"x": 1}})
        self.assertEqual(j.description, "completa")
        self.assertEqual(j.posted_at, "2026-01-01")                  # já tinha: não troca
        self.assertEqual(j.deadline, "2026-03-03")
        self.assertEqual(j.raw["detail"], {"x": 1})


def J(**kw):
    base = dict(company_id="acme", company_name="Acme", source="greenhouse", title="Dev Go", job_id="1",
                url="https://x/1", location="Brazil", description="texto", score=80.0, verdict="ELIGIBLE")
    base.update(kw)
    return Job(**base)


class ArchiveTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.path = Path(self.tmp.name) / "t.db"
        self.conn = db.connect(self.path)

    def tearDown(self):
        self.conn.close()
        self.tmp.cleanup()

    def row(self, key="acme:1"):
        return self.conn.execute("SELECT * FROM jobs WHERE job_key=?", (key,)).fetchone()

    def test_old_database_is_migrated_without_losing_data(self):
        legacy = Path(self.tmp.name) / "old.db"
        c = sqlite3.connect(legacy)
        c.executescript("""CREATE TABLE jobs (job_key TEXT PRIMARY KEY, company_id TEXT NOT NULL, company_name TEXT, source TEXT,
            job_id TEXT, title TEXT, url TEXT, location TEXT, area TEXT, workplace_type TEXT, commitment TEXT, description TEXT,
            score REAL, verdict TEXT, techs TEXT, reasons TEXT, first_run_id INTEGER NOT NULL, last_run_id INTEGER NOT NULL,
            first_seen TEXT NOT NULL, last_seen TEXT NOT NULL, status TEXT NOT NULL DEFAULT 'open', closed_run_id INTEGER);
            INSERT INTO jobs VALUES('a:1','a','A','x','1','Antiga','u','BR','','','','desc antiga',50,'MAYBE','[]','[]',1,1,'2026-01-01','2026-01-02','open',NULL);""")
        c.commit()
        c.close()
        conn = db.connect(legacy)
        r = conn.execute("SELECT * FROM jobs").fetchone()
        self.assertEqual((r["title"], r["description"]), ("Antiga", "desc antiga"))
        self.assertIn("raw", r.keys())
        self.assertEqual(conn.execute("PRAGMA user_version").fetchone()[0], db.SCHEMA_VERSION)
        conn.close()

    def test_full_record_is_stored_and_versioned_on_change(self):
        j = J(description_html="<p>v1</p>", salary_text="USD 10", raw={"id": 1, "x": "a"}, metadata={"k": "v"},
              locations=["Brazil", "LATAM"], posted_at="2026-10-01", sections=[{"title": "Req", "html": "<ul><li>Go</li></ul>"}])
        db.save_run(self.conn, [j], {"acme": {"ok": True, "count": 1}})
        r = self.row()
        self.assertEqual((r["versions"], json.loads(r["raw"])["x"], r["posted_at"], r["salary_text"]), (1, "a", "2026-10-01", "USD 10"))
        self.assertEqual(json.loads(r["locations"]), ["Brazil", "LATAM"])
        # a fonte edita a descrição: nova versão, a anterior continua guardada
        j2 = J(description="texto novo", description_html="<p>v2</p>", salary_text="USD 10", raw={"id": 1, "x": "b"})
        db.save_run(self.conn, [j2], {"acme": {"ok": True, "count": 1}})
        r = self.row()
        self.assertEqual(r["versions"], 2)
        vs = self.conn.execute("SELECT data FROM job_versions WHERE job_key='acme:1' ORDER BY version_id").fetchall()
        self.assertEqual(json.loads(vs[0]["data"])["description_html"], "<p>v1</p>")
        self.assertEqual(json.loads(vs[1]["data"])["description_html"], "<p>v2</p>")

    def test_unchanged_job_does_not_create_new_version(self):
        for _ in range(3):
            db.save_run(self.conn, [J(description_html="<p>igual</p>")], {"acme": {"ok": True, "count": 1}})
        self.assertEqual(self.row()["versions"], 1)

    def test_run_without_detail_never_erases_stored_detail(self):
        full = J(description="descrição completa", description_html="<p>completa</p>", posted_at="2026-10-01",
                 sections=[{"title": "Req", "html": "<p>x</p>"}], raw={"detail": {"big": 1}})
        db.save_run(self.conn, [full], {"acme": {"ok": True, "count": 1}})
        listing_only = J(description="", raw={"list": {"id": 1}})        # hoje só veio a lista, sem reabrir o detalhe
        db.save_run(self.conn, [listing_only], {"acme": {"ok": True, "count": 1}})
        r = self.row()
        self.assertEqual((r["description"], r["description_html"], r["posted_at"]), ("descrição completa", "<p>completa</p>", "2026-10-01"))
        self.assertEqual(json.loads(r["sections"])[0]["title"], "Req")
        raw = json.loads(r["raw"])
        self.assertEqual((raw["detail"], raw["list"]), ({"big": 1}, {"id": 1}))
        self.assertEqual(r["versions"], 1)                                 # não contou como edição

    def test_closed_job_keeps_everything_and_gets_closed_at(self):
        db.save_run(self.conn, [J(description_html="<p>x</p>", raw={"a": 1}), J(job_id="2", url="u2", title="Outra")],
                    {"acme": {"ok": True, "count": 2}})
        db.save_run(self.conn, [J(job_id="2", url="u2", title="Outra")], {"acme": {"ok": True, "count": 1}})
        r = self.row()
        self.assertEqual(r["status"], "closed")
        self.assertTrue(r["closed_at"])
        self.assertEqual((r["description_html"], json.loads(r["raw"])), ("<p>x</p>", {"a": 1}))

    def test_load_details_returns_cached_fields(self):
        db.save_run(self.conn, [J(description="d" * 500, description_html="<p>x</p>", raw={"detail": {"z": 1}})],
                    {"acme": {"ok": True, "count": 1}})
        known = db.load_details(self.conn, "acme")
        self.assertEqual(known["acme:1"]["raw_detail"], {"z": 1})
        self.assertTrue(known["acme:1"]["detail_at"])


class DashboardRecordTests(unittest.TestCase):
    def test_build_embeds_records_and_never_the_raw_payload(self):
        with tempfile.TemporaryDirectory() as tmp:
            conn = db.connect(Path(tmp) / "t.db")
            db.save_run(conn, [J(description_html="<p>Texto &amp; mais</p>", raw={"segredo_bruto": "NAO-NO-HTML"},
                                 sections=[{"title": "Req", "html": "<p>Go</p>"}])], {"acme": {"ok": True, "count": 1}})
            db.save_run(conn, [J(description="novo", description_html="<p>editado</p>", raw={"segredo_bruto": "NAO-NO-HTML"})],
                        {"acme": {"ok": True, "count": 1}})
            out = dashboard.build(conn, Path(tmp) / "d.html")
            html = out.read_text(encoding="utf-8")
            conn.close()
        self.assertNotIn("NAO-NO-HTML", html)
        m = re.search(r'<script type="application/json" id="rec-0">(.*?)</script>', html, re.S)
        rec = json.loads(m.group(1).replace("<\\/", "</"))
        self.assertEqual(rec["description_html"], "<p>editado</p>")
        self.assertEqual([v["n"] for v in rec["versions"]], [1, 2])
        self.assertTrue(rec["versions"][0]["data"])                       # versão antiga traz o conteúdo antigo
        self.assertIsNone(rec["versions"][1]["data"])                     # a atual não repete
        self.assertTrue(any("descrição" in c for c in rec["versions"][1]["changes"]))

    def test_script_breakout_in_description_is_neutralized(self):
        with tempfile.TemporaryDirectory() as tmp:
            conn = db.connect(Path(tmp) / "t.db")
            db.save_run(conn, [J(title="</script><script>alert(1)</script>", description_html=richtext.clean_html("<p>x</p><script>y()</script>"))],
                        {"acme": {"ok": True, "count": 1}})
            html = dashboard.build(conn, Path(tmp) / "d.html").read_text(encoding="utf-8")
            conn.close()
        self.assertNotIn("</script><script>alert(1)", html)


class PanelWindowTests(unittest.TestCase):
    def test_get_raw_reads_the_payload_from_the_database(self):
        from scraper import panel_window
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "t.db"
            conn = db.connect(path)
            db.save_run(conn, [J(raw={"origem": "api"})], {"acme": {"ok": True, "count": 1}})
            conn.close()
            real_connect = db.connect
            with mock.patch.object(panel_window.db, "connect", lambda *a, **k: real_connect(path)):
                self.assertEqual(panel_window.Api().get_raw("acme:1"), {"origem": "api"})
                self.assertIsNone(panel_window.Api().get_raw("nao:existe"))

    def test_falls_back_to_browser_when_webview_is_unavailable(self):
        import builtins
        from scraper import panel_window
        real_import = builtins.__import__

        def fake(name, *a, **k):
            if name == "webview":
                raise ImportError("sem webview")
            return real_import(name, *a, **k)

        with tempfile.TemporaryDirectory() as tmp:
            page = Path(tmp) / "dashboard.html"
            page.write_text("<html></html>", encoding="utf-8")
            with mock.patch.object(panel_window, "dashboard_path", return_value=page), \
                    mock.patch.object(panel_window, "open_in_browser") as opened, \
                    mock.patch("builtins.__import__", side_effect=fake):
                self.assertEqual(panel_window.run(), 0)
            opened.assert_called_once_with(page)


if __name__ == "__main__":
    unittest.main()
