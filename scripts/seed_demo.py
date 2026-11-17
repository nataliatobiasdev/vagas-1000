"""Cria um banco de demonstração a partir dos fixtures de teste e gera o painel (out/dashboard.html).

Serve para ver o painel sem rodar a captura e para o autoteste do CI abrir a janela com cards de verdade.
Use com VAGAS1000_HOME apontando para uma pasta descartável:  VAGAS1000_HOME=.tmp/demo python scripts/seed_demo.py
"""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from scraper import dashboard, db, parsers, paths                      # noqa: E402
from scraper.filtering import score_job                                 # noqa: E402

FIX = ROOT / "tests" / "fixtures"


def main() -> None:
    profile = json.loads((ROOT / "config" / "profile.json").read_text(encoding="utf-8"))
    load = lambda n: json.loads((FIX / n).read_text(encoding="utf-8"))   # noqa: E731
    jobs = (parsers.parse_greenhouse_api(load("greenhouse_api.json"), "acme-gh", "Acme (Greenhouse)")
            + parsers.parse_lever_api(load("lever_api.json"), "acme-lever", "Acme (Lever)")
            + parsers.parse_ashby_api(load("ashby_api.json"), "acme-ashby", "Acme (Ashby)"))
    for j in jobs:
        score_job(j, profile)
    status = {cid: {"ok": True, "count": sum(1 for j in jobs if j.company_id == cid)}
              for cid in {j.company_id for j in jobs}}
    conn = db.connect()
    db.save_run(conn, jobs, status)
    out = dashboard.build(conn)
    conn.close()
    print(f"{len(jobs)} vagas de demonstração -> {out}")


if __name__ == "__main__":
    main()
