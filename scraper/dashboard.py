"""Gera out/dashboard.html (autossuficiente, sem internet) a partir do banco SQLite.

O painel é uma página só: lista (cards ou tabela), painéis de resumo e a página completa de cada vaga
(`#/vaga/<id>`). A lista vai leve no JSON principal; o registro completo de cada vaga (descrição em HTML,
seções, metadados, histórico de versões) vai em `<script type="application/json" id="rec-N">` e só é lido
quando a vaga é aberta. O payload bruto da fonte NÃO vai para o HTML (pesa dezenas de MB): ele fica no banco
e no arquivo `out/banco-vagas.json` (`python main.py --exportar`).
"""
from __future__ import annotations

import base64
import hashlib
import json
import sqlite3
from datetime import datetime
from pathlib import Path

from . import paths
from .filtering import is_brazil_location
from .match_v2 import assess, VERDICT_ORDER
from .models import Job

ROOT = paths.HOME
TEMPLATE = Path(__file__).resolve().parent / "templates" / "dashboard.html"

# campos do conteúdo de uma versão (o que o usuário lê); usados para dizer o que mudou entre versões
VERSION_FIELDS = (("title", "título"), ("location", "local"), ("locations", "locais"), ("area", "área"),
                  ("team", "time"), ("commitment", "tipo de contrato"), ("workplace_type", "modalidade"),
                  ("salary_text", "salário"), ("description", "descrição"), ("sections", "seções"))


def _j(s, default):
    try:
        return json.loads(s) if s else default
    except (TypeError, ValueError):
        return default


def _changes(prev: dict, cur: dict) -> list[str]:
    """Rótulos legíveis do que mudou de uma versão para a seguinte ('descrição (+120 caracteres)')."""
    out = []
    for key, label in VERSION_FIELDS:
        a, b = prev.get(key), cur.get(key)
        if a == b or (not a and not b):
            continue
        if key == "description":
            delta = len(b or "") - len(a or "")
            out.append(f"descrição ({'+' if delta >= 0 else '−'}{abs(delta)} caracteres)")
        else:
            out.append(label)
    if prev.get("description_html") != cur.get("description_html") and "descrição" not in " ".join(out):
        out.append("formatação da descrição")
    return out


def _versions(conn: sqlite3.Connection) -> dict[str, list[dict]]:
    """Histórico por vaga (só quem tem mais de uma versão): data de cada versão, o que mudou e o conteúdo antigo."""
    by: dict[str, list[dict]] = {}
    keys = [r[0] for r in conn.execute("SELECT job_key FROM jobs WHERE versions>1")]
    for k in keys:
        rows = conn.execute("SELECT version_id, run_id, seen_at, data FROM job_versions WHERE job_key=? "
                            "ORDER BY version_id", (k,)).fetchall()
        vs, prev = [], None
        for i, r in enumerate(rows):
            data = _j(r["data"], {})
            vs.append({"n": i + 1, "run_id": r["run_id"], "seen_at": r["seen_at"],
                       "changes": _changes(prev, data) if prev is not None else ["primeira captura"],
                       "data": data if i < len(rows) - 1 else None})   # a última é a atual: não repete o conteúdo
            prev = data
        by[k] = vs
    return by


def _linkedin_columns(meta: dict) -> dict:
    """Colunas da captura manual do LinkedIn que a aba do painel mostra (guardadas em `metadata` pelo importador)."""
    return {"fit": meta.get("aderência (planilha)", ""), "applicants": meta.get("candidaturas", ""),
            "seniority": meta.get("senioridade", ""), "notes": meta.get("observações", ""),
            "posted": meta.get("publicada_original", "")}


def collect(conn: sqlite3.Connection, cache: dict | None = None) -> dict:
    # O ranking é uma projeção reversível: não reclassifica snapshots históricos.
    match_profile = json.loads(paths.config_file('match_profile.json').read_text(encoding='utf-8'))
    profile_key = json.dumps(match_profile, sort_keys=True, ensure_ascii=False)
    used_cache_keys = set()
    runs = [dict(r) for r in conn.execute("SELECT * FROM runs ORDER BY run_id DESC LIMIT 30")]
    last = runs[0]["run_id"] if runs else 0
    versions = _versions(conn)
    jobs, records = [], []
    for r in conn.execute("SELECT * FROM jobs"):
        locs = _j(r["locations"], [])
        rid = len(records)
        meta = _j(r["metadata"], {})
        job = Job(company_id=r['company_id'] or '', company_name=r['company_name'] or '',
                  source=r['source'] or '', title=r['title'] or '', location=r['location'] or '',
                  area=r['area'] or '', workplace_type=r['workplace_type'] or '', description=r['description'] or '')
        signature = json.dumps(['match-v1', profile_key, job.title, job.location, job.area,
                                job.workplace_type, job.description], ensure_ascii=False)
        cache_key = hashlib.sha256(signature.encode('utf-8')).hexdigest()
        used_cache_keys.add(cache_key)
        match = cache.get(cache_key) if cache is not None else None
        if not isinstance(match, dict) or not {'verdict', 'score', 'track', 'confidence', 'components', 'warnings', 'evidence'} <= match.keys():
            match = assess(job, match_profile)
            if cache is not None:
                cache[cache_key] = match
        category = match['verdict']
        # As três classes antigas mantêm filtros e gráficos existentes compatíveis.
        verdict = ('ELIGIBLE' if category == 'ANÁLISE MANUAL' else
                   'MAYBE' if category in ('CONDICIONAL', 'INFORMAÇÕES INSUFICIENTES') else 'BLOCKED')
        reasons = ['Análise automática por regras; não é chance de contratação.',
                   f"Classificação: {category}; trilha: {match['track']}; confiança: {match['confidence']}."]
        reasons.extend(f"{name}: {points} pontos" for name, points in match['components'].items())
        reasons.extend(match['warnings'])
        reasons.extend(f"{e['skill']} ({e['kind']}): {e['text']}" for e in match['evidence'][:12])
        jobs.append({
            "key": r["job_key"], "rid": rid, "company_id": r["company_id"], "company": r["company_name"],
            "title": r["title"], "url": r["url"], "location": r["location"], "nloc": len(locs), "area": r["area"],
            "team": r["team"] or "", "workplace": r["workplace_type"], "commitment": r["commitment"] or "",
            "salary": r["salary_text"] or "", "posted_at": r["posted_at"] or "",
            "score": match['score'], "verdict": verdict, "techs": _j(r["techs"], []),
            "match_category": category, "match_order": VERDICT_ORDER[category], "match_track": match['track'],
            "match_confidence": match['confidence'],
            "first_seen": r["first_seen"], "last_seen": r["last_seen"], "closed_at": r["closed_at"] or "",
            "status": r["status"], "is_new": bool(last > 1 and r["first_run_id"] == last),
            "intl": not is_brazil_location(r["location"]), "versions": r["versions"] or 1,
            "li": _linkedin_columns(meta) if r["source"] == "linkedin" else None,
        })
        records.append({
            "key": r["job_key"], "source": r["source"], "job_id": r["job_id"], "reasons": reasons,
            "description": "" if r["description_html"] else (r["description"] or ""),
            "description_html": r["description_html"] or "", "sections": _j(r["sections"], []),
            "metadata": meta, "locations": locs, "apply_url": r["apply_url"] or "",
            "salary_min": r["salary_min"], "salary_max": r["salary_max"], "salary_currency": r["salary_currency"] or "",
            "salary_period": r["salary_period"] or "", "updated_at": r["updated_at_src"] or "",
            "deadline": r["deadline"] or "", "requisition_id": r["requisition_id"] or "",
            "detail_at": r["detail_at"] or "", "first_run_id": r["first_run_id"], "last_run_id": r["last_run_id"],
            "versions": versions.get(r["job_key"], []), "has_raw": bool(r["raw"]) and r["raw"] != "{}",
        })
    if cache is not None:
        for key in list(cache):
            if key not in used_cache_keys:
                del cache[key]
    companies = []
    for r in conn.execute(
        # o resultado MAIS RECENTE de cada empresa (não só o da última execução): numa execução parcial (refazer só as que
        # falharam) as outras fontes não podem virar "sem leitura"
        "SELECT c.company_id, c.name, c.board_url, c.adapter, rc.ok, rc.job_count, rc.error FROM companies c "
        "LEFT JOIN run_companies rc ON rc.company_id=c.company_id AND "
        "rc.run_id=(SELECT MAX(run_id) FROM run_companies WHERE company_id=c.company_id) "
        "ORDER BY c.composite_score DESC"):
        ok, count = (None if r["ok"] is None else bool(r["ok"])), r["job_count"]
        if r["adapter"] == "importado":                  # fonte importada de fora: não tem "execução"; mostra o que há no banco
            ok, count = True, sum(1 for j in jobs if j["company_id"] == r["company_id"] and j["status"] == "open")
        companies.append({"company_id": r["company_id"], "name": r["name"], "board_url": r["board_url"],
                          "ok": ok, "count": count, "error": r["error"], "imported": r["adapter"] == "importado"})
    return {"generated_at": datetime.now().isoformat(timespec="seconds"), "last_run_id": last,
            "runs": runs, "companies": companies, "jobs": jobs, "records": records}


def _font_css() -> str:
    """@font-face com Inter, Space Grotesk e JetBrains Mono embutidas (WOFF2 latino, ~200 KB): o painel segue offline."""
    faces = []
    for fam, fn, w in (("Inter Nevora", "Inter", "100 900"), ("Space Grotesk Nevora", "SpaceGrotesk", "300 700"),
                       ("JetBrains Mono Nevora", "JetBrainsMono", "100 800")):
        f = paths.BUNDLE / "assets" / "fonts" / f"{fn}.woff2"
        if f.exists():
            b64 = base64.b64encode(f.read_bytes()).decode("ascii")
            faces.append(f'@font-face{{font-family:"{fam}";font-weight:{w};font-display:swap;'
                         f'src:url(data:font/woff2;base64,{b64}) format("woff2")}}')
    return "\n".join(faces)


def _safe(s: str) -> str:
    """JSON dentro de <script>: `</` e o separador de linha U+2028 não podem aparecer cru."""
    return s.replace("</", "<\\/").replace("\u2028", "\\u2028").replace("\u2029", "\\u2029")


def build(conn: sqlite3.Connection, out_path: Path | str | None = None) -> Path:
    out = Path(out_path) if out_path else paths.OUT / "dashboard.html"
    out.parent.mkdir(parents=True, exist_ok=True)
    # Cache descartável: o hash inclui o perfil, a versão do motor e o texto da vaga.
    cache_path = out.parent / 'match-cache-v1.json'
    try:
        cache = json.loads(cache_path.read_text(encoding='utf-8'))
        if not isinstance(cache, dict):
            cache = {}
    except (OSError, ValueError):
        cache = {}
    data = collect(conn, cache)
    try:
        cache_tmp = cache_path.with_name(cache_path.name + '.tmp')
        cache_tmp.write_text(json.dumps(cache, ensure_ascii=False), encoding='utf-8')
        cache_tmp.replace(cache_path)
    except OSError:
        pass  # O painel continua funcionando se o cache não puder ser gravado.
    records = data.pop("records")
    payload = _safe(json.dumps(data, ensure_ascii=False))
    rec_tags = "\n".join(f'<script type="application/json" id="rec-{i}">{_safe(json.dumps(r, ensure_ascii=False))}</script>'
                         for i, r in enumerate(records))
    html = (TEMPLATE.read_text(encoding="utf-8").replace("/*__DATA__*/null", payload)
            .replace("/*__FONTS__*/", _font_css()).replace("<!--__RECORDS__-->", rec_tags))
    tmp = out.with_name(out.name + ".tmp")               # grava inteiro e troca: quem lê (painel embutido, navegador) nunca vê o arquivo pela metade
    tmp.write_text(html, encoding="utf-8")
    tmp.replace(out)
    return out
