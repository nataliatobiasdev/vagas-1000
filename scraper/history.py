"""Histórico dia a dia: eventos de mudança (`job_events`) e resumo diário (`day_summary`).

Regras
  * O dia é a DATA (calendário, horário local) do início da extração.
  * Várias extrações no mesmo dia viram um dia só: cada vaga guarda no máximo um evento por (dia, tipo, campo), com o valor
    do começo do dia e o do fim ("mudança líquida"). Voltar ao valor de antes apaga o evento; reabrir uma vaga fechada no
    mesmo dia (ou fechar uma reaberta) se anula.
  * Só se guarda o que mudou. Tipos: `entrou`, `saiu`, `voltou` e `mudou` (com o campo: titulo, local, modalidade, contrato,
    salario, descricao, veredito, nota).
  * O primeiro dia do banco é a LINHA DE BASE: as vagas dele não são "entradas".
  * Fonte que falhou nunca fecha vaga (regra de db.py); o resumo do dia diz quais fontes ficaram sem leitura.
"""
from __future__ import annotations

import json
import logging
import sqlite3
from datetime import date, timedelta

log = logging.getLogger("scraper")

SCHEMA = """
CREATE TABLE IF NOT EXISTS job_events (
  day TEXT NOT NULL, job_key TEXT NOT NULL, kind TEXT NOT NULL, field TEXT NOT NULL DEFAULT '',
  company_id TEXT NOT NULL, old TEXT, new TEXT, verdict TEXT, score REAL,
  first_run_id INTEGER, last_run_id INTEGER, at TEXT NOT NULL,
  PRIMARY KEY (day, job_key, kind, field)
);
CREATE INDEX IF NOT EXISTS ix_events_company ON job_events(company_id, day);
CREATE TABLE IF NOT EXISTS day_summary (
  day TEXT PRIMARY KEY, runs INTEGER DEFAULT 0, last_run_id INTEGER, baseline INTEGER DEFAULT 0,
  open_end INTEGER DEFAULT 0, entered INTEGER DEFAULT 0, exited INTEGER DEFAULT 0, reopened INTEGER DEFAULT 0,
  changed INTEGER DEFAULT 0, eligible_open INTEGER DEFAULT 0, eligible_in INTEGER DEFAULT 0, eligible_out INTEGER DEFAULT 0,
  companies_ok INTEGER DEFAULT 0, companies_total INTEGER DEFAULT 0, failing TEXT DEFAULT '[]',
  unverified_open INTEGER DEFAULT 0, partial INTEGER DEFAULT 0, gap_days INTEGER DEFAULT 0,
  indicators TEXT DEFAULT '{}', computed_at TEXT
);
"""

HISTORY_VERSION = 3                    # PRAGMA user_version a partir do qual o histórico existe
SCORE_DELTA_MIN = 10                   # mudança de nota abaixo disso é ruído, não evento
PROFILE_CHANGE_SHARE = 0.30            # se tantas vagas mudam de veredito numa execução, foi o perfil que mudou, não o mercado

# Campo que estava VAZIO e foi preenchido (o detalhe da vaga foi aberto numa busca seguinte) não é mudança da empresa.
ENRICHMENT_FIELDS = {"local", "modalidade", "contrato"}

# coluna de `jobs` -> nome do campo no evento
FIELDS = {"title": "titulo", "location": "local", "workplace_type": "modalidade", "commitment": "contrato",
          "salary_text": "salario"}


def _s(v) -> str:
    return "" if v is None else str(v)


def day_of(ts: str | None) -> str:
    return (ts or "")[:10]


def _event(conn: sqlite3.Connection, day: str, key: str, cid: str, kind: str, field: str, old, new, run_id: int | None,
           at: str, verdict: str = "", score: float | None = None) -> None:
    """Grava ou atualiza o evento do dia, guardando o valor do começo (`old`) e o do fim (`new`)."""
    row = conn.execute("SELECT old, new FROM job_events WHERE day=? AND job_key=? AND kind=? AND field=?",
                       (day, key, kind, field)).fetchone()
    if row is None:
        conn.execute("INSERT INTO job_events(day,job_key,kind,field,company_id,old,new,verdict,score,first_run_id,"
                     "last_run_id,at) VALUES(?,?,?,?,?,?,?,?,?,?,?,?)",
                     (day, key, kind, field, cid, _s(old), _s(new), verdict, score, run_id, run_id, at))
        return
    if kind == "mudou" and _s(row[0]) == _s(new):              # voltou ao valor do começo do dia: sem mudança líquida
        conn.execute("DELETE FROM job_events WHERE day=? AND job_key=? AND kind=? AND field=?", (day, key, kind, field))
        return
    conn.execute("UPDATE job_events SET new=?, verdict=?, score=?, last_run_id=?, at=? "
                 "WHERE day=? AND job_key=? AND kind=? AND field=?", (_s(new), verdict, score, run_id, at, day, key, kind, field))


def _drop(conn: sqlite3.Connection, day: str, key: str, kind: str) -> bool:
    return conn.execute("DELETE FROM job_events WHERE day=? AND job_key=? AND kind=? AND field=''",
                        (day, key, kind)).rowcount > 0


def _text_len(s) -> str:
    n = len(_s(s))
    return f"{n} caracteres"


def on_job_seen(conn: sqlite3.Connection, day: str, key: str, old: sqlite3.Row | None, v: dict, j, chash: str,
                run_id: int, now: str, baseline: bool, profile_changed: bool) -> None:
    """Registra os eventos de uma vaga vista na extração: entrou, voltou e o que mudou em relação ao que o banco tinha."""
    cid = j.company_id
    if old is None:
        if not baseline:
            _event(conn, day, key, cid, "entrou", "", "", j.title, run_id, now, j.verdict, j.score)
        return
    if old["status"] == "closed" and not _drop(conn, day, key, "saiu"):     # reaberta no mesmo dia que fechou: se anula
        _event(conn, day, key, cid, "voltou", "", old["closed_at"] or "", now, run_id, now, j.verdict, j.score)
    for col, name in FIELDS.items():
        a, b = _s(old[col]), _s(v.get(col))
        if a != b and not (name in ENRICHMENT_FIELDS and not a):
            _event(conn, day, key, cid, "mudou", name, a, b, run_id, now, j.verdict, j.score)
    old_t = old["description_html"] or old["description"]
    if old["content_hash"] and old["content_hash"] != chash and _s(old_t):      # texto que estava vazio e foi preenchido não é reescrita
        text_changed = (_s(old["description_html"]) != _s(v["description_html"]) or _s(old["description"]) != _s(v["description"])
                        or _s(old["sections"] or "[]") != json.dumps(v["sections"], ensure_ascii=False, default=str))
        if text_changed:
            _event(conn, day, key, cid, "mudou", "descricao", _text_len(old_t), _text_len(v["description_html"] or v["description"]),
                   run_id, now, j.verdict, j.score)
    if profile_changed:
        return
    if old["verdict"] and _s(old["verdict"]) != _s(j.verdict):
        _event(conn, day, key, cid, "mudou", "veredito", old["verdict"], j.verdict, run_id, now, j.verdict, j.score)
    if old["score"] is not None and abs((j.score or 0.0) - old["score"]) >= SCORE_DELTA_MIN:
        _event(conn, day, key, cid, "mudou", "nota", round(old["score"]), round(j.score or 0.0), run_id, now, j.verdict, j.score)


def on_job_closed(conn: sqlite3.Connection, day: str, key: str, cid: str, verdict: str, score, run_id: int, now: str) -> None:
    if not _drop(conn, day, key, "voltou"):                    # reaberta e fechada no mesmo dia: sem mudança líquida
        _event(conn, day, key, cid, "saiu", "", "", "", run_id, now, verdict or "", score)


def looks_like_profile_change(conn: sqlite3.Connection, jobs: list) -> bool:
    """Se o perfil (profile.json) mudou, boa parte das vagas muda de veredito de uma vez: isso não é mercado."""
    if len(jobs) < 20:
        return False
    old = {r[0]: r[1] for r in conn.execute("SELECT job_key, verdict FROM jobs WHERE status='open'")}
    from . import db                                           # import tardio: db importa este módulo
    seen = diff = 0
    for j in jobs:
        o = old.get(db.job_key(j))
        if o:
            seen += 1
            diff += o != j.verdict
    return seen >= 20 and diff / seen >= PROFILE_CHANGE_SHARE


# ------------------------------------------------------------------------------------------------- resumo do dia
def first_day(conn: sqlite3.Connection) -> str | None:
    return conn.execute("SELECT MIN(substr(started_at,1,10)) FROM runs").fetchone()[0]


def open_count(conn: sqlite3.Connection, day: str, company_ids: list[str] | None = None) -> int:
    """Vagas abertas no fim de `day`, pelas datas de primeira vez e de encerramento."""
    sql = ("SELECT COUNT(*) FROM jobs WHERE substr(first_seen,1,10) <= ? "
           "AND (closed_at IS NULL OR closed_at='' OR substr(closed_at,1,10) > ?)")
    args: list = [day, day]
    if company_ids is not None:
        if not company_ids:
            return 0
        sql += f" AND company_id IN ({','.join('?' * len(company_ids))})"
        args += company_ids
    return conn.execute(sql, args).fetchone()[0]


def coverage(conn: sqlite3.Connection, day: str) -> tuple[int, int, list[str]]:
    """(fontes ok, fontes lidas, ids das que falharam), pelo ÚLTIMO resultado de cada fonte até o fim de `day`."""
    rows = conn.execute(
        "SELECT rc.company_id, rc.ok FROM run_companies rc WHERE rc.run_id = ("
        "  SELECT MAX(rc2.run_id) FROM run_companies rc2 JOIN runs r2 ON r2.run_id = rc2.run_id "
        "  WHERE rc2.company_id = rc.company_id AND substr(r2.started_at,1,10) <= ?)", (day,)).fetchall()
    failing = sorted({r[0] for r in rows if not r[1]})
    return len(rows) - len(failing), len(rows), failing


def refresh_day(conn: sqlite3.Connection, day: str, cfg: dict | None = None) -> None:
    """Recalcula o resumo de um dia a partir dos eventos (idempotente: reexecutar não conta duas vezes)."""
    runs = conn.execute("SELECT run_id FROM runs WHERE substr(started_at,1,10)=? ORDER BY run_id", (day,)).fetchall()
    if not runs:
        return
    ev = conn.execute("SELECT kind, field, verdict, old, new, job_key FROM job_events WHERE day=?", (day,)).fetchall()
    n = lambda kind: sum(1 for e in ev if e["kind"] == kind)                                   # noqa: E731
    entered, exited, reopened = n("entrou"), n("saiu"), n("voltou")
    changed = len({e["job_key"] for e in ev if e["kind"] == "mudou"})
    elig_in = (sum(1 for e in ev if e["kind"] in ("entrou", "voltou") and e["verdict"] == "ELIGIBLE")
               + sum(1 for e in ev if e["kind"] == "mudou" and e["field"] == "veredito" and e["new"] == "ELIGIBLE"))
    elig_out = (sum(1 for e in ev if e["kind"] == "saiu" and e["verdict"] == "ELIGIBLE")
                + sum(1 for e in ev if e["kind"] == "mudou" and e["field"] == "veredito" and e["old"] == "ELIGIBLE"))
    prev = conn.execute("SELECT * FROM day_summary WHERE day < ? ORDER BY day DESC LIMIT 1", (day,)).fetchone()
    base = day == first_day(conn)
    last_day = conn.execute("SELECT MAX(substr(started_at,1,10)) FROM runs").fetchone()[0]
    if day == last_day:                                         # o último dia confere com o banco (a verdade)
        open_end = conn.execute("SELECT COUNT(*) FROM jobs WHERE status='open'").fetchone()[0]
        eligible_open = conn.execute("SELECT COUNT(*) FROM jobs WHERE status='open' AND verdict='ELIGIBLE'").fetchone()[0]
    elif base or prev is None:
        open_end = open_count(conn, day)
        snap = conn.execute("SELECT COUNT(*), SUM(verdict='ELIGIBLE') FROM job_snapshots WHERE run_id=?", (runs[-1][0],)).fetchone()
        if snap[0]:                                             # banco antigo: o veredito da ÉPOCA está nos snapshots
            eligible_open = snap[1] or 0
        else:
            eligible_open = conn.execute("SELECT COUNT(*) FROM jobs WHERE verdict='ELIGIBLE' AND substr(first_seen,1,10)<=? "
                                         "AND (closed_at IS NULL OR closed_at='' OR substr(closed_at,1,10)>?)", (day, day)).fetchone()[0]
    else:
        open_end = prev["open_end"] + entered - exited + reopened
        eligible_open = prev["eligible_open"] + elig_in - elig_out
    ok, total, failing = coverage(conn, day)
    gap = (date.fromisoformat(day) - date.fromisoformat(prev["day"])).days - 1 if prev else 0
    row = {"day": day, "runs": len(runs), "last_run_id": runs[-1][0], "baseline": int(base), "open_end": open_end,
           "entered": 0 if base else entered, "exited": exited, "reopened": reopened, "changed": changed,
           "eligible_open": eligible_open, "eligible_in": 0 if base else elig_in, "eligible_out": elig_out,
           "companies_ok": ok, "companies_total": total, "failing": json.dumps(failing),
           "unverified_open": open_count(conn, day, failing), "partial": int(bool(failing)), "gap_days": max(gap, 0),
           "indicators": "{}"}
    conn.execute(f"INSERT OR REPLACE INTO day_summary({','.join(row)},computed_at) VALUES({','.join('?' * len(row))},"
                 f"datetime('now','localtime'))", tuple(row.values()))
    try:
        from . import indicators
        ind = indicators.compute(conn, day, row, cfg)
        conn.execute("UPDATE day_summary SET indicators=? WHERE day=?", (json.dumps(ind, ensure_ascii=False), day))
    except Exception:                                           # indicador com defeito nunca derruba a gravação da execução
        log.exception("histórico: falha ao calcular os indicadores de %s", day)


# --------------------------------------------------------------------------------------------- migração (uma vez)
def backfill(conn: sqlite3.Connection) -> int:
    """Reconstrói os eventos dos dias já gravados (banco criado antes do histórico). Só roda com as tabelas vazias.
    Devolve quantos dias foram resumidos. Não altera `jobs`, `job_versions` nem `job_snapshots`."""
    if conn.execute("SELECT COUNT(*) FROM job_events").fetchone()[0] or conn.execute("SELECT COUNT(*) FROM day_summary").fetchone()[0]:
        return 0
    if not conn.execute("SELECT COUNT(*) FROM runs").fetchone()[0]:
        return 0
    base = first_day(conn)
    run_day = {r[0]: day_of(r[1]) for r in conn.execute("SELECT run_id, started_at FROM runs")}
    run_at = {r[0]: r[1] for r in conn.execute("SELECT run_id, started_at FROM runs")}
    for r in conn.execute("SELECT job_key, company_id, title, verdict, score, first_seen, first_run_id, closed_at, closed_run_id FROM jobs"):
        d = day_of(r["first_seen"])
        if d and d != base:
            _event(conn, d, r["job_key"], r["company_id"], "entrou", "", "", r["title"], r["first_run_id"], r["first_seen"], r["verdict"] or "", r["score"])
        if r["closed_at"]:
            _event(conn, day_of(r["closed_at"]), r["job_key"], r["company_id"], "saiu", "", "", "", r["closed_run_id"], r["closed_at"],
                   r["verdict"] or "", r["score"])
    # mudanças de conteúdo: versão a versão (a versão 1 é a primeira vez que a vaga foi vista)
    prev_key, prev = None, None
    for r in conn.execute("SELECT v.job_key, v.run_id, v.seen_at, v.data, j.company_id, j.verdict, j.score FROM job_versions v "
                          "JOIN jobs j ON j.job_key=v.job_key ORDER BY v.job_key, v.version_id"):
        try:
            data = json.loads(r["data"] or "{}")
        except ValueError:
            data = {}
        if r["job_key"] == prev_key and prev is not None:
            d = day_of(r["seen_at"])
            for col, name in FIELDS.items():
                if _s(prev.get(col)) != _s(data.get(col)) and not (name in ENRICHMENT_FIELDS and not _s(prev.get(col))):
                    _event(conn, d, r["job_key"], r["company_id"], "mudou", name, prev.get(col), data.get(col), r["run_id"], r["seen_at"],
                           r["verdict"] or "", r["score"])
            old_t, new_t = prev.get("description_html") or prev.get("description"), data.get("description_html") or data.get("description")
            if _s(old_t) and (_s(old_t) != _s(new_t) or _s(prev.get("sections")) != _s(data.get("sections"))):
                _event(conn, d, r["job_key"], r["company_id"], "mudou", "descricao", _text_len(old_t), _text_len(new_t), r["run_id"],
                       r["seen_at"], r["verdict"] or "", r["score"])
        prev_key, prev = r["job_key"], data
    # veredito e nota: de uma execução para a seguinte (snapshots existentes)
    prev_key, prev = None, None
    for r in conn.execute("SELECT s.job_key, s.run_id, s.verdict, s.score, j.company_id FROM job_snapshots s "
                          "JOIN jobs j ON j.job_key=s.job_key ORDER BY s.job_key, s.run_id"):
        if r["job_key"] == prev_key and prev is not None:
            d, at = run_day.get(r["run_id"], ""), run_at.get(r["run_id"], "")
            if d and prev["verdict"] and r["verdict"] and prev["verdict"] != r["verdict"]:
                _event(conn, d, r["job_key"], r["company_id"], "mudou", "veredito", prev["verdict"], r["verdict"], r["run_id"], at,
                       r["verdict"], r["score"])
            if d and prev["score"] is not None and r["score"] is not None and abs(r["score"] - prev["score"]) >= SCORE_DELTA_MIN:
                _event(conn, d, r["job_key"], r["company_id"], "mudou", "nota", round(prev["score"]), round(r["score"]), r["run_id"], at,
                       r["verdict"] or "", r["score"])
        prev_key, prev = r["job_key"], {"verdict": r["verdict"], "score": r["score"]}
    days = sorted({d for d in run_day.values() if d})
    for d in days:
        refresh_day(conn, d)
    log.info("histórico: %d dia(s) reconstruídos a partir das execuções já gravadas", len(days))
    return len(days)


def previous_day(day: str) -> str:
    return (date.fromisoformat(day) - timedelta(days=1)).isoformat()
