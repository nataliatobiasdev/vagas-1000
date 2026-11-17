"""Histórico dia a dia: eventos líquidos por data, resumo diário, migração e indicadores (etapa 1, sem tela)."""
import json
import sqlite3
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from scraper import db, history, indicators  # noqa: E402
from scraper.models import Job  # noqa: E402

D1, D2, D3, D4 = "2026-11-10", "2026-11-11", "2026-11-12", "2026-11-14"


def J(cid, jid, title=None, verdict="BLOCKED", score=40.0, techs=None, **kw):
    return Job(company_id=cid, company_name=cid.upper(), source="greenhouse", title=title or f"Vaga {cid}{jid}", job_id=str(jid),
               url=f"https://x/{cid}/{jid}", location=kw.pop("location", "Brazil"), verdict=verdict, score=score,
               techs=techs or [], **kw)


def ok(n):
    return {"ok": True, "count": n}


ERR = {"ok": False, "error": "HTTPError: HTTP Error 500"}
COMPANIES = [{"company_id": c, "name": c.upper(), "adapter": "greenhouse_api", "board_url": f"https://x/{c}"} for c in ("a", "b", "c")]


class HistoryBase(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.path = Path(self.tmp.name) / "t.db"
        self.conn = db.connect(self.path)
        self.addCleanup(self.conn.close)

    def run_at(self, day, hhmm, jobs, status):
        return db.save_run(self.conn, jobs, status, COMPANIES, f"{day}T{hhmm}:00")

    def events(self, day=None):
        sql = "SELECT day, job_key, kind, field, old, new FROM job_events" + (" WHERE day=?" if day else "") + " ORDER BY day, job_key, kind, field"
        return [tuple(r) for r in self.conn.execute(sql, (day,) if day else ())]

    def summary(self, day):
        return dict(self.conn.execute("SELECT * FROM day_summary WHERE day=?", (day,)).fetchone())


class DayRulesTests(HistoryBase):
    def test_first_day_is_the_baseline_and_has_no_entries(self):
        self.run_at(D1, "08:00", [J("a", 1), J("a", 2)], {"a": ok(2)})
        s = self.summary(D1)
        self.assertEqual((s["baseline"], s["entered"], s["open_end"]), (1, 0, 2))
        self.assertEqual(self.events(D1), [])

    def test_next_day_checks_what_still_exists_and_notes_the_changes(self):
        self.run_at(D1, "08:00", [J("a", 1), J("a", 2), J("a", 3)], {"a": ok(3)})
        self.run_at(D2, "08:00", [J("a", 1, title="Vaga a1 (Sênior)"), J("a", 3), J("a", 4)], {"a": ok(3)})
        self.assertEqual(self.events(D2), [(D2, "a:1", "mudou", "titulo", "Vaga a1", "Vaga a1 (Sênior)"),
                                           (D2, "a:2", "saiu", "", "", ""), (D2, "a:4", "entrou", "", "", "Vaga a4")])
        s = self.summary(D2)
        self.assertEqual((s["baseline"], s["entered"], s["exited"], s["changed"], s["open_end"]), (0, 1, 1, 1, 3))

    def test_several_runs_in_one_day_keep_only_the_net_change(self):
        self.run_at(D1, "08:00", [J("a", 1, score=40), J("a", 2)], {"a": ok(2)})
        self.run_at(D2, "06:00", [J("a", 1, title="B"), J("a", 2)], {"a": ok(2)})          # muda o título
        self.run_at(D2, "12:00", [J("a", 1, title="C"), J("a", 2)], {"a": ok(2)})          # muda de novo no mesmo dia
        self.run_at(D2, "18:00", [J("a", 1, title="Vaga a1"), J("a", 2)], {"a": ok(2)})    # e volta ao original
        self.assertEqual(self.events(D2), [])                                              # sem mudança líquida: nada a anotar
        self.run_at(D3, "08:00", [J("a", 1, title="B"), J("a", 2)], {"a": ok(2)})
        self.run_at(D3, "09:00", [J("a", 1, title="C"), J("a", 2)], {"a": ok(2)})
        self.assertEqual(self.events(D3), [(D3, "a:1", "mudou", "titulo", "Vaga a1", "C")])  # começo do dia -> fim do dia
        self.assertEqual(self.summary(D3)["runs"], 2)

    def test_closed_and_reopened_on_the_same_day_cancel_out(self):
        self.run_at(D1, "08:00", [J("a", 1), J("a", 2)], {"a": ok(2)})
        self.run_at(D2, "08:00", [J("a", 2)], {"a": ok(1)})                                # a:1 some
        self.assertEqual([e[2] for e in self.events(D2)], ["saiu"])
        self.run_at(D2, "14:00", [J("a", 1), J("a", 2)], {"a": ok(2)})                     # e volta no mesmo dia
        self.assertEqual(self.events(D2), [])
        self.assertEqual(self.summary(D2)["open_end"], 2)

    def test_a_job_that_opens_and_closes_in_the_same_day_keeps_both_events(self):
        self.run_at(D1, "08:00", [J("a", 1)], {"a": ok(1)})
        self.run_at(D2, "08:00", [J("a", 1), J("a", 9)], {"a": ok(2)})
        self.run_at(D2, "20:00", [J("a", 1)], {"a": ok(1)})
        self.assertEqual([(e[1], e[2]) for e in self.events(D2)], [("a:9", "entrou"), ("a:9", "saiu")])   # vaga relâmpago
        s = self.summary(D2)
        self.assertEqual((s["entered"], s["exited"], s["open_end"]), (1, 1, 1))

    def test_job_reopened_on_a_later_day_is_recorded_as_returned(self):
        self.run_at(D1, "08:00", [J("a", 1), J("a", 2)], {"a": ok(2)})
        self.run_at(D2, "08:00", [J("a", 2)], {"a": ok(1)})
        self.run_at(D3, "08:00", [J("a", 1), J("a", 2)], {"a": ok(2)})
        self.assertEqual([e[2] for e in self.events(D3)], ["voltou"])
        self.assertEqual(self.summary(D3)["reopened"], 1)
        self.assertEqual(self.summary(D3)["open_end"], 2)

    def test_failed_source_closes_nothing_and_the_day_is_marked_partial(self):
        self.run_at(D1, "08:00", [J("a", 1), J("b", 1)], {"a": ok(1), "b": ok(1)})
        self.run_at(D2, "08:00", [J("a", 1)], {"a": ok(1), "b": ERR})
        self.assertEqual(self.events(D2), [])                                              # b:1 não "saiu": a fonte falhou
        s = self.summary(D2)
        self.assertEqual((s["partial"], json.loads(s["failing"]), s["companies_ok"], s["companies_total"]), (1, ["b"], 1, 2))
        self.assertEqual((s["open_end"], s["unverified_open"]), (2, 1))                    # a vaga de b segue guardada, não verificada

    def test_days_without_any_extraction_are_counted_as_a_gap(self):
        self.run_at(D1, "08:00", [J("a", 1)], {"a": ok(1)})
        self.run_at(D4, "08:00", [J("a", 1), J("a", 2)], {"a": ok(2)})                     # 11, 12 e 13 sem extração
        s = self.summary(D4)
        self.assertEqual((s["gap_days"], s["entered"]), (3, 1))                            # a mudança vai para o dia seguinte

    def test_refreshing_a_day_twice_does_not_double_count(self):
        self.run_at(D1, "08:00", [J("a", 1), J("a", 2)], {"a": ok(2)})
        self.run_at(D2, "08:00", [J("a", 1)], {"a": ok(1)})
        before = self.summary(D2)
        history.refresh_day(self.conn, D2)
        history.refresh_day(self.conn, D2)
        after = self.summary(D2)
        for k in ("entered", "exited", "changed", "open_end", "eligible_open", "runs"):
            self.assertEqual(before[k], after[k], k)

    def test_verdict_and_big_score_changes_are_events_small_ones_are_not(self):
        self.run_at(D1, "08:00", [J("a", 1, verdict="MAYBE", score=60), J("a", 2, score=40)], {"a": ok(2)})
        self.run_at(D2, "08:00", [J("a", 1, verdict="ELIGIBLE", score=80), J("a", 2, score=44)], {"a": ok(2)})
        got = {(e[1], e[3]): (e[4], e[5]) for e in self.events(D2)}
        self.assertEqual(got, {("a:1", "veredito"): ("MAYBE", "ELIGIBLE"), ("a:1", "nota"): ("60", "80")})   # a:2 (+4) é ruído
        s = self.summary(D2)
        self.assertEqual((s["eligible_in"], s["eligible_out"], s["eligible_open"]), (1, 0, 1))

    def test_a_profile_change_is_not_market_news(self):
        """Se o profile.json muda, quase todas as vagas trocam de veredito de uma vez: não vira evento."""
        many = [J("a", i, verdict="BLOCKED") for i in range(30)]
        self.run_at(D1, "08:00", many, {"a": ok(30)})
        self.run_at(D2, "08:00", [J("a", i, verdict="ELIGIBLE", score=90) for i in range(30)], {"a": ok(30)})
        self.assertEqual([e for e in self.events(D2) if e[3] in ("veredito", "nota")], [])

    def test_baseline_means_the_whole_first_day_not_only_the_first_run(self):
        self.run_at(D1, "08:00", [J("a", 1)], {"a": ok(1)})
        self.run_at(D1, "16:00", [J("a", 1), J("a", 2)], {"a": ok(2)})
        self.assertEqual(self.events(D1), [])
        self.assertEqual(self.summary(D1)["open_end"], 2)


class NoiseTests(HistoryBase):
    def test_fields_filled_in_later_are_not_changes_but_a_salary_appearing_is(self):
        """O detalhe da vaga é aberto numa busca seguinte: contrato/modalidade/texto que estavam vazios e foram preenchidos não são
        mudança da empresa (dava 12 'reescritas' e 10 'mudou de contrato' num dia sem nada de novo). Salário que aparece é."""
        self.run_at(D1, "08:00", [J("a", 1), J("a", 2)], {"a": ok(2)})
        self.run_at(D2, "08:00", [J("a", 1, commitment="Full time", workplace_type="remote", description_html="<p>Texto novo</p>"),
                                  J("a", 2, salary_text="R$ 10 mil")], {"a": ok(2)})
        got = {(e[1], e[3]) for e in self.events(D2)}
        self.assertEqual(got, {("a:2", "salario")})
        self.run_at(D3, "08:00", [J("a", 1, commitment="Part time", workplace_type="remote", description_html="<p>Texto reescrito</p>"),
                                  J("a", 2, salary_text="R$ 10 mil")], {"a": ok(2)})
        self.assertEqual({(e[1], e[3]) for e in self.events(D3)}, {("a:1", "contrato"), ("a:1", "descricao")})   # valor -> outro valor: mudança

    def test_flash_jobs_ignore_jobs_that_already_existed_on_the_baseline_day(self):
        self.run_at(D1, "08:00", [J("a", 1), J("a", 2)], {"a": ok(2)})
        self.run_at(D2, "08:00", [J("a", 1)], {"a": ok(1)})                                 # a:2 saiu, mas já estava aqui no dia 1
        ids = [m["id"] for m in json.loads(self.summary(D2)["indicators"])["modules"]]
        self.assertNotIn("relampago", ids)


class BackfillTests(HistoryBase):
    def test_a_database_from_before_the_history_is_rebuilt_and_backed_up(self):
        """Banco 1.4 (sem eventos, com job_snapshots): a migração reconstrói os dias e guarda uma cópia antes."""
        self.run_at(D1, "08:00", [J("a", 1, score=50, verdict="MAYBE"), J("a", 2), J("b", 1)], {"a": ok(2), "b": ok(1)})
        self.run_at(D2, "08:00", [J("a", 1, title="Vaga a1 (Sênior)", score=90, verdict="ELIGIBLE"), J("a", 3), J("b", 1)],
                    {"a": ok(2), "b": ok(1)})
        live = {d: self.summary(d) for d in (D1, D2)}
        live_events = self.events()
        # simula o banco antigo: sem eventos nem resumo, versão 2, com snapshots por execução
        self.conn.executescript("DELETE FROM job_events; DELETE FROM day_summary; PRAGMA user_version=2;")
        self.conn.execute("DELETE FROM job_snapshots")
        for run_id, rows in ((1, [("a:1", 50, "MAYBE"), ("a:2", 40, "BLOCKED"), ("b:1", 40, "BLOCKED")]),
                             (2, [("a:1", 90, "ELIGIBLE"), ("a:3", 40, "BLOCKED"), ("b:1", 40, "BLOCKED")])):
            for key, score, verdict in rows:
                self.conn.execute("INSERT INTO job_snapshots(run_id,job_key,score,verdict) VALUES(?,?,?,?)", (run_id, key, score, verdict))
        self.conn.commit()
        self.conn.close()
        conn = db.connect(self.path)
        self.addCleanup(conn.close)
        self.assertTrue((self.path.with_name("t.db.bak-antes-do-historico")).exists())      # cópia de segurança antes da migração
        got = [tuple(r) for r in conn.execute("SELECT day, job_key, kind, field, old, new FROM job_events ORDER BY day, job_key, kind, field")]
        self.assertEqual(sorted(got), sorted(live_events))                                  # mesmos eventos que ao vivo
        for d in (D1, D2):
            row = dict(conn.execute("SELECT * FROM day_summary WHERE day=?", (d,)).fetchone())
            for k in ("baseline", "entered", "exited", "changed", "open_end", "eligible_in", "eligible_out", "eligible_open", "runs"):
                self.assertEqual(row[k], live[d][k], f"{d} {k}")
        self.assertEqual(conn.execute("PRAGMA user_version").fetchone()[0], history.HISTORY_VERSION)
        self.assertEqual(history.backfill(conn), 0)                                         # rodar de novo não duplica nada


class IndicatorTests(HistoryBase):
    def cfg(self, **mods):
        return {"modulos": {k: v for k, v in mods.items()}}

    def test_fixed_block_always_has_the_core_numbers(self):
        self.run_at(D1, "08:00", [J("a", 1)], {"a": ok(1)})
        self.run_at(D2, "08:00", [J("a", 1), J("a", 2)], {"a": ok(2)})
        ind = json.loads(self.summary(D2)["indicators"])
        fixed = {i["id"]: i for i in ind["fixed"]}
        self.assertEqual([k for k in fixed], ["abertas", "entraram", "sairam", "mudaram", "elegiveis", "cobertura"])
        self.assertEqual((fixed["abertas"]["value"], fixed["entraram"]["value"]), (2, 1))
        self.assertIn("+1", fixed["abertas"]["detail"])

    def test_company_with_big_movement_shows_up_only_above_the_thresholds(self):
        first = [J("a", i) for i in range(20)] + [J("b", i) for i in range(20)]
        self.run_at(D1, "08:00", first, {"a": ok(20), "b": ok(20), "c": ok(1)})
        second = [J("a", i) for i in range(20)] + [J("b", i) for i in range(20)] + [J("b", 100 + i) for i in range(6)]    # b: +6 (23%)
        self.run_at(D2, "08:00", second, {"a": ok(20), "b": ok(26), "c": ok(0)})
        mods = {m["id"]: m for m in json.loads(self.summary(D2)["indicators"])["modules"]}
        self.assertIn("movimento:b", mods)
        self.assertEqual(mods["movimento:b"]["value"], 6)
        self.assertNotIn("movimento:a", mods)

    def test_new_eligible_jobs_module_points_to_the_best_one(self):
        self.run_at(D1, "08:00", [J("a", 1)], {"a": ok(1)})
        self.run_at(D2, "08:00", [J("a", 1), J("a", 2, verdict="ELIGIBLE", score=95, techs=["PYTHON"]),
                                  J("a", 3, verdict="ELIGIBLE", score=70)], {"a": ok(3)})
        m = {m["id"]: m for m in json.loads(self.summary(D2)["indicators"])["modules"]}["elegiveis_novas"]
        self.assertEqual(m["value"], 2)
        self.assertEqual(m["jobs"][0], "a:2")
        self.assertIn("95", m["detail"])
        self.assertEqual(m["tone"], "good")

    def test_anomaly_needs_history_and_flags_a_spike_of_exits(self):
        jobs = [J("a", i) for i in range(40)]
        self.run_at("2026-11-01", "08:00", jobs, {"a": ok(40)})
        for n, d in enumerate(("2026-11-02", "2026-11-03", "2026-11-04", "2026-11-05"), start=1):
            self.run_at(d, "08:00", jobs[: 40 - n], {"a": ok(40 - n)})                      # 1 saída por dia
        self.run_at("2026-11-06", "08:00", jobs[:25], {"a": ok(25)})                        # 10 saídas de uma vez
        ids = [m["id"] for m in json.loads(self.summary("2026-11-06")["indicators"])["modules"]]
        self.assertIn("anomalia:exited", ids)
        self.assertNotIn("anomalia:exited", [m["id"] for m in json.loads(self.summary("2026-11-05")["indicators"])["modules"]])

    def test_source_without_reading_for_consecutive_days_is_flagged(self):
        self.run_at(D1, "08:00", [J("a", 1), J("b", 1)], {"a": ok(1), "b": ok(1)})
        self.run_at(D2, "08:00", [J("a", 1)], {"a": ok(1), "b": ERR})
        self.assertNotIn("sem_leitura:b", [m["id"] for m in json.loads(self.summary(D2)["indicators"])["modules"]])   # 1º dia: só cobertura
        self.run_at(D3, "08:00", [J("a", 1)], {"a": ok(1), "b": ERR})
        m = {m["id"]: m for m in json.loads(self.summary(D3)["indicators"])["modules"]}["sem_leitura:b"]
        self.assertEqual((m["value"], m["tone"]), (2, "warn"))

    def test_source_that_answers_zero_jobs_and_company_that_starts_hiring_are_reported(self):
        self.run_at(D1, "08:00", [J("a", 1), J("b", 1), J("b", 2)], {"a": ok(1), "b": ok(2), "c": ok(0)})
        self.run_at(D2, "08:00", [J("a", 1), J("c", 1), J("c", 2)], {"a": ok(1), "b": ok(0), "c": ok(2)})   # b devolve 0; c começa
        mods = {m["id"]: m for m in json.loads(self.summary(D2)["indicators"])["modules"]}
        self.assertEqual(mods["zerou:b"]["tone"], "warn")
        self.assertIn("2 vagas abertas continuam guardadas", mods["zerou:b"]["detail"])
        self.assertEqual(mods["comecou:c"]["value"], 2)
        self.assertEqual(self.events(D2)[0][1], "c:1")                                       # b não fechou nada (0 vagas é suspeito)
        self.assertNotIn("zerou:a", mods)

    def test_modules_can_be_turned_off_and_the_card_shows_only_the_top_ones(self):
        self.run_at(D1, "08:00", [J("a", 1)], {"a": ok(1)})
        self.run_at(D2, "08:00", [J("a", 1), J("a", 2, verdict="ELIGIBLE", score=95)], {"a": ok(2)})
        ind = json.loads(self.summary(D2)["indicators"])
        self.assertTrue(any(m["id"] == "elegiveis_novas" for m in ind["modules"]))
        off = indicators.compute(self.conn, D2, self.summary(D2), self.cfg(elegiveis_novas={"ativo": False}))
        self.assertFalse(any(m["id"] == "elegiveis_novas" for m in off["modules"]))
        fake = {"modules": [{"id": f"m{i}", "relevance": 0.9 - i * 0.1} for i in range(8)]}
        picked = indicators.select(fake, {"max_modulos_no_card": 3, "relevancia_minima": 0.4})
        self.assertEqual([m["id"] for m in picked], ["m0", "m1", "m2"])
        picked = indicators.select(fake, {"max_modulos_no_card": 9, "relevancia_minima": 0.7})
        self.assertEqual([m["id"] for m in picked], ["m0", "m1", "m2"])                      # só os acima do mínimo

    def test_a_broken_module_does_not_break_the_others_or_the_run(self):
        original = indicators.MODULES["salario"]
        indicators.MODULES["salario"] = lambda c, mc: 1 / 0
        self.addCleanup(lambda: indicators.MODULES.__setitem__("salario", original))
        self.run_at(D1, "08:00", [J("a", 1)], {"a": ok(1)})
        self.run_at(D2, "08:00", [J("a", 1), J("a", 2, verdict="ELIGIBLE", score=95)], {"a": ok(2)})
        ids = [m["id"] for m in json.loads(self.summary(D2)["indicators"])["modules"]]
        self.assertIn("elegiveis_novas", ids)

    def test_config_file_defaults_are_complete_and_user_values_win(self):
        cfg = indicators.load_config({"modulos": {"movimento_empresa": {"min_eventos": 9}}})
        self.assertEqual(cfg["modulos"]["movimento_empresa"], {"ativo": True, "min_eventos": 9, "min_parcela": 0.10})
        self.assertEqual(set(cfg["modulos"]), set(indicators.MODULES))                      # todo módulo tem configuração
        shipped = json.loads((ROOT / "config" / "historico.json").read_text(encoding="utf-8"))
        self.assertEqual(set(shipped["modulos"]), set(indicators.MODULES))


if __name__ == "__main__":
    unittest.main()
