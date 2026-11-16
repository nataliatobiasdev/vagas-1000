from __future__ import annotations

import csv
import json
import logging
import time
from datetime import datetime
from pathlib import Path

from . import dashboard, db, reports
from .collectors import COLLECTORS
from .driver import quit_driver, session_alive
from .filtering import score_job
from .models import Job

log = logging.getLogger("scraper")
ROOT = Path(__file__).resolve().parent.parent

CSV_FIELDS = ["company_name", "title", "verdict", "score", "location", "workplace_type", "area",
              "techs", "url", "source", "captured_at", "reasons"]


def load_json(p: Path) -> dict:
    return json.loads(p.read_text(encoding="utf-8"))


def collect_one(collector, driver, cfg: dict, driver_factory=None, retries: int = 1):
    """Executa o coletor de UMA empresa. Se a sessão do navegador morrer no meio (janela fechada,
    Chrome encerrado), recria o driver com `driver_factory` e tenta de novo — no máximo `retries` vezes.
    Devolve (jobs|None, driver_em_uso, erro|None)."""
    attempt = 0
    while True:
        try:
            return collector(driver, cfg), driver, None
        except Exception as e:
            if attempt >= retries or driver_factory is None or session_alive(driver):
                return None, driver, e     # erro da empresa (não da sessão): não insiste
            attempt += 1
            log.warning("[%s] sessão do navegador caiu (%s); recriando o Chrome — tentativa %d/%d",
                        cfg.get("company_id"), type(e).__name__, attempt + 1, retries + 1)
            quit_driver(driver)
            driver = driver_factory()

def run(driver, only: list[str] | None = None, out_dir: Path | None = None,
        driver_factory=None) -> list[Job]:
    cfg = load_json(ROOT / "config" / "companies.json")["companies"]
    profile = load_json(ROOT / "config" / "profile.json")
    out_dir = out_dir or ROOT / "out"
    out_dir.mkdir(parents=True, exist_ok=True)

    jobs: list[Job] = []
    status: dict[str, dict] = {}
    drivers = [driver]                     # o 1º é do chamador; os criados aqui são encerrados no fim
    started = time.perf_counter()
    try:
        for c in cfg:
            if only and c["company_id"] not in only:
                continue
            t0 = time.perf_counter()
            got, drv, err = collect_one(COLLECTORS[c["adapter"]], drivers[-1], c, driver_factory)
            elapsed = time.perf_counter() - t0
            if drv is not drivers[-1]:
                drivers.append(drv)
            if err is not None:             # uma empresa falhar não derruba as outras
                log.error("[%s] falhou após %.1fs: %s: %s", c["company_id"], elapsed,
                          type(err).__name__, err, exc_info=err)
                status[c["company_id"]] = {"ok": False, "error": f"{type(err).__name__}: {err}",
                                           "seconds": round(elapsed, 1)}
            else:
                log.info("[%s] %d vagas em %.1fs", c["company_id"], len(got), elapsed)
                status[c["company_id"]] = {"ok": True, "count": len(got), "seconds": round(elapsed, 1)}
                jobs.extend(got)

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
                reports.build_presenciais(conn, out_dir / "presenciais.md")
            finally:
                conn.close()
        return jobs
    finally:
        for extra in drivers[1:]:
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
               "status": status, "total": len(jobs), "jobs": [j.to_dict() for j in jobs]}
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
