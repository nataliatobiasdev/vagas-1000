"""Uso:
    python main.py                       # captura as 3 empresas, grava no banco e abre o painel
    python main.py --show                # com janela do Chrome visível (útil para depurar seletores)
    python main.py --only ciandt stone   # só algumas empresas
    python main.py --painel              # só regenera o painel a partir do banco (sem capturar)
    python main.py --reavaliar           # reaplica o profile.json às vagas já no banco e regenera o painel
    python main.py --no-open             # não abre o painel no navegador ao final
"""
import argparse
import logging
import webbrowser
from pathlib import Path

from scraper import dashboard, db, reports
from scraper.runner import ROOT, run, print_summary

LOG_DIR = ROOT / "logs"


def setup_logging() -> None:
    """Log no console (só hora) e no arquivo logs/scraper.log (data + hora), para diagnosticar depois."""
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    console = logging.StreamHandler()
    console.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(message)s", "%H:%M:%S"))
    logfile = logging.FileHandler(LOG_DIR / "scraper.log", encoding="utf-8")
    logfile.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(message)s", "%Y-%m-%d %H:%M:%S"))
    logging.basicConfig(level=logging.INFO, handlers=[console, logfile])


def main():
    ap = argparse.ArgumentParser(description="Captura vagas de 3 empresas via Chrome/Selenium")
    ap.add_argument("--show", action="store_true", help="abre o Chrome com janela")
    ap.add_argument("--only", nargs="*", help="company_id: ciandt stone zupinnovation")
    ap.add_argument("--painel", action="store_true", help="só regenera out/dashboard.html a partir do banco")
    ap.add_argument("--reavaliar", action="store_true", help="reavalia vagas do banco com o profile.json atual")
    ap.add_argument("--no-open", action="store_true", help="não abre o painel ao final")
    args = ap.parse_args()
    setup_logging()

    if args.painel or args.reavaliar:
        import json
        conn = db.connect()
        if args.reavaliar:
            prof = json.loads((ROOT / "config" / "profile.json").read_text(encoding="utf-8"))
            print(db.rescore_all(conn, prof), "vagas reavaliadas")
        out = dashboard.build(conn)
        reports.build_presenciais(conn, ROOT / "out" / "presenciais.md")
        conn.close()
    else:
        from scraper.driver import make_driver, quit_driver
        try:
            driver = make_driver(headless=not args.show)
        except Exception:
            logging.getLogger("scraper").exception("não foi possível abrir o Chrome")
            print("\nNão foi possível abrir o Chrome. Confira se o Google Chrome está instalado e rode setup.bat.")
            raise SystemExit(1)
        try:
            # se a sessão do Chrome morrer no meio, o runner recria o driver (1 retentativa por empresa)
            jobs = run(driver, only=args.only, driver_factory=lambda: make_driver(headless=not args.show))
        finally:
            quit_driver(driver)             # sempre encerra o navegador, mesmo se a sessão morreu
        print_summary(jobs)
        out = ROOT / "out" / "dashboard.html"
    print(f"\nPainel: {out}\nBanco:  {db.DEFAULT_DB}")
    if not args.no_open and Path(out).exists():
        webbrowser.open(Path(out).resolve().as_uri())


if __name__ == "__main__":
    main()
