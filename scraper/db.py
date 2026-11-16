"""Banco SQLite com histórico das capturas (data/vagas.db).

Tabelas
  companies       empresas monitoradas (de config/companies.json)
  runs            uma linha por execução (totais, novas, encerradas)
  run_companies   resultado por empresa em cada execução (ok, quantidade, erro)
  jobs            a vaga (1 linha por vaga): dados atuais + first_run_id/last_run_id/status
  job_snapshots   nota e veredito da vaga em cada execução (histórico de mudanças)

Regras
  * Vaga vista na execução  -> status 'open', last_run_id = execução.
  * Vaga NÃO vista, mas a empresa coletou OK com >0 vagas -> status 'closed' (encerrada).
  * Empresa com erro ou com 0 vagas capturadas NUNCA encerra vagas (evita falso "encerrada" por falha de coleta).
"""
from __future__ import annotations

import hashlib
import json
import logging
import sqlite3
from datetime import datetime
from pathlib import Path

from .models import Job

log = logging.getLogger("scraper")
ROOT = Path(__file__).resolve().parent.parent
DEFAULT_DB = ROOT / "data" / "vagas.db"

SCHEMA = """
PRAGMA foreign_keys = ON;
CREATE TABLE IF NOT EXISTS companies (
  company_id TEXT PRIMARY KEY, name TEXT NOT NULL, adapter TEXT, board_url TEXT,
  access_code TEXT, composite_score REAL
);
CREATE TABLE IF NOT EXISTS runs (
  run_id INTEGER PRIMARY KEY AUTOINCREMENT, started_at TEXT NOT NULL,
  total INTEGER DEFAULT 0, eligible INTEGER DEFAULT 0, new_count INTEGER DEFAULT 0, closed_count INTEGER DEFAULT 0
);
CREATE TABLE IF NOT EXISTS run_companies (
  run_id INTEGER NOT NULL REFERENCES runs(run_id), company_id TEXT NOT NULL,
  ok INTEGER NOT NULL, job_count INTEGER DEFAULT 0, error TEXT,
  PRIMARY KEY (run_id, company_id)
);
CREATE TABLE IF NOT EXISTS jobs (
  job_key TEXT PRIMARY KEY, company_id TEXT NOT NULL, company_name TEXT, source TEXT,
  job_id TEXT, title TEXT, url TEXT, location TEXT, area TEXT, workplace_type TEXT, commitment TEXT,
  description TEXT, score REAL, verdict TEXT, techs TEXT, reasons TEXT,
  first_run_id INTEGER NOT NULL, last_run_id INTEGER NOT NULL,
  first_seen TEXT NOT NULL, last_seen TEXT NOT NULL,
  status TEXT NOT NULL DEFAULT 'open', closed_run_id INTEGER
);
CREATE INDEX IF NOT EXISTS ix_jobs_company ON jobs(company_id, status);
CREATE TABLE IF NOT EXISTS job_snapshots (
  run_id INTEGER NOT NULL REFERENCES runs(run_id), job_key TEXT NOT NULL REFERENCES jobs(job_key),
  score REAL, verdict TEXT, title TEXT, location TEXT,
  PRIMARY KEY (run_id, job_key)
);
CREATE VIEW IF NOT EXISTS v_open_jobs AS
  SELECT * FROM jobs WHERE status = 'open' ORDER BY
    CASE verdict WHEN 'ELIGIBLE' THEN 0 WHEN 'MAYBE' THEN 1 ELSE 2 END, score DESC;
"""


def connect(path: Path | str | None = None) -> sqlite3.Connection:
    path = Path(path) if path else DEFAULT_DB
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    conn.executescript(SCHEMA)
    return conn


def job_key(j: Job) -> str:
    ident = j.job_id or hashlib.sha1((j.url or f"{j.title}|{j.location}").encode("utf-8")).hexdigest()[:12]
    return f"{j.company_id}:{ident}"


def sync_companies(conn: sqlite3.Connection, companies: list[dict]) -> None:
    for c in companies:
        conn.execute(
            "INSERT INTO companies(company_id,name,adapter,board_url,access_code,composite_score) VALUES(?,?,?,?,?,?) "
            "ON CONFLICT(company_id) DO UPDATE SET name=excluded.name, adapter=excluded.adapter, "
            "board_url=excluded.board_url, access_code=excluded.access_code, composite_score=excluded.composite_score",
            (c["company_id"], c["name"], c.get("adapter"), c.get("board_url"), c.get("access_code"), c.get("composite_score")))


def save_run(conn: sqlite3.Connection, jobs: list[Job], status: dict[str, dict],
             companies: list[dict] | None = None, started_at: str | None = None) -> int:
    """Grava uma execução inteira numa transação. Devolve o run_id (0 = nada gravado).

    Execução em que TODAS as empresas falharam não é registrada: sem isso o painel mostraria uma
    "execução vazia" como se as vagas tivessem acabado. Os erros ficam no log e no JSON da execução.
    """
    if status and not any(st.get("ok") for st in status.values()):
        log.error("todas as empresas falharam: execução NÃO gravada no banco")
        return 0
    now = started_at or datetime.now().isoformat(timespec="seconds")
    with conn:
        if companies:
            sync_companies(conn, companies)
        run_id = conn.execute("INSERT INTO runs(started_at) VALUES(?)", (now,)).lastrowid
        new_count = 0
        for j in jobs:
            key = job_key(j)
            row = conn.execute("SELECT job_key FROM jobs WHERE job_key=?", (key,)).fetchone()
            vals = (j.company_name, j.source, j.job_id, j.title, j.url, j.location, j.area, j.workplace_type,
                    j.commitment, j.description, j.score, j.verdict, json.dumps(j.techs), json.dumps(j.reasons, ensure_ascii=False))
            if row is None:
                new_count += 1
                conn.execute(
                    "INSERT INTO jobs(company_name,source,job_id,title,url,location,area,workplace_type,commitment,description,"
                    "score,verdict,techs,reasons,job_key,company_id,first_run_id,last_run_id,first_seen,last_seen,status) "
                    "VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,'open')",
                    vals + (key, j.company_id, run_id, run_id, now, now))
            else:
                conn.execute(
                    "UPDATE jobs SET company_name=?,source=?,job_id=?,title=?,url=?,location=?,area=?,workplace_type=?,commitment=?,"
                    "description=?,score=?,verdict=?,techs=?,reasons=?,last_run_id=?,last_seen=?,status='open',closed_run_id=NULL "
                    "WHERE job_key=?", vals + (run_id, now, key))
            conn.execute("INSERT OR REPLACE INTO job_snapshots(run_id,job_key,score,verdict,title,location) VALUES(?,?,?,?,?,?)",
                         (run_id, key, j.score, j.verdict, j.title, j.location))

        closed_count = 0
        for cid, st in status.items():
            conn.execute("INSERT OR REPLACE INTO run_companies(run_id,company_id,ok,job_count,error) VALUES(?,?,?,?,?)",
                         (run_id, cid, 1 if st.get("ok") else 0, st.get("count", 0), st.get("error")))
            if st.get("ok") and st.get("count", 0) > 0:
                cur = conn.execute("UPDATE jobs SET status='closed', closed_run_id=? "
                                   "WHERE company_id=? AND status='open' AND last_run_id<>?", (run_id, cid, run_id))
                closed_count += cur.rowcount
            elif st.get("ok"):
                log.warning("[%s] 0 vagas capturadas: nenhuma vaga anterior foi marcada como encerrada", cid)

        eligible = sum(1 for j in jobs if j.verdict == "ELIGIBLE")
        conn.execute("UPDATE runs SET total=?, eligible=?, new_count=?, closed_count=? WHERE run_id=?",
                     (len(jobs), eligible, new_count, closed_count, run_id))
    log.info("banco: execução %d gravada (%d vagas, %d novas, %d encerradas)", run_id, len(jobs), new_count, closed_count)
    return run_id


def import_json(conn: sqlite3.Connection, path: Path | str, companies: list[dict] | None = None) -> int:
    """Importa um vagas-*.json já gerado (útil para semear o banco com execuções anteriores)."""
    d = json.loads(Path(path).read_text(encoding="utf-8"))
    fields = Job.__dataclass_fields__.keys()
    jobs = [Job(**{k: v for k, v in j.items() if k in fields}) for j in d["jobs"]]
    return save_run(conn, jobs, d.get("status", {}), companies, started_at=d.get("generated_at"))


def rescore_all(conn: sqlite3.Connection, profile: dict) -> int:
    """Reavalia todas as vagas do banco com o profile.json atual (use depois de ajustar pesos/termos)."""
    from .filtering import score_job
    n = 0
    with conn:
        for r in conn.execute("SELECT * FROM jobs").fetchall():
            j = Job(company_id=r["company_id"], company_name=r["company_name"], source=r["source"], title=r["title"],
                    url=r["url"], location=r["location"], area=r["area"], workplace_type=r["workplace_type"],
                    commitment=r["commitment"], description=r["description"], job_id=r["job_id"])
            score_job(j, profile)
            conn.execute("UPDATE jobs SET score=?, verdict=?, techs=?, reasons=? WHERE job_key=?",
                         (j.score, j.verdict, json.dumps(j.techs), json.dumps(j.reasons, ensure_ascii=False), r["job_key"]))
            n += 1
    return n


if __name__ == "__main__":      # python -m scraper.db importar out/vagas-xxx.json
    import sys
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    if len(sys.argv) == 3 and sys.argv[1] == "importar":
        comps = json.loads((ROOT / "config" / "companies.json").read_text(encoding="utf-8"))["companies"]
        print("run_id", import_json(connect(), sys.argv[2], comps))
    elif len(sys.argv) == 2 and sys.argv[1] == "reavaliar":
        prof = json.loads((ROOT / "config" / "profile.json").read_text(encoding="utf-8"))
        print(rescore_all(connect(), prof), "vagas reavaliadas")
    else:
        print("uso: python -m scraper.db importar out\\vagas-AAAAMMDD-HHMMSS.json | python -m scraper.db reavaliar")
