"""Relatórios derivados do banco (sem Selenium): exportação do banco em JSON."""
from __future__ import annotations

import sqlite3
from datetime import datetime
from pathlib import Path

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
