"""Importa vagas captadas por fora (LinkedIn, planilha, outro Claude/navegador) para o banco de vagas.

Aceita JSON (lista, ou objeto com `jobs`/`vagas`/`results`), CSV/TSV e tabela Markdown. Os nomes das colunas
são reconhecidos em português e inglês (`cargo`/`title`, `empresa`/`company`, `link`/`url`...). Tudo que não
tem coluna própria vai para os metadados da vaga e a linha original inteira fica em `raw`: nada se perde.

As vagas entram como fonte `linkedin` (ou o rótulo escolhido), passam pela mesma nota e pelo mesmo registro
completo das demais e NÃO encerram vagas antigas (um arquivo importado é um recorte, não uma varredura inteira).
"""
from __future__ import annotations

import csv
import hashlib
import html as html_lib
import io
import json
import re
import unicodedata
from datetime import datetime, timedelta
from pathlib import Path

from .models import Job
from .parsers import _workplace, salary_text

# nome normalizado da coluna -> campo do registro
ALIASES = {
    "title": ("title", "cargo", "vaga", "job_title", "titulo", "nome_da_vaga", "position", "role"),
    "company": ("company", "empresa", "company_name", "organizacao", "employer", "nome_da_empresa"),
    "location": ("location", "local", "localizacao", "cidade", "local_da_vaga", "city"),
    "url": ("url", "link", "job_url", "linkedin_url", "link_da_vaga", "href", "job_link"),
    "job_id": ("job_id", "id", "linkedin_id", "id_da_vaga"),
    "posted": ("posted", "posted_at", "publicada", "publicada_em", "data", "publicacao", "data_publicacao",
               "posted_date", "listed_at", "data_de_publicacao"),
    "description": ("description", "descricao", "detalhes", "resumo", "sobre_a_vaga", "job_description",
                    "requisitos_stack", "requisitos", "stack"),
    "workplace": ("workplace", "workplace_type", "modalidade", "modelo", "modelo_de_trabalho", "remoto", "work_model",
                  "modelo_contrato", "modelo_e_contrato"),
    "commitment": ("employment_type", "tipo", "contrato", "tipo_de_contrato", "jobtype", "tipo_de_emprego", "commitment"),
    "seniority": ("seniority", "nivel", "senioridade", "experience_level", "nivel_de_experiencia"),
    "salary": ("salary", "salario", "remuneracao", "faixa_salarial", "compensation", "pay", "salario_beneficios"),
    "applicants": ("applicants", "candidatos", "num_applicants", "numero_de_candidatos", "candidaturas"),
    "fit": ("aderencia", "fit", "match", "afinidade"),
    "notes": ("observacoes", "observacao", "notas", "notes", "obs", "comentarios"),
}
LIST_KEYS = ("jobs", "vagas", "results", "resultados", "items", "data", "listings")


def _norm_key(k: str) -> str:
    s = unicodedata.normalize("NFKD", str(k)).encode("ascii", "ignore").decode().lower()
    return re.sub(r"[^a-z0-9]+", "_", s).strip("_")


def _slug(s: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", unicodedata.normalize("NFKD", s).encode("ascii", "ignore").decode().lower()).strip("-")


# ------------------------------------------------------------------ leitura de arquivo
def read_file(path: Path | str) -> tuple[list[dict], dict]:
    """(linhas, info): `info` traz o que o arquivo diz sobre si (`capturado_em`, `fonte`, `origem`)."""
    p = Path(path)
    text = p.read_text(encoding="utf-8-sig", errors="replace")
    info: dict = {}
    t = text.strip()
    if p.suffix.lower() == ".json" or t[:1] in "[{":
        try:
            data = json.loads(t)
        except ValueError as e:
            raise ValueError(f"JSON inválido: {e}") from e
        if isinstance(data, dict):
            info = {k: data[k] for k in ("capturado_em", "captured_at", "fonte", "origem", "source") if data.get(k)}
        return _rows_from_json(data), info
    return rows_from_text(text, p.suffix.lower()), info


def read_rows(path: Path | str) -> list[dict]:
    return read_file(path)[0]


def rows_from_text(text: str, suffix: str = "") -> list[dict]:
    t = text.strip()
    if not t:
        raise ValueError("arquivo vazio")
    if suffix == ".json" or t[0] in "[{":
        try:
            data = json.loads(t)
        except ValueError as e:
            raise ValueError(f"JSON inválido: {e}") from e
        return _rows_from_json(data)
    if "|" in t.splitlines()[0] and suffix in (".md", ".markdown", ".txt", ""):
        rows = _rows_from_markdown(t)
        if rows:
            return rows
    delim = "\t" if suffix == ".tsv" or t.splitlines()[0].count("\t") > t.splitlines()[0].count(";") else (";" if t.splitlines()[0].count(";") > t.splitlines()[0].count(",") else ",")
    rows = [dict(r) for r in csv.DictReader(io.StringIO(t), delimiter=delim)]
    if not rows:
        raise ValueError("não encontrei linhas de vagas (esperava JSON, CSV ou tabela Markdown)")
    return rows


def _rows_from_json(data) -> list[dict]:
    if isinstance(data, list):
        return [r for r in data if isinstance(r, dict)]
    if isinstance(data, dict):
        for k in LIST_KEYS:
            if isinstance(data.get(k), list):
                return [r for r in data[k] if isinstance(r, dict)]
        if any(_norm_key(k) in sum(ALIASES.values(), ()) for k in data):      # um objeto = uma vaga
            return [data]
    raise ValueError("JSON sem lista de vagas (procurei as chaves: " + ", ".join(LIST_KEYS) + ")")


def _rows_from_markdown(text: str) -> list[dict]:
    lines = [ln.strip() for ln in text.splitlines() if ln.strip().startswith("|")]
    if len(lines) < 3:
        return []
    cut = lambda ln: [c.strip() for c in ln.strip().strip("|").split("|")]          # noqa: E731
    head = cut(lines[0])
    rows = []
    for ln in lines[2:] if set(lines[1].replace("|", "").replace(":", "").replace("-", "").strip()) == set() else lines[1:]:
        cells = cut(ln)
        if len(cells) == len(head):
            rows.append(dict(zip(head, cells)))
    return rows


# ------------------------------------------------------------------ linha -> Job
def _pick(row_norm: dict, field: str):
    for a in ALIASES[field]:
        v = row_norm.get(a)
        if v not in (None, "", [], {}):
            return v
    return ""


def _text(v) -> str:
    if isinstance(v, (list, tuple)):
        return ", ".join(_text(x) for x in v if x not in (None, ""))
    if isinstance(v, dict):
        return ", ".join(f"{k}: {_text(x)}" for k, x in v.items() if x not in (None, ""))
    return re.sub(r"\s+", " ", str(v)).strip() if not isinstance(v, str) else v.strip()


def _linkedin_id(url: str, explicit: str) -> str:
    if explicit and re.fullmatch(r"\d{6,}", str(explicit).strip()):
        return str(explicit).strip()
    m = re.search(r"/jobs/view/(?:[^/?]*-)?(\d{6,})", url or "") or re.search(r"currentJobId=(\d+)", url or "")
    return m.group(1) if m else ""


def parse_posted(value: str, base: datetime | None = None) -> str:
    """'2026-11-10', '10/11/2026', 'há 3 dias', '2 weeks ago' -> data ISO (YYYY-MM-DD); vazio se não entender."""
    s = _text(value).lower()
    if not s:
        return ""
    base = base or datetime.now()
    m = re.match(r"(\d{4})-(\d{2})-(\d{2})", s)
    if m:
        return f"{m.group(1)}-{m.group(2)}-{m.group(3)}"
    m = re.match(r"(\d{1,2})/(\d{1,2})/(\d{4})", s)
    if m:
        return f"{m.group(3)}-{int(m.group(2)):02d}-{int(m.group(1)):02d}"
    if re.search(r"\b(hoje|today|agora|just now)\b|\bh[aá]\s*\d+\s*(h|hora|horas|min|minuto|minutos)\b|\d+\s*(h|hour|minute|min)s?\s*ago", s):
        return base.strftime("%Y-%m-%d")
    if re.search(r"\bontem\b|yesterday", s):
        return (base - timedelta(days=1)).strftime("%Y-%m-%d")
    m = re.search(r"(\d+)\s*(dia|day|semana|week|m[eê]s|month|ano|year)", s)
    if m:
        n, unit = int(m.group(1)), m.group(2)
        days = 1 if unit.startswith(("dia", "day")) else 7 if unit.startswith(("sem", "week")) else \
            30 if unit.startswith(("mes", "mês", "month")) else 365
        return (base - timedelta(days=n * days)).strftime("%Y-%m-%d")
    return ""


_MONEY = re.compile(r"(r\$|us\$|usd|brl|eur|€|\$)\s?\d", re.I)
_SKIP = {"", "—", "-", "–", "n/a", "na", "não informado", "nao informado"}


def _clean(v) -> str:
    s = _text(v)
    return "" if s.lower() in _SKIP else s


def _split_model(raw: str) -> tuple[str, str]:
    """'Híbrido (2-3 dias presenciais) · integral' -> ('Híbrido (2-3 dias presenciais)', 'integral')."""
    parts = [x.strip() for x in re.split(r"\s[·|]\s", raw, maxsplit=1)]
    return (parts[0], parts[1] if len(parts) > 1 else "")


def to_job(row: dict, source: str = "linkedin", captured: datetime | None = None) -> Job | None:
    norm = {_norm_key(k): v for k, v in row.items()}
    title, company = _text(_pick(norm, "title")), _text(_pick(norm, "company"))
    if not title:
        return None
    url = _text(_pick(norm, "url"))
    m = re.search(r'HYPERLINK\("([^"]+)"', url)                 # célula de planilha: =HYPERLINK("url";"abrir")
    url = m.group(1) if m else url
    location = _text(_pick(norm, "location"))
    jid = _linkedin_id(url, _text(_pick(norm, "job_id")))
    if not jid:                                   # sem id do LinkedIn: impressão digital estável da vaga
        jid = hashlib.sha1(f"{company}|{title}|{location}".lower().encode("utf-8")).hexdigest()[:12]
    desc = _clean(_pick(norm, "description"))
    wp_raw, commitment = _text(_pick(norm, "workplace")), _text(_pick(norm, "commitment"))
    if "·" in wp_raw or " | " in wp_raw:
        wp_raw, extra_commit = _split_model(wp_raw)
        commitment = commitment or extra_commit
    sal_raw = _clean(_pick(norm, "salary"))
    sal = sal_raw if _MONEY.search(sal_raw) else ""
    posted_raw = _text(_pick(norm, "posted"))
    used = {a for f in ALIASES.values() for a in f}
    meta = {k: _text(v) for k, v in norm.items()
            if k not in used and k not in ("", "n", "score", "order") and v not in (None, "", [], {})}
    if posted_raw and not parse_posted(posted_raw, captured):
        meta["publicada_texto"] = posted_raw
    if posted_raw:
        meta["publicada_original"] = posted_raw
    for f, label in (("seniority", "senioridade"), ("applicants", "candidaturas"), ("fit", "aderência (planilha)"),
                     ("notes", "observações")):
        v = _clean(_pick(norm, f))
        if v:
            meta[label] = v
    if sal_raw:
        meta["salário / benefícios"] = sal_raw
    meta["importado"] = "sim"
    sections = []
    if sal_raw and not sal:                      # texto de benefícios (sem valor em dinheiro)
        sections.append({"title": "Benefícios", "html": f"<p>{html_lib.escape(sal_raw)}</p>"})
    paragraphs = [par.strip() for par in re.split(r"\n{2,}|\r\n\r\n", desc) if par.strip()]
    job = Job(company_id=source, company_name=company or "Empresa não informada", source=source, job_id=jid,
              title=title, url=url or (f"https://www.linkedin.com/jobs/view/{jid}/" if jid.isdigit() else ""),
              location=location, workplace_type=_workplace(wp_raw) or _workplace(location) or _workplace(title),
              commitment=commitment, description=desc, apply_url=url, locations=[location] if location else [],
              salary_text=sal, posted_at=parse_posted(posted_raw, captured),
              description_html="".join(f"<p>{html_lib.escape(par)}</p>" for par in paragraphs),
              sections=sections, metadata=meta, raw={"import": row},
              detail_at=(captured or datetime.now()).isoformat(timespec="seconds") if desc else "")
    return job


def parse_file(path: Path | str, source: str | None = None) -> list[Job]:
    p = Path(path)
    rows, info = read_file(p)
    captured = None
    stamp = info.get("capturado_em") or info.get("captured_at")
    if stamp:
        try:
            captured = datetime.fromisoformat(str(stamp)[:19])
        except ValueError:
            captured = None
    captured = captured or datetime.fromtimestamp(p.stat().st_mtime)
    src = source or _slug(str(info.get("fonte") or info.get("source") or "linkedin")) or "linkedin"
    jobs = []
    for row in rows:
        j = to_job(row, src, captured)
        if j:
            if info.get("origem"):
                j.metadata.setdefault("origem", str(info["origem"]))
            jobs.append(j)
    if not jobs:
        raise ValueError("nenhuma vaga com título encontrada no arquivo")
    return jobs


def run_import(path: Path | str, source: str | None = None) -> dict:
    """Lê o arquivo, dá nota (profile.json), grava no banco e regenera o painel.

    Devolve {"lidas", "novas", "atualizadas", "fonte", "painel"}. Levanta ValueError se o arquivo não servir.
    """
    from . import dashboard, db, paths, reports
    from .filtering import score_job
    jobs = parse_file(path, source)
    profile = json.loads(paths.config_file("profile.json").read_text(encoding="utf-8"))
    for j in jobs:
        score_job(j, profile)
    src = jobs[0].source
    label = {"linkedin": "LinkedIn"}.get(src, src)
    conn = db.connect()
    try:
        res = db.save_import(conn, jobs, [{"company_id": src, "name": f"{label} (importado)", "adapter": "importado",
                                           "board_url": "", "composite_score": None}])
        out = dashboard.build(conn)
        reports.build_presenciais(conn, paths.OUT / "presenciais.md")
    finally:
        conn.close()
    return {"lidas": len(jobs), "novas": res["novas"], "atualizadas": res["atualizadas"], "fonte": src, "painel": str(out)}
