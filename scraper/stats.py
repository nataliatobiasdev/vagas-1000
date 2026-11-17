"""Números do alto da tela Início: o que a última leitura confirmou e o que o banco só guarda.

O banco nunca apaga uma vaga só porque a fonte não respondeu (queda da Lever, 429 do Workday...): elas ficam abertas, mas
não foram verificadas. Contá-las junto com as confirmadas fazia o alto da tela (1.201 vagas, 262 elegíveis) divergir da
linha de baixo ("1110 vagas · 219 elegíveis" da última busca) e parecer desatualizado.
"""
from __future__ import annotations

import sqlite3

# Fontes cuja leitura MAIS RECENTE falhou. Olha o último resultado de cada empresa, não só a última execução: uma
# execução parcial (refazer só as que falharam) não pode fazer as outras 50 parecerem "sem leitura".
FAILING_SQL = """SELECT DISTINCT rc.company_id FROM run_companies rc
                 WHERE rc.ok = 0 AND rc.run_id = (SELECT MAX(run_id) FROM run_companies WHERE company_id = rc.company_id)"""


def board_counts(con: sqlite3.Connection) -> dict:
    failing = [r[0] for r in con.execute(FAILING_SQL)]
    marks = ",".join("?" * len(failing))

    def count(extra: str = "", args: tuple = ()) -> int:
        return con.execute(f"SELECT COUNT(*) FROM jobs WHERE status='open' {extra}", args).fetchone()[0]

    open_total = count()
    eligible_total = count("AND verdict='ELIGIBLE'")
    unverified_open = count(f"AND company_id IN ({marks})", tuple(failing)) if failing else 0
    unverified_eligible = count(f"AND verdict='ELIGIBLE' AND company_id IN ({marks})", tuple(failing)) if failing else 0
    companies = con.execute("SELECT COUNT(*) FROM companies WHERE coalesce(adapter,'')<>'importado'").fetchone()[0]
    return {
        "open_confirmed": open_total - unverified_open, "eligible_confirmed": eligible_total - unverified_eligible,
        "open_total": open_total, "eligible_total": eligible_total,
        "unverified_open": unverified_open, "unverified_eligible": unverified_eligible,
        "failing_ids": failing, "companies": companies,
    }
