"""Indicadores do card de cada dia (aba Histórico). Modulares: cada módulo olha os eventos do dia e devolve zero ou mais
indicadores com uma RELEVÂNCIA (0 a 1); o card mostra o bloco fixo mais os módulos mais relevantes. Ligar, desligar e
ajustar limites: `config/historico.json`.

Um indicador é um dicionário: id, label, value, detail, relevance, tone ("info" | "good" | "warn"), company_id, jobs.
"""
from __future__ import annotations

import json
import logging
from copy import deepcopy
from types import SimpleNamespace
from typing import Callable

from . import history, paths

log = logging.getLogger("scraper")

DEFAULTS = {
    "max_modulos_no_card": 4,
    "relevancia_minima": 0.25,
    "modulos": {
        "movimento_empresa": {"ativo": True, "min_eventos": 5, "min_parcela": 0.10},
        "empresa_zerou_voltou": {"ativo": True},
        "elegiveis_novas": {"ativo": True},
        "mudanca_veredito": {"ativo": True},
        "mudanca_nota": {"ativo": True},
        "salario": {"ativo": True},
        "modalidade_local": {"ativo": True},
        "vagas_reescritas": {"ativo": True},
        "tecnologia": {"ativo": True, "min_saldo": 3},
        "relampago": {"ativo": True, "max_dias": 2},
        "reaberturas": {"ativo": True},
        "anomalia": {"ativo": True, "fator": 3, "min_eventos": 5, "janela_dias": 7},
        "fonte_sem_leitura": {"ativo": True, "min_dias": 2},
    },
}
VERDICT = {"ELIGIBLE": "Elegível", "MAYBE": "Talvez", "BLOCKED": "Bloqueada"}
WORK = {"remote": "Remoto", "hybrid": "Híbrido", "onsite": "Presencial", "": "não informado"}
TECH = {"SALESFORCE": "Salesforce", "AWS": "AWS", "GO": "Go", "PYTHON": "Python", "TYPESCRIPT_NODE": "TypeScript/Node",
        "ANGULAR_REACT": "Angular/React", "GRAPHQL": "GraphQL", "AI_GENAI": "IA/GenAI", "INTEGRATION_ARCH": "Integração",
        "JAVA": "Java", "DOTNET": ".NET"}


def load_config(override: dict | None = None) -> dict:
    """Padrões do código + `config/historico.json` (se existir) + `override` (testes). Config inválida cai nos padrões."""
    cfg = deepcopy(DEFAULTS)

    def merge(dst: dict, src: dict) -> None:
        for k, v in (src or {}).items():
            if isinstance(v, dict) and isinstance(dst.get(k), dict):
                merge(dst[k], v)
            else:
                dst[k] = v
    try:
        merge(cfg, json.loads(paths.config_file("historico.json").read_text(encoding="utf-8")))
    except (OSError, ValueError):
        pass
    merge(cfg, override or {})
    return cfg


def ind(id_: str, label: str, value, detail: str = "", relevance: float = 0.0, tone: str = "info", company_id: str = "",
        jobs: list[str] | None = None) -> dict:
    return {"id": id_, "label": label, "value": value, "detail": detail, "relevance": round(min(max(relevance, 0.0), 1.0), 3),
            "tone": tone, "company_id": company_id, "jobs": (jobs or [])[:8]}


def _events(conn, day: str) -> list[dict]:
    return [dict(r) for r in conn.execute(
        "SELECT e.*, j.title, j.company_name, j.score AS job_score, j.techs, j.first_seen FROM job_events e "
        "LEFT JOIN jobs j ON j.job_key = e.job_key WHERE e.day=?", (day,))]


def _plural(n: int, one: str, many: str) -> str:
    return f"{n} {one if n == 1 else many}"


# ----------------------------------------------------------------------------------------------------- bloco fixo
def fixed(summary: dict, prev: dict | None, names: dict) -> list[dict]:
    delta = ""
    if summary["baseline"]:
        delta = "linha de base: ponto de partida do histórico"
    elif prev:
        delta = f"{summary['open_end'] - prev['open_end']:+d} em relação a {prev['day']}"
    failing = json.loads(summary["failing"] or "[]")
    cov_detail = ("sem leitura: " + ", ".join(names.get(c, c) for c in failing)) if failing else "todas as fontes responderam"
    out = [
        ind("abertas", "Abertas no fim do dia", summary["open_end"], delta),
        ind("entraram", "Entraram", summary["entered"], "primeira vez vistas neste dia"),
        ind("sairam", "Saíram", summary["exited"], "sumiram da fonte (fonte lida com sucesso)"),
        ind("mudaram", "Mudaram", summary["changed"], "vagas com alguma alteração"),
        ind("elegiveis", "Elegíveis abertas", summary["eligible_open"],
            f"+{summary['eligible_in']} entraram · −{summary['eligible_out']} saíram"),
        ind("cobertura", "Fontes lidas", f"{summary['companies_ok']}/{summary['companies_total']}", cov_detail,
            tone="warn" if failing else "info"),
    ]
    if summary["reopened"]:
        out.insert(3, ind("voltaram", "Voltaram", summary["reopened"], "vagas que tinham saído e reapareceram"))
    return out


# ------------------------------------------------------------------------------------------------------- módulos
def m_movimento_empresa(c, mc):
    by: dict[str, dict] = {}
    for e in c.events:
        if e["kind"] in ("entrou", "saiu", "voltou"):
            d = by.setdefault(e["company_id"], {"in": 0, "out": 0})
            d["out" if e["kind"] == "saiu" else "in"] += 1
    out = []
    for cid, d in by.items():
        n = d["in"] + d["out"]
        share = n / max(history.open_count(c.conn, c.day, [cid]), 1)
        if n >= mc.get("min_eventos", 5) and share >= mc.get("min_parcela", 0.10):
            out.append(ind(f"movimento:{cid}", f"{c.names.get(cid, cid)}: +{d['in']} / −{d['out']}", n,
                           f"{share:.0%} das vagas da empresa mudaram de lugar", 0.3 + share, "info", cid))
    return sorted(out, key=lambda i: -i["relevance"])[:3]


def m_empresa_zerou_voltou(c, mc):
    """Fonte que responde OK mas com 0 vagas (o banco não fecha nada nesse caso: pode ser congelamento de contratações ou
    fonte quebrada) e empresa que começa a ter vagas."""
    out = []
    rows = c.conn.execute(
        "SELECT rc.company_id, rc.ok, rc.job_count FROM run_companies rc WHERE rc.run_id = ("
        " SELECT MAX(rc2.run_id) FROM run_companies rc2 JOIN runs r2 ON r2.run_id = rc2.run_id"
        " WHERE rc2.company_id = rc.company_id AND substr(r2.started_at,1,10) = ?)", (c.day,)).fetchall()
    for r in rows:
        if r["ok"] and r["job_count"] == 0:
            kept = history.open_count(c.conn, c.day, [r["company_id"]])
            if kept > 0:
                out.append(ind(f"zerou:{r['company_id']}", f"{c.names.get(r['company_id'], r['company_id'])} devolveu 0 vagas", 0,
                               f"{kept} vagas abertas continuam guardadas (congelamento de contratações ou fonte quebrada?)", 0.9, "warn",
                               r["company_id"]))
    entered = {e["company_id"] for e in c.events if e["kind"] == "entrou"}
    for cid in entered:
        if history.open_count(c.conn, history.previous_day(c.day), [cid]) == 0:
            after = history.open_count(c.conn, c.day, [cid])
            out.append(ind(f"comecou:{cid}", f"{c.names.get(cid, cid)} começou a ter vagas", after, "não tinha nenhuma aberta no dia anterior",
                           0.8, "good", cid))
    return out


def _eligible_in(c):
    return [e for e in c.events if (e["kind"] in ("entrou", "voltou") and e["verdict"] == "ELIGIBLE")
            or (e["kind"] == "mudou" and e["field"] == "veredito" and e["new"] == "ELIGIBLE")]


def m_elegiveis_novas(c, mc):
    rows = _eligible_in(c)
    if not rows:
        return []
    best = max(rows, key=lambda e: e.get("job_score") or 0)
    detail = f"maior nota: {round(best.get('job_score') or 0)} · {best.get('title') or ''} ({best.get('company_name') or ''})"
    return [ind("elegiveis_novas", _plural(len(rows), "vaga elegível nova", "vagas elegíveis novas"), len(rows), detail,
                0.4 + len(rows) / 10, "good", jobs=[e["job_key"] for e in sorted(rows, key=lambda e: -(e.get("job_score") or 0))])]


def m_mudanca_veredito(c, mc):
    rows = [e for e in c.events if e["kind"] == "mudou" and e["field"] == "veredito"]
    if not rows:
        return []
    pairs: dict[str, int] = {}
    for e in rows:
        k = f"{VERDICT.get(e['old'], e['old'])} → {VERDICT.get(e['new'], e['new'])}"
        pairs[k] = pairs.get(k, 0) + 1
    return [ind("mudanca_veredito", _plural(len(rows), "vaga mudou", "vagas mudaram") + " de veredito", len(rows),
                " · ".join(f"{n}× {k}" for k, n in sorted(pairs.items(), key=lambda p: -p[1])), 0.3 + len(rows) / 10,
                jobs=[e["job_key"] for e in rows])]


def m_mudanca_nota(c, mc):
    rows = [e for e in c.events if e["kind"] == "mudou" and e["field"] == "nota"]
    if not rows:
        return []
    big = max(rows, key=lambda e: abs(float(e["new"] or 0) - float(e["old"] or 0)))
    return [ind("mudanca_nota", _plural(len(rows), "vaga com nota", "vagas com nota") + f" ±{history.SCORE_DELTA_MIN} ou mais", len(rows),
                f"maior: {big['old']} → {big['new']} · {big.get('title') or ''}", 0.2 + len(rows) / 20,
                jobs=[e["job_key"] for e in rows])]


def m_salario(c, mc):
    rows = [e for e in c.events if e["kind"] == "mudou" and e["field"] == "salario"]
    if not rows:
        return []
    appeared = sum(1 for e in rows if not e["old"] and e["new"])
    removed = sum(1 for e in rows if e["old"] and not e["new"])
    changed = len(rows) - appeared - removed
    parts = [p for p in (f"{appeared} passaram a mostrar", f"{removed} deixaram de mostrar", f"{changed} alteradas") if p[0] != "0"]
    return [ind("salario", _plural(len(rows), "vaga com salário alterado", "vagas com salário alterado"), len(rows), " · ".join(parts),
                0.5 + len(rows) / 20, jobs=[e["job_key"] for e in rows])]


def m_modalidade_local(c, mc):
    rows = [e for e in c.events if e["kind"] == "mudou" and e["field"] in ("modalidade", "local", "contrato")]
    if not rows:
        return []
    e0 = rows[0]
    fmt = lambda v: WORK.get(v, v) if e0["field"] == "modalidade" else (v or "—")                    # noqa: E731
    return [ind("modalidade_local", _plural(len(rows), "vaga mudou", "vagas mudaram") + " de modalidade, local ou contrato", len(rows),
                f"ex.: {e0['field']}: {fmt(e0['old'])} → {fmt(e0['new'])} · {e0.get('title') or ''}", 0.35 + len(rows) / 15,
                jobs=[e["job_key"] for e in rows])]


def m_vagas_reescritas(c, mc):
    rows = [e for e in c.events if e["kind"] == "mudou" and e["field"] in ("descricao", "titulo")]
    if not rows:
        return []
    return [ind("vagas_reescritas", _plural(len(rows), "vaga reescrita", "vagas reescritas"), len(rows),
                "título ou texto alterados pela empresa", 0.2 + len(rows) / 30, jobs=[e["job_key"] for e in rows])]


def m_tecnologia(c, mc):
    delta: dict[str, int] = {}
    ins = _eligible_in(c)
    outs = [e for e in c.events if (e["kind"] == "saiu" and e["verdict"] == "ELIGIBLE")
            or (e["kind"] == "mudou" and e["field"] == "veredito" and e["old"] == "ELIGIBLE")]
    for rows, sign in ((ins, 1), (outs, -1)):
        for e in rows:
            try:
                techs = json.loads(e.get("techs") or "[]")
            except ValueError:
                techs = []
            for t in techs:
                delta[t] = delta.get(t, 0) + sign
    if not delta:
        return []
    t, d = max(delta.items(), key=lambda kv: abs(kv[1]))
    if abs(d) < mc.get("min_saldo", 3):
        return []
    return [ind(f"tecnologia:{t}", f"{TECH.get(t, t)} {d:+d} elegíveis", d, "saldo de vagas elegíveis com essa tecnologia no dia",
                0.4 + abs(d) / 15, "good" if d > 0 else "warn")]


def m_relampago(c, mc):
    from datetime import date, timedelta
    limit = (date.fromisoformat(c.day) - timedelta(days=int(mc.get("max_dias", 2)))).isoformat()
    base = history.first_day(c.conn)                               # vaga da linha de base já existia: não dá para saber a idade
    rows = [e for e in c.events if e["kind"] == "saiu" and (e.get("first_seen") or "")[:10] >= limit
            and (e.get("first_seen") or "")[:10] != base]
    if not rows:
        return []
    return [ind("relampago", _plural(len(rows), "vaga aberta e fechada", "vagas abertas e fechadas") + f" em até {mc.get('max_dias', 2)} dias",
                len(rows), "vagas de vida curta (testes, pré-requisição ou erro de publicação)", 0.3 + len(rows) / 10,
                jobs=[e["job_key"] for e in rows])]


def m_reaberturas(c, mc):
    rows = [e for e in c.events if e["kind"] == "voltou"]
    return [ind("reaberturas", _plural(len(rows), "vaga reaberta", "vagas reabertas"), len(rows),
                "tinham saído e voltaram", 0.4 + len(rows) / 10, jobs=[e["job_key"] for e in rows])] if rows else []


def m_anomalia(c, mc):
    window = [p for p in c.prev if not p["baseline"] and not p["gap_days"]][: int(mc.get("janela_dias", 7))]
    if len(window) < 3 or c.summary["baseline"]:
        return []
    out = []
    for field, label in (("exited", "saídas"), ("entered", "entradas")):
        avg = sum(p[field] for p in window) / len(window)
        v = c.summary[field]
        if v >= mc.get("min_eventos", 5) and v >= mc.get("fator", 3) * max(avg, 1):
            out.append(ind(f"anomalia:{field}", f"{label.capitalize()} {v / max(avg, 1):.0f}× acima do normal", v,
                           f"média dos últimos {len(window)} dias: {avg:.1f}", 1.0, "warn"))
    return out


def m_fonte_sem_leitura(c, mc):
    out = []
    for cid in json.loads(c.summary["failing"] or "[]"):
        days = 1
        for p in c.prev:
            if cid in json.loads(p["failing"] or "[]"):
                days += 1
            else:
                break
        if days >= mc.get("min_dias", 2):
            out.append(ind(f"sem_leitura:{cid}", f"{c.names.get(cid, cid)}: {days} dias sem leitura", days,
                           "as vagas dela seguem guardadas, mas não verificadas", 0.5 + 0.1 * days, "warn", cid))
    return out


MODULES: dict[str, Callable] = {
    "movimento_empresa": m_movimento_empresa, "empresa_zerou_voltou": m_empresa_zerou_voltou,
    "elegiveis_novas": m_elegiveis_novas, "mudanca_veredito": m_mudanca_veredito, "mudanca_nota": m_mudanca_nota,
    "salario": m_salario, "modalidade_local": m_modalidade_local, "vagas_reescritas": m_vagas_reescritas,
    "tecnologia": m_tecnologia, "relampago": m_relampago, "reaberturas": m_reaberturas, "anomalia": m_anomalia,
    "fonte_sem_leitura": m_fonte_sem_leitura,
}


def compute(conn, day: str, summary: dict, cfg_override: dict | None = None) -> dict:
    """Todos os indicadores do dia: `fixed` (sempre no card) e `modules` (ordenados por relevância)."""
    cfg = load_config(cfg_override)
    names = {r[0]: r[1] for r in conn.execute("SELECT company_id, name FROM companies")}
    prev_rows = [dict(r) for r in conn.execute("SELECT * FROM day_summary WHERE day < ? ORDER BY day DESC LIMIT 30", (day,))]
    ctx = SimpleNamespace(conn=conn, day=day, summary=summary, events=_events(conn, day), prev=prev_rows, names=names)
    modules: list[dict] = []
    for name, fn in MODULES.items():
        mc = cfg["modulos"].get(name, {})
        if not mc.get("ativo", True):
            continue
        if summary["baseline"] and name != "fonte_sem_leitura":       # dia de linha de base: não há "mudança" a comentar
            continue
        try:
            modules += fn(ctx, mc)
        except Exception:                                              # um módulo com defeito não derruba os outros
            log.exception("histórico: módulo %s falhou em %s", name, day)
    modules.sort(key=lambda i: -i["relevance"])
    return {"fixed": fixed(summary, prev_rows[0] if prev_rows else None, names), "modules": modules}


def select(indicators: dict, cfg_override: dict | None = None) -> list[dict]:
    """Módulos que entram no card: os mais relevantes, acima do mínimo e até o máximo configurado."""
    cfg = load_config(cfg_override)
    return [m for m in indicators.get("modules", []) if m["relevance"] >= cfg["relevancia_minima"]][: int(cfg["max_modulos_no_card"])]
