from __future__ import annotations

import csv
import json
import logging
import time
import urllib.error
from datetime import datetime
from pathlib import Path

from . import dashboard, db, paths
from .collectors import COLLECTORS, reset_host_state
from .driver import quit_driver, session_alive
from .filtering import score_job
from .models import Job

log = logging.getLogger("scraper")
ROOT = paths.HOME
NEEDS_BROWSER = {"stone_portal", "lever", "greenhouse"}   # adaptadores que dependem do Chrome
DETAIL_CACHED = {"gupy", "workday", "gft"}                # adaptadores que reabrem 1 página por vaga


def _known_details(company_id: str) -> dict:
    """Detalhes já gravados das vagas da empresa (vazio se o banco não existe ou falha: nunca derruba a coleta)."""
    try:
        conn = db.connect()
        try:
            return db.load_details(conn, company_id)
        finally:
            conn.close()
    except Exception as e:
        log.warning("[%s] sem cache de detalhes (%s): vai reabrir as páginas", company_id, e)
        return {}

CSV_FIELDS = ["company_name", "title", "verdict", "score", "location", "workplace_type", "area",
              "techs", "url", "source", "captured_at", "reasons"]


def load_json(p: Path) -> dict:
    return json.loads(p.read_text(encoding="utf-8"))


def source_error_message(err: Exception) -> str:
    if isinstance(err, urllib.error.HTTPError):
        if err.code == 403:
            return 'HTTP 403: o portal recusou o acesso. Vagas anteriores preservadas; tente novamente mais tarde.'
        if err.code == 429:
            retry_after = err.headers.get('Retry-After') if err.headers else None
            wait = f' O servidor informou Retry-After: {retry_after}.' if retry_after else ''
            return f'HTTP 429: o portal limitou as consultas.{wait} Vagas anteriores preservadas; tente novamente mais tarde.'
    return f'{type(err).__name__}: {err}'


def collect_one(collector, driver, cfg: dict, driver_factory=None, retries: int = 1):
    """Executa o coletor de UMA empresa. Se a sessão do navegador morrer no meio (janela fechada,
    Chrome encerrado), recria o driver com `driver_factory` e tenta de novo — no máximo `retries` vezes.
    Devolve (jobs|None, driver_em_uso, erro|None)."""
    attempt = 0
    while True:
        try:
            return collector(driver, cfg), driver, None
        except Exception as e:
            if driver is None or attempt >= retries or driver_factory is None or session_alive(driver):
                return None, driver, e     # erro da empresa (não da sessão): não insiste
            attempt += 1
            log.warning("[%s] sessão do navegador caiu (%s); recriando o Chrome — tentativa %d/%d",
                        cfg.get("company_id"), type(e).__name__, attempt + 1, retries + 1)
            quit_driver(driver)
            driver = driver_factory()

def write_status(out_dir: Path, **data) -> None:
    """Grava out/status.json (o app lê para a barra de progresso estilo player)."""
    try:
        out_dir.mkdir(parents=True, exist_ok=True)
        payload = {"updated_at": datetime.now().isoformat(timespec="seconds"), **data}
        tmp = out_dir / ".status.tmp"
        tmp.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
        tmp.replace(out_dir / "status.json")
    except Exception as e:
        log.debug("não consegui gravar status: %s", e)


def run(driver, only: list[str] | None = None, out_dir: Path | None = None,
        driver_factory=None) -> list[Job]:
    reset_host_state()                                   # o disjuntor de hosts vale só para esta execução
    cfg = load_json(paths.config_file("companies.json"))["companies"]
    profile = load_json(paths.config_file("profile.json"))
    out_dir = out_dir or paths.OUT
    out_dir.mkdir(parents=True, exist_ok=True)

    selected = [c for c in cfg if not only or c["company_id"] in only]
    jobs: list[Job] = []
    status: dict[str, dict] = {}
    drivers = [driver]                     # o 1º é do chamador; os criados aqui são encerrados no fim
    started = time.perf_counter()
    progress = {"state": "running", "started_at": datetime.now().isoformat(timespec="seconds"),
                "total": len(selected), "done": 0, "current": None, "results": [], "errors": []}
    write_status(out_dir, **progress)
    try:
        for c in selected:
            progress["current"] = {"company_id": c["company_id"], "name": c["name"]}
            write_status(out_dir, **progress)
            t0 = time.perf_counter()
            if c["adapter"] in DETAIL_CACHED:        # detalhes já guardados no banco: só abre o que é novo ou velho
                c = {**c, "_known": _known_details(c["company_id"])}
            if c["adapter"] in NEEDS_BROWSER and drivers[-1] is None and driver_factory is not None:
                try:                       # Chrome sob demanda: só abre se alguma empresa precisar dele
                    drivers.append(driver_factory())
                except Exception as e:
                    log.error("[%s] não consegui abrir o Chrome: %s", c["company_id"], e)
            if c["adapter"] in NEEDS_BROWSER and drivers[-1] is None:
                got, drv, err = None, drivers[-1], RuntimeError("Chrome indisponível (instale o Google Chrome)")
            else:
                got, drv, err = collect_one(COLLECTORS[c["adapter"]], drivers[-1], c, driver_factory)
            elapsed = time.perf_counter() - t0
            if drv is not drivers[-1]:
                drivers.append(drv)
            if err is not None:             # uma empresa falhar não derruba as outras
                log.error("[%s] falhou após %.1fs: %s: %s", c["company_id"], elapsed,
                          type(err).__name__, err, exc_info=err)
                message = source_error_message(err)
                status[c["company_id"]] = {"ok": False, "error": message,
                                           "seconds": round(elapsed, 1)}
                progress["errors"].append({"company_id": c["company_id"], "name": c["name"],
                                           "error": message})
            else:
                log.info("[%s] %d vagas em %.1fs", c["company_id"], len(got), elapsed)
                status[c["company_id"]] = {"ok": True, "count": len(got), "seconds": round(elapsed, 1)}
                jobs.extend(got)
            progress["done"] += 1
            progress["results"].append({"company_id": c["company_id"], "name": c["name"],
                                        "ok": err is None, "count": len(got) if err is None else 0,
                                        "seconds": round(elapsed, 1)})
            progress["current"] = None
            write_status(out_dir, **progress)

        for j in jobs:
            score_job(j, profile)
        jobs.sort(key=lambda j: ({"ELIGIBLE": 0, "MAYBE": 1, "BLOCKED": 2}[j.verdict], -j.score))
        log.info("captura: %d vagas em %.1fs (%d empresas)", len(jobs), time.perf_counter() - started,
                 len(status))
        write_outputs(jobs, status, out_dir)

        if not status:
            log.error("nenhuma empresa selecionada (confira --only em config/companies.json): nada gravado no banco")
        elif not any(st.get("ok") for st in status.values()):
            log.error("todas as empresas falharam: execução NÃO gravada no banco (erros em %s)",
                      out_dir / "vagas-latest.json")
        else:
            conn = db.connect()
            try:
                db.save_run(conn, jobs, status, cfg)
                dashboard.build(conn, out_dir / "dashboard.html")
            finally:
                conn.close()

        progress.update(state="done", finished_at=datetime.now().isoformat(timespec="seconds"),
                        total_jobs=len(jobs),
                        eligible=sum(1 for j in jobs if j.verdict == "ELIGIBLE"),
                        all_failed=bool(status) and not any(st.get("ok") for st in status.values()))
        write_status(out_dir, **progress)
        return jobs
    except Exception as e:
        progress.update(state="crashed", error=f"{type(e).__name__}: {e}")
        write_status(out_dir, **progress)
        raise
    finally:
        for extra in drivers[1:]:
            if extra is not None:
                quit_driver(extra)


def cleanup_outputs(out_dir: Path, keep: int = 60) -> None:
    """Mantém só as N execuções mais recentes (cada JSON tem ~5 MB; rodar todo dia acumula)."""
    runs = sorted(out_dir.glob("vagas-20*.json"), key=lambda p: p.stat().st_mtime, reverse=True)
    removed = 0
    for old in runs[keep:]:
        for ext in (".json", ".csv"):
            p = old.with_suffix(ext)
            if p.exists():
                p.unlink()
                removed += 1
    if removed:
        log.info("limpeza: %d arquivo(s) antigos removidos de out/ (mantendo %d execuções)", removed, keep)


def write_outputs(jobs: list[Job], status: dict, out_dir: Path) -> None:
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    payload = {"generated_at": datetime.now().isoformat(timespec="seconds"),
               "status": status, "total": len(jobs), "jobs": [j.to_dict(full=False) for j in jobs]}
    for name in (f"vagas-{stamp}.json", "vagas-latest.json"):
        (out_dir / name).write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    for name in (f"vagas-{stamp}.csv", "vagas-latest.csv"):
        with open(out_dir / name, "w", newline="", encoding="utf-8-sig") as f:   # utf-8-sig: Excel abre acentos certo
            w = csv.DictWriter(f, fieldnames=CSV_FIELDS)
            w.writeheader()
            for j in jobs:
                d = j.to_dict()
                d["techs"] = ", ".join(j.techs)
                d["reasons"] = " | ".join(j.reasons)
                w.writerow({k: d[k] for k in CSV_FIELDS})
    cleanup_outputs(out_dir)


def print_summary(jobs: list[Job]) -> None:
    from collections import Counter
    print(f"\n{len(jobs)} vagas capturadas")
    for cid, n in Counter(j.company_name for j in jobs).items():
        print(f"  {cid}: {n}")
    if not jobs:
        print("\n[!] Nenhuma vaga capturada. Veja logs/scraper.log e out/vagas-latest.json (status por empresa).")
        return
    print("\nTop 15 (ELIGIBLE/MAYBE):")
    for j in [x for x in jobs if x.verdict != "BLOCKED"][:15]:
        print(f"  [{j.verdict:8}] {j.score:5.1f}  {j.company_name:15} {j.title[:60]}  ({j.location})")
