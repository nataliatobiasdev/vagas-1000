"""Erros da busca de vagas que o app instalado encontrou (1.3.0) e a janela que ficava com números velhos."""
import sys
import unittest
import urllib.error
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from scraper import collectors, panel_window, richtext  # noqa: E402


class CleanHtmlTests(unittest.TestCase):
    def test_unknown_tag_inside_a_dropped_tag_does_not_crash(self):
        """Stone: um <path>/<x-foo> dentro de <svg>/<noscript> (removidos) quebrava com 'Cannot replace an element with
        its contents when that element is not part of a tree' e a vaga ficava sem descrição."""
        out = richtext.clean_html('<p>Texto</p><svg><g><path d="1"/></g></svg>'
                                  '<noscript><x-foo>a</x-foo></noscript><custom-tag>fica</custom-tag>')
        self.assertEqual(out, "<p>Texto</p>fica")


class HostCircuitBreakerTests(unittest.TestCase):
    def setUp(self):
        collectors.reset_host_state()
        self.addCleanup(collectors.reset_host_state)
        sleep = mock.patch.object(collectors.time, "sleep")
        sleep.start()
        self.addCleanup(sleep.stop)

    def test_a_host_that_never_answers_is_skipped_after_two_companies(self):
        """A API da Lever ficou fora do ar: cada empresa gastava ~93 s em timeouts (6 min só em 4 empresas)."""
        with mock.patch.object(collectors.urllib.request, "urlopen", side_effect=TimeoutError("lido")) as op:
            for _ in range(collectors.HOST_FAIL_LIMIT):
                with self.assertRaises(TimeoutError):
                    collectors._get_json("https://api.lever.co/v0/postings/a?mode=json")
            calls = op.call_count
            with self.assertRaises(collectors.SourceUnavailable) as cm:
                collectors._get_json("https://api.lever.co/v0/postings/b?mode=json")
            self.assertEqual(op.call_count, calls)                 # nem tentou a rede
            self.assertIn("api.lever.co", str(cm.exception))

    def test_second_company_on_a_failing_host_gets_a_single_attempt(self):
        with mock.patch.object(collectors.urllib.request, "urlopen", side_effect=TimeoutError("lido")) as op:
            with self.assertRaises(TimeoutError):
                collectors._get_json("https://api.lever.co/v0/postings/a")
            first = op.call_count
            with self.assertRaises(TimeoutError):
                collectors._get_json("https://api.lever.co/v0/postings/b")
            self.assertEqual(op.call_count - first, 1)

    def test_other_hosts_are_not_affected(self):
        with mock.patch.object(collectors.urllib.request, "urlopen", side_effect=TimeoutError("lido")):
            for _ in range(collectors.HOST_FAIL_LIMIT):
                with self.assertRaises(TimeoutError):
                    collectors._get_json("https://api.lever.co/v0/postings/a?mode=json")
        resp = mock.MagicMock()
        resp.__enter__.return_value.read.return_value = b'{"ok": true}'
        with mock.patch.object(collectors.urllib.request, "urlopen", return_value=resp):
            self.assertEqual(collectors._get_json("https://boards-api.greenhouse.io/v1/boards/x/jobs"), {"ok": True})

    def test_an_answer_resets_the_failure_count(self):
        ok = mock.MagicMock()
        ok.__enter__.return_value.read.return_value = b"{}"
        with mock.patch.object(collectors.urllib.request, "urlopen", side_effect=TimeoutError("lido")):
            with self.assertRaises(TimeoutError):
                collectors._get_json("https://x.example/a")
        with mock.patch.object(collectors.urllib.request, "urlopen", return_value=ok):
            collectors._get_json("https://x.example/b")
        with mock.patch.object(collectors.urllib.request, "urlopen", side_effect=TimeoutError("lido")):
            with self.assertRaises(TimeoutError):                  # 1 falha de novo (a 1ª foi zerada pela resposta)
                collectors._get_json("https://x.example/c")
        self.assertNotIn("x.example", collectors._HOST_DOWN)       # sem a resposta no meio seriam 2 seguidas: fora do ar

    def test_429_waits_longer_each_attempt_and_respects_retry_after(self):
        def err(retry_after=None):
            hdrs = {"Retry-After": retry_after} if retry_after else {}
            return urllib.error.HTTPError("https://x", 429, "Too Many Requests", hdrs, None)
        self.assertEqual(collectors._retry_wait(err(), 0), 10.0)
        self.assertEqual(collectors._retry_wait(err(), 1), 20.0)
        self.assertEqual(collectors._retry_wait(err("45"), 0), 45.0)
        self.assertEqual(collectors._retry_wait(err("999"), 0), 60.0)               # teto
        self.assertEqual(collectors._retry_wait(TimeoutError("x"), 0), 2.0)

    def test_server_errors_5xx_also_open_the_breaker(self):
        """Durante a queda da Lever (17/11) a API respondia 500/502/504 em ~15 s: o disjuntor só olhava timeout."""
        e = urllib.error.HTTPError("https://x", 504, "Gateway Time-out", {}, None)
        with mock.patch.object(collectors.urllib.request, "urlopen", side_effect=e) as op:
            for _ in range(collectors.HOST_FAIL_LIMIT):
                with self.assertRaises(urllib.error.HTTPError):
                    collectors._get_json("https://api.lever.co/v0/postings/a")
            calls = op.call_count
            with self.assertRaises(collectors.SourceUnavailable):
                collectors._get_json("https://api.lever.co/v0/postings/b")
            self.assertEqual(op.call_count, calls)

    def test_http_errors_do_not_mark_the_host_as_down(self):
        e = urllib.error.HTTPError("https://x", 429, "Too Many Requests", {}, None)
        with mock.patch.object(collectors.urllib.request, "urlopen", side_effect=e):
            for _ in range(collectors.HOST_FAIL_LIMIT + 1):
                with self.assertRaises(urllib.error.HTTPError):
                    collectors._get_json("https://salesforce.wd12.myworkdayjobs.com/a", attempts=1)


class WindowLayoutTests(unittest.TestCase):
    def test_window_has_no_presenciais_button(self):
        app = (ROOT / "app.py").read_text(encoding="utf-8")
        self.assertNotIn("Abrir presenciais", app)
        self.assertNotIn("open_presenciais", app)

    def test_window_has_only_inicio_and_painel_tabs_and_the_panel_keeps_its_own(self):
        app = (ROOT / "app.py").read_text(encoding="utf-8")
        self.assertIn('(("home", "Início"), ("panel", "Painel de vagas"))', app)
        self.assertNotIn('("li", "LinkedIn")', app)                   # a aba do LinkedIn mora dentro do painel
        html = (ROOT / "scraper" / "templates" / "dashboard.html").read_text(encoding="utf-8")
        self.assertIn('id="tabBtnLi"', html)
        self.assertNotIn('[data-embed="1"] .tabs{display:none}', html)  # as abas internas aparecem também dentro do app


class PolishTests(unittest.TestCase):
    """Itens P3 da crítica visual (placeholder, cards encerrados, ordenação por teclado)."""

    def setUp(self):
        self.html = (ROOT / "scraper" / "templates" / "dashboard.html").read_text(encoding="utf-8")

    def test_placeholder_has_an_explicit_color(self):
        self.assertIn("::placeholder{color:var(--ink-3);opacity:1}", self.html)

    def test_closed_cards_fade_only_title_and_tile(self):
        self.assertNotIn(".card.closed{opacity", self.html)           # esmaecer o card todo derrubava o contraste dos metadados
        self.assertIn(".card.closed .c-title,.card.closed .tile{opacity:.6}", self.html)

    def test_sortable_headers_are_keyboard_reachable_and_hint_at_sorting(self):
        self.assertIn('tabindex="0" title="Ordenar por ', self.html)
        self.assertIn('e.target.matches("th[data-k]")', self.html)
        self.assertIn('content:" ↕"', self.html)


class FetchDetailsTests(unittest.TestCase):
    def test_stops_opening_details_after_three_failures_in_a_row(self):
        """Workday respondia 429 em cada detalhe e o app seguia batendo na porta até o fim da lista."""
        jobs = [collectors.Job(company_id="c", company_name="C", source="workday", job_id=f"/j{i}", title="t", url=f"https://x/{i}")
                for i in range(8)]
        fetch = mock.Mock(side_effect=RuntimeError("HTTP Error 429"))
        with mock.patch.object(collectors, "_pause"):
            collectors._fetch_details(jobs, {"company_id": "c"}, fetch, max_new=30, pause=(0, 0), label="Workday")
        self.assertEqual(fetch.call_count, 3)


class PanelAutoReloadTests(unittest.TestCase):
    def test_reloads_only_after_the_file_changed_and_settled(self):
        state = {"mtime": 100.0}
        self.assertFalse(panel_window.mtime_settled(state, 100.0, now=0))        # nada mudou
        self.assertFalse(panel_window.mtime_settled(state, 200.0, now=10))       # mudou agora: espera assentar
        self.assertFalse(panel_window.mtime_settled(state, 200.0, now=11))       # 1 s ainda é pouco
        self.assertTrue(panel_window.mtime_settled(state, 200.0, now=11.6))      # parado há 1,6 s: recarrega

    def test_a_file_still_being_written_restarts_the_wait(self):
        state = {"mtime": 100.0}
        panel_window.mtime_settled(state, 200.0, now=10)
        self.assertFalse(panel_window.mtime_settled(state, 201.0, now=11.7))     # mudou de novo: reinicia
        self.assertTrue(panel_window.mtime_settled(state, 201.0, now=13.3))


class DashboardWriteTests(unittest.TestCase):
    def test_build_replaces_the_file_atomically(self):
        import sqlite3
        import tempfile
        from scraper import dashboard, db
        with tempfile.TemporaryDirectory() as tmp:
            con = sqlite3.connect(":memory:")
            db.init(con) if hasattr(db, "init") else None
            out = Path(tmp) / "dashboard.html"
            out.write_text("antigo", encoding="utf-8")
            with mock.patch.object(dashboard, "collect", return_value={"jobs": [], "runs": [], "companies": [], "records": []}):
                dashboard.build(con, out)
            self.assertIn("<!DOCTYPE html>", out.read_text(encoding="utf-8"))
            self.assertFalse((Path(tmp) / "dashboard.html.tmp").exists())          # o temporário some na troca


if __name__ == "__main__":
    unittest.main()
