"""vagas1000 — captura de vagas (linha de comando).

Uso:
    python main.py                       # captura todas as empresas, grava no banco e abre o painel
    python main.py --show                # com janela do Chrome visível (útil para depurar seletores)
    python main.py --only ciandt stone   # só algumas empresas
    python main.py --painel              # só regenera o painel a partir do banco (sem capturar)
    python main.py --reavaliar           # reaplica o profile.json às vagas já no banco e regenera o painel
    python main.py --no-open             # não abre o painel no navegador ao final
    python main.py --exportar [arquivo]  # exporta o banco inteiro (vagas + versões + payload bruto) para JSON
    python main.py --importar arquivo    # importa vagas de fora (LinkedIn, planilha): JSON, CSV ou tabela Markdown
"""
import argparse
import logging
import sys
import webbrowser
from pathlib import Path

from scraper import dashboard, db, paths, reports
from scraper.runner import run, print_summary

LOG_DIR = paths.LOGS


def setup_logging() -> None:
    """Log no console (só hora) e no arquivo logs/scraper.log (data + hora), para diagnosticar depois."""
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    handlers = []
    if sys.stderr is not None:       # no app instalado (sem console) não há stderr
        console = logging.StreamHandler()
        console.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(message)s", "%H:%M:%S"))
        handlers.append(console)
    logfile = logging.FileHandler(LOG_DIR / "scraper.log", encoding="utf-8")
    logfile.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(message)s", "%Y-%m-%d %H:%M:%S"))
    handlers.append(logfile)
    logging.basicConfig(level=logging.INFO, handlers=handlers)


def main(argv=None):
    ap = argparse.ArgumentParser(description="vagas1000: captura vagas de dezenas de empresas")
    ap.add_argument("--show", action="store_true", help="abre o Chrome com janela")
    ap.add_argument("--only", nargs="*", help="company_id: ciandt stone zupinnovation")
    ap.add_argument("--painel", action="store_true", help="só regenera out/dashboard.html a partir do banco")
    ap.add_argument("--reavaliar", action="store_true", help="reavalia vagas do banco com o profile.json atual")
    ap.add_argument("--no-open", action="store_true", help="não abre o painel ao final")
    ap.add_argument("--importar", metavar="ARQUIVO",
                    help="importa vagas de um arquivo (JSON, CSV ou tabela Markdown), como a captura do LinkedIn")
    ap.add_argument("--fonte", help="rótulo da fonte ao importar (padrão: o que o arquivo diz, ou linkedin)")
    ap.add_argument("--exportar", nargs="?", const="", metavar="ARQUIVO",
                    help="exporta todas as vagas guardadas (com versões e payload bruto) para JSON; padrão out/banco-vagas.json")
    args = ap.parse_args(argv)
    setup_logging()
    paths.ensure_config()          # copia config/*.json do pacote para a pasta de dados (editável) na 1ª execução

    if args.importar:
        from scraper import importer
        try:
            res = importer.run_import(args.importar, args.fonte)
        except (ValueError, OSError) as e:
            print(f"Não consegui importar: {e}")
            raise SystemExit(1)
        print(f"{res['lidas']} vagas lidas ({res['fonte']}): {res['novas']} novas, {res['atualizadas']} já existiam.")
        print(f"Painel: {res['painel']}")
        return

    if args.exportar is not None:
        conn = db.connect()
        dest = reports.export_archive(conn, args.exportar or paths.OUT / "banco-vagas.json")
        conn.close()
        print(f"Banco exportado: {dest}")
        return

    if args.painel or args.reavaliar:
        import json
        conn = db.connect()
        if args.reavaliar:
            prof = json.loads(paths.config_file("profile.json").read_text(encoding="utf-8"))
            print(db.rescore_all(conn, prof), "vagas reavaliadas")
        out = dashboard.build(conn)
        conn.close()
    else:
        from scraper.driver import make_driver
        # O Chrome só abre quando uma empresa precisa dele (hoje, só a Stone): se ele faltar,
        # as demais empresas continuam e a Stone aparece como erro no relatório.
        jobs = run(None, only=args.only, driver_factory=lambda: make_driver(headless=not args.show))
        print_summary(jobs)
        out = paths.OUT / "dashboard.html"
    print(f"\nPainel: {out}\nBanco:  {db.DEFAULT_DB}")
    if not args.no_open and Path(out).exists():
        webbrowser.open(Path(out).resolve().as_uri())


if __name__ == "__main__":
    main()
