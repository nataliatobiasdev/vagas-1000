"""Relatórios derivados do banco (sem Selenium): lista de vagas presenciais por cidade/UF."""
from __future__ import annotations

import re
import sqlite3
from datetime import datetime
from pathlib import Path

CHINESAS = ("byd", "nio", "gwm", "great wall", "huawei", "xiaomi", "tcl", "chery", "jac",
            "geely", "changan", "gac", "saic", "catl")


def estado(location: str) -> str:
    """'Camaçari, BA' / 'Brasil - BR' -> 'BA' / 'BR'."""
    loc = (location or "").strip()
    m = re.search(r"[,/]\s*([A-Z]{2})\s*$", loc) or re.search(r"-\s*([A-Z]{2})\s*$", loc)
    return m.group(1) if m else "—"


def _chinesa(company_id: str, company_name: str) -> bool:
    cid = (company_id or "").lower()
    name = (company_name or "").lower()
    return any(k in cid for k in CHINESAS) or any(k in name for k in ("byd", "nio", "great wall", "huawei",
                                                                     "xiaomi", "tcl", "chery", "jac "))


def _row(r: dict) -> str:
    titulo = (r["title"] or "").replace("|", "/")[:70]
    emp = (r["company_name"] or "").replace("|", "/")
    if r.get("chinesa"):
        emp = f"**{emp}** 🇨🇳"
    nota = f'{r["score"]:.0f}' if r.get("score") is not None else ""
    link = f'[abrir]({r["url"]})' if r.get("url") else ""
    return f'| {emp} | {titulo} | {r["location"]} | {nota} | {r["verdict"]} | {link} |'


def build_presenciais(conn: sqlite3.Connection, out_path: Path | str) -> Path:
    """Grava out/presenciais.md com as vagas presenciais agrupadas por UF/cidade."""
    out = Path(out_path)
    rows = [dict(r) for r in conn.execute(
        "SELECT company_id, company_name, title, location, url, source, score, verdict "
        "FROM jobs WHERE status='open' AND workplace_type='onsite' "
        "ORDER BY location, score DESC, company_name")]
    for r in rows:
        r["uf"] = estado(r["location"])
        r["chinesa"] = _chinesa(r["company_id"], r["company_name"])

    ba = [r for r in rows if r["uf"] == "BA"]
    by_state: dict[str, list[dict]] = {}
    for r in rows:
        by_state.setdefault(r["uf"], []).append(r)

    lines = [
        "# Vagas presenciais — onde são",
        "",
        f"Gerado em {datetime.now().strftime('%d/%m/%Y %H:%M')} · {len(rows)} vagas presenciais em "
        f"{len({r['location'] for r in rows})} locais · {len(ba)} na Bahia · "
        f"{sum(1 for r in rows if r['chinesa'])} de empresas chinesas",
        "",
        "> Ordenado por UF e nota. A coluna Link abre a vaga original.",
        "",
    ]
    header = ["| Empresa | Vaga | Cidade | Nota | Veredito | Link |", "|---|---|---|---|---|---|"]
    if ba:
        lines += ["## Bahia (BA)", ""] + header + [_row(r) for r in ba] + [""]
    lines += ["## Por estado", ""]
    for uf, items in sorted(by_state.items(), key=lambda kv: (kv[0] == "—", kv[0])):
        lines += [f"### {uf} ({len(items)})", ""] + header + [_row(r) for r in items] + [""]

    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text("\n".join(lines), encoding="utf-8")
    return out


def export_archive(conn, out_path: Path | str) -> Path:
    """Exporta o banco inteiro: cada vaga com todos os campos, o payload bruto e o histórico de versões.

    É o formato para usar a base fora do app (planilha, notebook, outro sistema). Vagas encerradas incluídas.
    """
    import json
    out = Path(out_path)
    out.parent.mkdir(parents=True, exist_ok=True)
    jobs = []
    for r in conn.execute("SELECT * FROM jobs ORDER BY company_name, title"):
        d = {k: r[k] for k in r.keys()}
        for k in ("techs", "reasons", "locations", "sections", "metadata", "raw"):
            try:
                d[k] = json.loads(d[k]) if d.get(k) else ([] if k in ("techs", "reasons", "locations", "sections") else {})
            except (TypeError, ValueError):
                pass
        d["versions_history"] = [
            {"version_id": v["version_id"], "run_id": v["run_id"], "seen_at": v["seen_at"],
             "data": json.loads(v["data"]), "raw": json.loads(v["raw"]) if v["raw"] else None}
            for v in conn.execute("SELECT * FROM job_versions WHERE job_key=? ORDER BY version_id", (r["job_key"],))]
        jobs.append(d)
    payload = {"exported_at": __import__("datetime").datetime.now().isoformat(timespec="seconds"),
               "schema_version": conn.execute("PRAGMA user_version").fetchone()[0], "total": len(jobs), "jobs": jobs}
    out.write_text(json.dumps(payload, ensure_ascii=False, indent=1), encoding="utf-8")
    return out
