"""Gera out/dashboard.html (autossuficiente, sem internet) a partir do banco SQLite."""
from __future__ import annotations

import json
import sqlite3
from datetime import datetime
from pathlib import Path

from . import paths
from .filtering import is_brazil_location

ROOT = paths.HOME
TEMPLATE = Path(__file__).resolve().parent / "templates" / "dashboard.html"


def collect(conn: sqlite3.Connection) -> dict:
    runs = [dict(r) for r in conn.execute("SELECT * FROM runs ORDER BY run_id DESC LIMIT 30")]
    last = runs[0]["run_id"] if runs else 0
    jobs = []
    for r in conn.execute("SELECT * FROM jobs"):
        jobs.append({
            "key": r["job_key"], "company_id": r["company_id"], "company": r["company_name"], "title": r["title"],
            "url": r["url"], "location": r["location"], "area": r["area"], "workplace": r["workplace_type"],
            "score": r["score"], "verdict": r["verdict"], "techs": json.loads(r["techs"] or "[]"),
            "reasons": json.loads(r["reasons"] or "[]"), "first_seen": r["first_seen"], "last_seen": r["last_seen"],
            "status": r["status"], "is_new": bool(last > 1 and r["first_run_id"] == last),
            "intl": not is_brazil_location(r["location"]),
            "description": (r["description"] or "")[:3000],
        })
    companies = []
    for r in conn.execute(
        "SELECT c.company_id, c.name, c.board_url, rc.ok, rc.job_count, rc.error FROM companies c "
        "LEFT JOIN run_companies rc ON rc.company_id=c.company_id AND rc.run_id=? ORDER BY c.composite_score DESC", (last,)):
        companies.append({"company_id": r["company_id"], "name": r["name"], "board_url": r["board_url"],
                          "ok": None if r["ok"] is None else bool(r["ok"]), "count": r["job_count"], "error": r["error"]})
    return {"generated_at": datetime.now().isoformat(timespec="seconds"), "last_run_id": last,
            "runs": runs, "companies": companies, "jobs": jobs}


def _font_css() -> str:
    """@font-face com Inter, Space Grotesk e JetBrains Mono embutidas (WOFF2 latino, ~200 KB): o painel segue offline."""
    import base64
    faces = []
    for fam, fn, w in (("Inter Nevora", "Inter", "100 900"), ("Space Grotesk Nevora", "SpaceGrotesk", "300 700"),
                       ("JetBrains Mono Nevora", "JetBrainsMono", "100 800")):
        f = paths.BUNDLE / "assets" / "fonts" / f"{fn}.woff2"
        if f.exists():
            b64 = base64.b64encode(f.read_bytes()).decode("ascii")
            faces.append(f'@font-face{{font-family:"{fam}";font-weight:{w};font-display:swap;'
                         f'src:url(data:font/woff2;base64,{b64}) format("woff2")}}')
    return "\n".join(faces)


def build(conn: sqlite3.Connection, out_path: Path | str | None = None) -> Path:
    out = Path(out_path) if out_path else paths.OUT / "dashboard.html"
    out.parent.mkdir(parents=True, exist_ok=True)
    payload = json.dumps(collect(conn), ensure_ascii=False).replace("</", "<\\/")
    html = TEMPLATE.read_text(encoding="utf-8").replace("/*__DATA__*/null", payload).replace("/*__FONTS__*/", _font_css())
    out.write_text(html, encoding="utf-8")
    return out
