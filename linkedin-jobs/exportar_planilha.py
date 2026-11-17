"""Gera a planilha da busca Salesforce Sênior (Brasil e América Latina) SEM usar IA: é um script comum que usa o
Chrome já logado, como o linkedin_jobs.py, e grava o CSV no formato que o app importa (aba LinkedIn).

    python exportar_planilha.py                      # sem abrir detalhes (modo seguro, como o linkedin_jobs.py)
    python exportar_planilha.py --detalhes 30        # abre até 30 páginas de vaga (descrição completa)
    python exportar_planilha.py --detalhes todas     # abre todas (mais lento e mais arriscado; ver o aviso)

Depois, no app: botão **Importar vagas** e escolha o CSV gerado em out/ (ou `python main.py --importar <arquivo>`).

Limites: o LinkedIn não permite automação nos termos de uso; as pausas, o limite de 1 execução por dia e a parada
em CAPTCHA/checkpoint do linkedin_jobs.py continuam valendo. Não se candidata, não envia mensagem, não altera a conta.
"""
from __future__ import annotations

import argparse
import logging
import sys
from datetime import date
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import linkedin_jobs as lj  # noqa: E402  (reaproveita Chrome/CDP, buscas, cards, detalhes e pausas)
import planilha  # noqa: E402

log = logging.getLogger("planilha")

# a mesma busca da planilha de 17/11: Salesforce sênior, em duas áreas
BUSCAS = [
    {"id": "brasil", "label": "Brasil", "origem": "Brasil", "location": "Brazil", "tpr": "r604800", "wt": "2,3",
     "keywords": '("Salesforce Developer" OR "Salesforce Engineer" OR LWC OR Apex OR "Salesforce") AND (Senior OR Sênior)'},
    {"id": "latam", "label": "América Latina", "origem": "América Latina", "location": "Latin America", "tpr": "r604800",
     "wt": "2,3", "keywords": '("Salesforce Developer" OR "Salesforce Engineer" OR LWC OR Apex OR "Salesforce") AND (Senior OR Sênior)'},
]


def _detalhe_do_card(page, card: dict) -> dict:
    """Abre a página da vaga, lê descrição e campos e volta para a busca."""
    if not lj.open_detail(page, card):
        return dict(card)
    d = lj.parse_detail(page, card)
    apply_txt = (d.get("apply") or "").lower()
    d["easy_apply"] = "simplificad" in apply_txt or "easy apply" in apply_txt
    d["applied"] = "candidatad" in apply_txt or "applied" in apply_txt
    d["contract"] = d.get("contract", "")
    return d


def main() -> int:
    ap = argparse.ArgumentParser(description="Planilha da busca Salesforce Sênior, sem IA")
    ap.add_argument("--detalhes", default="0", help="quantas vagas abrir: número, ou 'todas' (padrão: 0, modo seguro)")
    ap.add_argument("--saida", type=Path, default=lj.OUT, help="pasta de saída (padrão: linkedin-jobs/out)")
    args = ap.parse_args()

    limite = 10_000 if args.detalhes == "todas" else int(args.detalhes or 0)
    if limite > 5 and args.detalhes != "todas":
        log.warning("abrindo %d páginas de vaga: quanto mais páginas, maior o risco de restrição na conta", limite)
    if args.detalhes == "todas":
        log.warning("abrindo TODAS as vagas: é o modo mais arriscado para a conta; use com moderação")
    args.saida.mkdir(parents=True, exist_ok=True)
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s", datefmt="%H:%M:%S",
                        handlers=[logging.StreamHandler(sys.stdout)])

    from playwright.sync_api import sync_playwright
    vistos: dict[str, tuple[dict, str]] = {}
    with sync_playwright() as pw:
        _browser, _ctx, page = lj.connect(pw)     # não fecha o navegador: é o Chrome do usuário
        try:
            for i, busca in enumerate(BUSCAS):
                if i:
                    lj.safe_pause(page, f"antes da busca {busca['label']}", lj.SEARCH_PAUSE)
                lj.open_search(page, busca, start=0)
                reason = lj.blocked_reason(page)
                if reason:
                    lj.save_debug(page, f"bloqueio-planilha-{busca['id']}")
                    raise lj.Blocked(reason)
                cards = lj.scrape_cards(page)
                log.info("[%s] %d cards na busca", busca["label"], len(cards))
                for c in cards:
                    vistos.setdefault(c["job_id"], (c, busca["origem"]))
            log.info("total: %d vagas únicas", len(vistos))

            linhas = []
            for n, (jid, (card, origem)) in enumerate(vistos.items()):
                vaga = card
                if n < limite:
                    lj.safe_pause(page, f"detalhe {n + 1}/{min(limite, len(vistos))}", (6.0, 14.0))
                    vaga = _detalhe_do_card(page, card)
                linhas.append(planilha.linha(vaga, origem))
        except lj.Blocked as e:
            log.error("parei: %s", e)
            return 2
        finally:
            pass

    destino = args.saida / planilha.nome_arquivo(date.today())
    planilha.escrever(destino, linhas)
    print(f"Planilha: {destino} ({len(linhas)} vagas, {min(limite, len(linhas))} com descrição completa)")
    print("No app: Importar vagas → escolha esse arquivo.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
