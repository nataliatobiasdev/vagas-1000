"""Banco SQLite com histórico das capturas (data/vagas.db).

Tabelas
  companies       empresas monitoradas (de config/companies.json)
  runs            uma linha por execução (totais, novas, encerradas)
  run_companies   resultado por empresa em cada execução (ok, quantidade, erro)
  jobs            a vaga (1 linha por vaga): dados atuais + first_run_id/last_run_id/status
  job_snapshots   nota e veredito da vaga em cada execução (só até a 1.4: hoje o histórico vai em job_events)
  job_events      histórico dia a dia: só o que mudou (entrou, saiu, voltou, mudou + campo), uma linha por (dia, vaga, tipo)
  day_summary     resumo e indicadores de cada data (o dia é a DATA da extração; várias extrações no dia viram um só)
  job_versions    versão completa da vaga (descrição, salário, locais, payload bruto) a cada mudança de conteúdo:
                  mesmo que a fonte edite ou apague a vaga, o que já foi visto continua guardado

Regras
  * Vaga vista na execução  -> status 'open', last_run_id = execução.
  * Vaga NÃO vista, mas a empresa coletou OK com >0 vagas -> status 'closed' (encerrada).
  * Empresa com erro ou com 0 vagas capturadas NUNCA encerra vagas (evita falso "encerrada" por falha de coleta).
  * Nada é apagado: vaga encerrada continua no banco com tudo que foi capturado (`closed_at` marca quando sumiu).
  * Campo que a captura de hoje não trouxe (ex.: detalhe não reaberto) NÃO apaga o que já estava guardado.
"""
from __future__ import annotations

import hashlib
import json
import logging
import shutil
import sqlite3
from datetime import datetime
from pathlib import Path

from . import history, paths
from .models import Job

log = logging.getLogger("scraper")
ROOT = paths.HOME
DEFAULT_DB = paths.DATA / "vagas.db"

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
CREATE TABLE IF NOT EXISTS job_versions (
  version_id INTEGER PRIMARY KEY AUTOINCREMENT, job_key TEXT NOT NULL REFERENCES jobs(job_key),
  run_id INTEGER NOT NULL, seen_at TEXT NOT NULL, content_hash TEXT NOT NULL,
  data TEXT NOT NULL, raw TEXT
);
CREATE INDEX IF NOT EXISTS ix_versions_job ON job_versions(job_key, version_id);
CREATE VIEW IF NOT EXISTS v_open_jobs AS
  SELECT * FROM jobs WHERE status = 'open' ORDER BY
    CASE verdict WHEN 'ELIGIBLE' THEN 0 WHEN 'MAYBE' THEN 1 ELSE 2 END, score DESC;
"""


# Colunas do registro completo (schema 2). Bancos criados antes ganham as colunas na abertura: só acrescenta,
# nunca altera nem apaga o que existe.
JOB_COLUMNS_V2 = {
    "team": "TEXT", "locations": "TEXT", "apply_url": "TEXT", "salary_text": "TEXT", "salary_min": "REAL",
    "salary_max": "REAL", "salary_currency": "TEXT", "salary_period": "TEXT", "posted_at": "TEXT",
    "updated_at_src": "TEXT", "deadline": "TEXT", "requisition_id": "TEXT", "description_html": "TEXT",
    "sections": "TEXT", "metadata": "TEXT", "raw": "TEXT", "content_hash": "TEXT", "detail_at": "TEXT",
    "closed_at": "TEXT", "versions": "INTEGER DEFAULT 0",
}
SCHEMA_VERSION = history.HISTORY_VERSION


def _migrate(conn: sqlite3.Connection) -> None:
    have = {r[1] for r in conn.execute("PRAGMA table_info(jobs)")}
    version = conn.execute("PRAGMA user_version").fetchone()[0]
    with conn:
        for col, typ in JOB_COLUMNS_V2.items():
            if col not in have:
                conn.execute(f"ALTER TABLE jobs ADD COLUMN {col} {typ}")
        # vagas encerradas antes da migração: closed_at = início da execução em que sumiram
        conn.execute("UPDATE jobs SET closed_at=(SELECT started_at FROM runs WHERE runs.run_id=jobs.closed_run_id) "
                     "WHERE status='closed' AND closed_at IS NULL AND closed_run_id IS NOT NULL")
        if version < history.HISTORY_VERSION:               # banco anterior ao histórico: reconstrói os dias já gravados
            history.backfill(conn)
        conn.execute(f"PRAGMA user_version={SCHEMA_VERSION}")


def connect(path: Path | str | None = None) -> sqlite3.Connection:
    path = Path(path) if path else DEFAULT_DB
    path.parent.mkdir(parents=True, exist_ok=True)
    _backup_before_history(path)
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA temp_store=MEMORY")      # ordenações sem arquivo temporário (%TEMP% pode estar bloqueado)
    conn.executescript(SCHEMA)
    conn.executescript(history.SCHEMA)
    _migrate(conn)
    return conn


def _backup_before_history(path: Path) -> None:
    """Banco com dados e anterior ao histórico: guarda uma cópia antes da migração (feita uma vez, nunca sobrescreve)."""
    bak = path.with_name(path.name + ".bak-antes-do-historico")
    if bak.exists() or not path.exists() or path.stat().st_size == 0:
        return
    try:
        c = sqlite3.connect(path)
        try:
            version = c.execute("PRAGMA user_version").fetchone()[0]
            has_jobs = c.execute("SELECT COUNT(*) FROM sqlite_master WHERE name='jobs'").fetchone()[0]
        finally:
            c.close()
        if has_jobs and version < history.HISTORY_VERSION:
            shutil.copy2(path, bak)
            log.info("banco: cópia de segurança antes do histórico em %s", bak.name)
    except (OSError, sqlite3.Error) as e:                   # sem cópia não impede a migração (ela só acrescenta tabelas)
        log.warning("banco: não consegui copiar antes do histórico (%s)", e)


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


def content_hash(j: Job) -> str:
    """Impressão digital do que o usuário lê na vaga: muda quando a fonte edita título, texto, local ou salário."""
    sec = [(s.get("title"), s.get("html")) for s in (j.sections or [])]
    payload = [j.title, j.location, j.locations, j.area, j.team, j.commitment, j.workplace_type, j.description,
               j.description_html, sec, j.salary_text, j.salary_min, j.salary_max]
    return hashlib.sha1(json.dumps(payload, ensure_ascii=False, default=str).encode("utf-8")).hexdigest()


def _loads(s, default):
    try:
        return json.loads(s) if s else default
    except (TypeError, ValueError):
        return default


def _dumps(v) -> str:
    return json.dumps(v, ensure_ascii=False, default=str)


# campos de texto: o que a captura de hoje não trouxe não apaga o que já foi guardado
KEEP_IF_EMPTY = ("description", "description_html", "apply_url", "team", "salary_text", "salary_currency", "salary_period",
                 "posted_at", "deadline", "requisition_id", "commitment", "area", "location")


def _merged(j: Job, old: sqlite3.Row | None) -> dict:
    """Valores a gravar: os de `j`, completados com o que já existia quando `j` veio sem eles."""
    v = {k: getattr(j, k) for k in KEEP_IF_EMPTY}
    v["updated_at_src"] = j.updated_at
    v.update(title=j.title, url=j.url, workplace_type=j.workplace_type, job_id=j.job_id)
    v["salary_min"], v["salary_max"] = j.salary_min, j.salary_max
    v["locations"], v["sections"] = list(j.locations or []), list(j.sections or [])
    v["metadata"], v["raw"] = dict(j.metadata or {}), dict(j.raw or {})
    v["detail_at"] = j.detail_at
    if old is not None:
        for k in KEEP_IF_EMPTY:
            if not v[k]:
                v[k] = old[k] or ""
        if not v["updated_at_src"]:
            v["updated_at_src"] = old["updated_at_src"] or ""
        for k in ("salary_min", "salary_max"):
            if v[k] is None:
                v[k] = old[k]
        for k in ("locations", "sections"):
            if not v[k]:
                v[k] = _loads(old[k], [])
        v["metadata"] = {**_loads(old["metadata"], {}), **v["metadata"]}
        v["raw"] = {**_loads(old["raw"], {}), **v["raw"]}
        v["detail_at"] = v["detail_at"] or old["detail_at"] or ""
    return v


def _upsert_job(conn: sqlite3.Connection, j: Job, run_id: int, now: str, baseline: bool = False,
                profile_changed: bool = False) -> bool:
    """Grava/atualiza uma vaga com o registro completo (e versão, se o conteúdo mudou). True se a vaga é nova."""
    key = job_key(j)
    old = conn.execute("SELECT * FROM jobs WHERE job_key=?", (key,)).fetchone()
    v = _merged(j, old)
    if not v["detail_at"] and (v["description_html"] or v["description"]):
        v["detail_at"] = now
    # o hash usa o conteúdo já mesclado: descrição não reaberta hoje não conta como "mudou"
    merged_job = Job(company_id=j.company_id, company_name=j.company_name, source=j.source, title=j.title,
                     location=v["location"], area=v["area"], commitment=v["commitment"],
                     workplace_type=v["workplace_type"], description=v["description"],
                     description_html=v["description_html"], sections=v["sections"], team=v["team"],
                     locations=v["locations"], salary_text=v["salary_text"], salary_min=v["salary_min"],
                     salary_max=v["salary_max"])
    chash = content_hash(merged_job)
    history.on_job_seen(conn, history.day_of(now), key, old, v, j, chash, run_id, now, baseline, profile_changed)
    cols = (j.company_name, j.source, v["job_id"], v["title"], v["url"], v["location"], v["area"],
            v["workplace_type"], v["commitment"], v["description"], j.score, j.verdict, _dumps(j.techs),
            _dumps(j.reasons), v["team"], _dumps(v["locations"]), v["apply_url"], v["salary_text"],
            v["salary_min"], v["salary_max"], v["salary_currency"], v["salary_period"], v["posted_at"],
            v["updated_at_src"], v["deadline"], v["requisition_id"], v["description_html"],
            _dumps(v["sections"]), _dumps(v["metadata"]), _dumps(v["raw"]), chash, v["detail_at"])
    names = ("company_name,source,job_id,title,url,location,area,workplace_type,commitment,description,score,"
             "verdict,techs,reasons,team,locations,apply_url,salary_text,salary_min,salary_max,salary_currency,"
             "salary_period,posted_at,updated_at_src,deadline,requisition_id,description_html,sections,"
             "metadata,raw,content_hash,detail_at").split(",")
    if old is None:
        conn.execute(
            f"INSERT INTO jobs({','.join(names)},job_key,company_id,first_run_id,last_run_id,first_seen,last_seen,"
            f"status,versions) VALUES({','.join('?' * len(names))},?,?,?,?,?,?,'open',0)",
            cols + (key, j.company_id, run_id, run_id, now, now))
    else:
        conn.execute(
            f"UPDATE jobs SET {','.join(n + '=?' for n in names)},last_run_id=?,last_seen=?,status='open',"
            f"closed_run_id=NULL,closed_at=NULL WHERE job_key=?", cols + (run_id, now, key))
    if old is None or old["content_hash"] != chash:
        data = {k: v[k] for k in ("title", "location", "locations", "area", "team", "commitment",
                                  "workplace_type", "description", "description_html", "sections",
                                  "salary_text", "salary_min", "salary_max", "salary_currency",
                                  "salary_period", "posted_at", "deadline", "requisition_id", "apply_url",
                                  "metadata")}
        conn.execute("INSERT INTO job_versions(job_key,run_id,seen_at,content_hash,data,raw) VALUES(?,?,?,?,?,?)",
                     (key, run_id, now, chash, _dumps(data), _dumps(v["raw"])))
        conn.execute("UPDATE jobs SET versions=versions+1 WHERE job_key=?", (key,))
    return old is None


def save_run(conn: sqlite3.Connection, jobs: list[Job], status: dict[str, dict],
             companies: list[dict] | None = None, started_at: str | None = None) -> int:
    """Grava uma execução inteira numa transação. Devolve o run_id (0 = nada gravado).

    Execução em que TODAS as empresas falharam não é registrada: sem isso o painel mostraria uma
    "execução vazia" como se as vagas tivessem acabado. Os erros ficam no log e no JSON da execução.
    Cada vaga guarda o registro completo; quando o conteúdo muda (texto, salário, local), a versão anterior
    continua em `job_versions`.
    """
    if status and not any(st.get("ok") for st in status.values()):
        log.error("todas as empresas falharam: execução NÃO gravada no banco")
        return 0
    now = started_at or datetime.now().isoformat(timespec="seconds")
    with conn:
        if companies:
            sync_companies(conn, companies)
        run_id = conn.execute("INSERT INTO runs(started_at) VALUES(?)", (now,)).lastrowid
        day = history.day_of(now)
        baseline = day == history.first_day(conn)            # o 1º dia do banco é a linha de base: não conta como "entrou"
        profile_changed = history.looks_like_profile_change(conn, jobs)
        if profile_changed:
            log.info("histórico: o perfil parece ter mudado (muitos vereditos de uma vez): sem eventos de veredito/nota")
        new_count = 0
        for j in jobs:
            if _upsert_job(conn, j, run_id, now, baseline, profile_changed):
                new_count += 1

        closed_count = 0
        for cid, st in status.items():
            conn.execute("INSERT OR REPLACE INTO run_companies(run_id,company_id,ok,job_count,error) VALUES(?,?,?,?,?)",
                         (run_id, cid, 1 if st.get("ok") else 0, st.get("count", 0), st.get("error")))
            if st.get("ok") and st.get("count", 0) > 0:
                gone = conn.execute("SELECT job_key, verdict, score FROM jobs WHERE company_id=? AND status='open' "
                                    "AND last_run_id<>?", (cid, run_id)).fetchall()
                cur = conn.execute("UPDATE jobs SET status='closed', closed_run_id=?, closed_at=? "
                                   "WHERE company_id=? AND status='open' AND last_run_id<>?", (run_id, now, cid, run_id))
                closed_count += cur.rowcount
                for g in gone:
                    history.on_job_closed(conn, day, g["job_key"], cid, g["verdict"], g["score"], run_id, now)
            elif st.get("ok"):
                log.warning("[%s] 0 vagas capturadas: nenhuma vaga anterior foi marcada como encerrada", cid)

        eligible = sum(1 for j in jobs if j.verdict == "ELIGIBLE")
        conn.execute("UPDATE runs SET total=?, eligible=?, new_count=?, closed_count=? WHERE run_id=?",
                     (len(jobs), eligible, new_count, closed_count, run_id))
        try:
            history.refresh_day(conn, day)
        except Exception:                                    # o histórico nunca impede a gravação da execução
            log.exception("histórico: não consegui resumir %s", day)
    log.info("banco: execução %d gravada (%d vagas, %d novas, %d encerradas)", run_id, len(jobs), new_count, closed_count)
    return run_id


def load_details(conn: sqlite3.Connection, company_id: str) -> dict[str, dict]:
    """Detalhes já guardados das vagas de uma empresa (job_key -> campos): evita reabrir páginas de detalhe
    que já temos; o coletor só busca o que é novo ou ficou velho."""
    out: dict[str, dict] = {}
    for r in conn.execute("SELECT job_key, description, description_html, sections, metadata, raw, posted_at, deadline, "
                          "requisition_id, apply_url, commitment, detail_at FROM jobs WHERE company_id=? "
                          "AND (description_html<>'' OR length(description)>400)", (company_id,)):
        raw = _loads(r["raw"], {})
        out[r["job_key"]] = {
            "description": r["description"] or "", "description_html": r["description_html"] or "",
            "sections": _loads(r["sections"], []), "metadata": _loads(r["metadata"], {}),
            "raw_detail": raw.get("detail"), "posted_at": r["posted_at"] or "", "deadline": r["deadline"] or "",
            "requisition_id": r["requisition_id"] or "", "apply_url": r["apply_url"] or "",
            "commitment": r["commitment"] or "", "detail_at": r["detail_at"] or "",
        }
    return out


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
        comps = json.loads(paths.config_file("companies.json").read_text(encoding="utf-8"))["companies"]
        print("run_id", import_json(connect(), sys.argv[2], comps))
    elif len(sys.argv) == 2 and sys.argv[1] == "reavaliar":
        prof = json.loads(paths.config_file("profile.json").read_text(encoding="utf-8"))
        print(rescore_all(connect(), prof), "vagas reavaliadas")
    else:
        print("uso: python -m scraper.db importar out\\vagas-AAAAMMDD-HHMMSS.json | python -m scraper.db reavaliar")


def save_import(conn: sqlite3.Connection, jobs: list[Job], companies: list[dict] | None = None) -> dict:
    """Grava vagas importadas de fora (LinkedIn, planilha). Diferente de `save_run`:

    - não cria "execução" nem encerra vagas: o arquivo é um recorte, não uma varredura inteira;
    - as vagas ficam ligadas à execução mais recente (ou a uma nova, se o banco ainda não tem nenhuma).
    Devolve {"novas": n, "atualizadas": m, "run_id": id}.
    """
    now = datetime.now().isoformat(timespec="seconds")
    with conn:
        if companies:
            sync_companies(conn, companies)
        row = conn.execute("SELECT run_id FROM runs ORDER BY run_id DESC LIMIT 1").fetchone()
        run_id = row[0] if row else conn.execute("INSERT INTO runs(started_at) VALUES(?)", (now,)).lastrowid
        new = sum(1 for j in jobs if _upsert_job(conn, j, run_id, now))
    log.info("banco: %d vagas importadas (%d novas, %d já existiam)", len(jobs), new, len(jobs) - new)
    return {"novas": new, "atualizadas": len(jobs) - new, "run_id": run_id}
