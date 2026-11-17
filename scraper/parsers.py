"""Parsers puros de HTML -> Job. Não dependem de Selenium, por isso são testáveis offline.

Os seletores foram extraídos do DOM real capturado em 2026-11-16:
  * Lever:      jobs.lever.co/ciandt
  * Greenhouse: job-boards.greenhouse.io/linkedinzup
  * Stone:      jornada.stone.com.br/vagas-abertas (portal próprio)
"""
from __future__ import annotations

import html as html_lib
import json
import re
from bs4 import BeautifulSoup

from .models import Job
from .richtext import clean_html, html_to_text, section


def _txt(el) -> str:
    return re.sub(r"\s+", " ", el.get_text(" ", strip=True).replace("\xa0", " ")).strip() if el else ""


def _clean_trailing_dash(s: str) -> str:
    return s.strip(" —-–")


def _workplace(raw: str) -> str:
    r = raw.lower()
    if "remot" in r or "home" in r:
        return "remote"
    if "hybrid" in r or "híbrid" in r or "hibrid" in r:
        return "hybrid"
    if "on-site" in r or "onsite" in r or "presencial" in r:
        return "onsite"
    return ""


# ------------------------------------------------------------ campos do registro completo
def _iso_ms(ms) -> str:
    """Epoch em milissegundos (Lever) -> ISO 8601 em UTC."""
    try:
        from datetime import datetime, timezone
        return datetime.fromtimestamp(int(ms) / 1000, tz=timezone.utc).isoformat(timespec="seconds")
    except (TypeError, ValueError, OverflowError, OSError):
        return ""


def _num(v):
    try:
        return float(v) if v not in (None, "") else None
    except (TypeError, ValueError):
        return None


def _period(s) -> str:
    r = str(s or "").lower()
    for key, val in (("year", "year"), ("annual", "year"), ("month", "month"), ("hour", "hour"), ("week", "week"),
                     ("day", "day")):
        if key in r:
            return val
    return ""


_PERIOD_PT = {"year": "ano", "month": "mês", "hour": "hora", "week": "semana", "day": "dia"}


def salary_text(cur: str, lo, hi, period: str) -> str:
    """Faixa salarial legível: 'USD 80.000 – 120.000 / ano'."""
    def fmt(v):
        return f"{v:,.0f}".replace(",", ".") if v is not None else ""
    if lo is None and hi is None:
        return ""
    rng = fmt(lo) if hi is None or lo == hi else (fmt(hi) if lo is None else f"{fmt(lo)} – {fmt(hi)}")
    return " ".join(x for x in (cur, rng) if x) + (f" / {_PERIOD_PT[period]}" if period in _PERIOD_PT else "")


def apply_detail(j: Job, d: dict) -> None:
    """Aplica o resultado de um parser de detalhe: a descrição do detalhe vale mais que a da lista;
    os demais campos só preenchem lacunas; metadata e raw são mesclados."""
    for k, v in d.items():
        if k == "raw_detail":
            j.raw = {**j.raw, "detail": v}
        elif k == "metadata":
            j.metadata = {**j.metadata, **v}
        elif k in ("description", "description_html", "sections", "title") and v:
            setattr(j, k, v)
        elif v and not getattr(j, k, None):
            setattr(j, k, v)


# ---------------------------------------------------------------- Lever
def parse_lever_list(html: str, company_id: str, company_name: str) -> list[Job]:
    soup = BeautifulSoup(html, "lxml")
    jobs: list[Job] = []
    for group in soup.select("div.postings-group"):
        area = _txt(group.select_one(".posting-category-title"))
        for p in group.select("div.posting"):
            a = p.select_one("a.posting-title")
            if not a:
                continue
            title = _txt(a.select_one('[data-qa="posting-name"]')) or _txt(a.select_one("h5"))
            wp_raw = _clean_trailing_dash(_txt(a.select_one(".workplaceTypes")))
            jobs.append(Job(
                company_id=company_id, company_name=company_name, source="lever",
                job_id=p.get("data-qa-posting-id", ""),
                title=title, url=a.get("href", ""),
                location=_txt(a.select_one(".location")),
                commitment=_txt(a.select_one(".commitment")),
                area=area, workplace_type=_workplace(wp_raw),
            ))
    return jobs


def parse_lever_detail(html: str) -> dict:
    soup = BeautifulSoup(html, "lxml")
    cats = soup.select_one(".posting-categories")
    desc = " ".join(_txt(x) for x in soup.select('[data-qa="job-description"], [data-qa="closing-description"]'))
    out = {"description": desc}
    if cats:
        out["location"] = _txt(cats.select_one(".location"))
        out["area"] = _txt(cats.select_one(".department"))
        out["commitment"] = _txt(cats.select_one(".commitment"))
        out["workplace_type"] = _workplace(_clean_trailing_dash(_txt(cats.select_one(".workplaceTypes"))))
    return {k: v for k, v in out.items() if v}


def _html_text(raw: str) -> str:
    """HTML (às vezes escapado) -> texto limpo."""
    if not raw:
        return ""
    return _txt(BeautifulSoup(html_lib.unescape(raw), "lxml"))


def parse_lever_api(payload: list, company_id: str, company_name: str,
                    site_filters: dict | None = None) -> list[Job]:
    """Lever -> Job a partir da API pública (mode=json), com a mesma descrição da página.

    `site_filters` repete o recorte que era feito na URL (location/workplaceType).
    A descrição é montada de description + additional + lists, que é o que o detalhe mostra.
    Além dos campos principais guarda tudo que a API envia: datas, faixa salarial, todos os locais,
    seções (requisitos, benefícios) e o payload original em `raw`.
    """
    filters = {k.lower(): (v or "").lower() for k, v in (site_filters or {}).items()}
    jobs: list[Job] = []
    for p in payload or []:
        cats = p.get("categories") or {}
        loc = cats.get("location") or ""
        wp = (p.get("workplaceType") or "").lower()
        if filters.get("location") and filters["location"] not in loc.lower():
            continue
        if filters.get("workplacetype") and filters["workplacetype"] != wp:
            continue
        parts = [_html_text(p.get("description") or ""), _html_text(p.get("additional") or "")]
        sections = []
        for lst in p.get("lists") or []:
            parts.append(_html_text(lst.get("text") or ""))
            parts.append(_html_text(lst.get("content") or ""))
            s = section(_html_text(lst.get("text") or "") or "Detalhes", lst.get("content") or "")
            if s:
                sections.append(s)
        extra = section("Informações adicionais", p.get("additional") or "")
        if extra:
            sections.append(extra)
        desc = " ".join(x for x in parts if x)
        sal = p.get("salaryRange") or {}
        lo, hi, cur = _num(sal.get("min")), _num(sal.get("max")), sal.get("currency") or ""
        per = _period(sal.get("interval"))
        sal_txt = salary_text(cur, lo, hi, per) or _html_text(p.get("salaryDescription") or "")
        locs = [x for x in (cats.get("allLocations") or []) if x] or ([loc] if loc else [])
        meta = {k: v for k, v in (("country", p.get("country")), ("department", cats.get("department")),
                                  ("team", cats.get("team")), ("workplaceType", p.get("workplaceType"))) if v}
        jobs.append(Job(
            company_id=company_id, company_name=company_name, source="lever",
            job_id=p.get("id") or "",
            title=_clean_trailing_dash((p.get("text") or "").strip()),
            url=p.get("hostedUrl") or p.get("applyUrl") or "",
            location=loc,
            area=cats.get("team") or cats.get("department") or "",
            commitment=cats.get("commitment") or "",
            workplace_type=_workplace(wp or loc),
            description=desc,
            apply_url=p.get("applyUrl") or "", team=cats.get("team") or "", locations=locs,
            salary_text=sal_txt, salary_min=lo, salary_max=hi, salary_currency=cur, salary_period=per,
            posted_at=_iso_ms(p.get("createdAt")),
            description_html=clean_html(p.get("description") or p.get("opening") or ""),
            sections=sections, metadata=meta, raw=p,
        ))
    return jobs


def parse_ashby_api(payload: dict, company_id: str, company_name: str) -> list[Job]:
    """Ashby -> Job a partir do JSON público (/posting-api/job-board/{board}), guardando o registro completo."""
    jobs: list[Job] = []
    for j in payload.get("jobs", []) or []:
        if j.get("isListed") is False:
            continue
        loc = j.get("location") or ""
        extra = [x.get("location") for x in (j.get("secondaryLocations") or []) if x.get("location")]
        full_loc = loc + (f" / {', '.join(extra)}" if extra else "")
        desc = j.get("descriptionPlain") or _html_text(j.get("descriptionHtml") or "")
        wp = j.get("workplaceType") or ("remote" if j.get("isRemote") else "")
        comp = j.get("compensation") or {}
        lo = hi = None
        cur = per = ""
        for c in comp.get("summaryComponents") or []:
            if str(c.get("compensationType") or "").lower() == "salary":
                lo, hi = _num(c.get("minValue")), _num(c.get("maxValue"))
                cur, per = c.get("currencyCode") or "", _period(c.get("interval"))
                break
        sal_txt = (comp.get("scrapeableCompensationSalarySummary") or comp.get("compensationTierSummary")
                   or salary_text(cur, lo, hi, per))
        addr = (j.get("address") or {}).get("postalAddress") or {}
        addr_txt = ", ".join(str(x) for x in (addr.get("addressLocality"), addr.get("addressRegion"),
                                              addr.get("addressCountry")) if x)
        meta = {k: v for k, v in (("isRemote", j.get("isRemote")), ("workplaceType", j.get("workplaceType")),
                                  ("address", addr_txt)) if v not in (None, "")}
        jobs.append(Job(
            company_id=company_id, company_name=company_name, source="ashby",
            job_id=str(j.get("id") or ""),
            title=(j.get("title") or "").strip(),
            url=j.get("jobUrl") or j.get("applyUrl") or "",
            location=full_loc,
            area=j.get("department") or "",
            commitment=j.get("employmentType") or "",
            description=desc,
            workplace_type=_workplace(wp),
            apply_url=j.get("applyUrl") or "", team=j.get("team") or "",
            locations=[x for x in [loc] + extra if x],
            salary_text=sal_txt or "", salary_min=lo, salary_max=hi, salary_currency=cur, salary_period=per,
            posted_at=j.get("publishedAt") or "",
            description_html=clean_html(j.get("descriptionHtml") or ""),
            metadata=meta, raw=j,
        ))
    return jobs


# ----------------------------------------------------------- Greenhouse
_GH_ID = re.compile(r"/jobs/(\d+)")


def parse_greenhouse_list(html: str, company_id: str, company_name: str) -> list[Job]:
    soup = BeautifulSoup(html, "lxml")
    jobs: list[Job] = []
    for dept in soup.select("div.job-posts--table--department"):
        area = _txt(dept.select_one("h3"))
        for tr in dept.select("tr.job-post"):
            a = tr.select_one("a[href]")
            if not a:
                continue
            ps = a.select("p")
            href = a.get("href", "")
            m = _GH_ID.search(href)
            jobs.append(Job(
                company_id=company_id, company_name=company_name, source="greenhouse",
                job_id=m.group(1) if m else "",
                title=_txt(ps[0]) if ps else _txt(a),
                location=_txt(ps[1]) if len(ps) > 1 else "",
                url=href, area=area,
                workplace_type=_workplace(_txt(ps[1]) if len(ps) > 1 else ""),
            ))
    # layout sem agrupamento por departamento (boards antigos)
    if not jobs:
        for tr in soup.select("tr.job-post"):
            a = tr.select_one("a[href]")
            if a:
                ps = a.select("p")
                href = a.get("href", "")
                m = _GH_ID.search(href)
                jobs.append(Job(company_id=company_id, company_name=company_name, source="greenhouse",
                                job_id=m.group(1) if m else "", title=_txt(ps[0]) if ps else _txt(a),
                                location=_txt(ps[1]) if len(ps) > 1 else "", url=href))
    return jobs


def greenhouse_is_empty(html: str) -> bool:
    return bool(BeautifulSoup(html, "lxml").select_one(".job-posts__empty-state"))


def parse_greenhouse_detail(html: str) -> dict:
    soup = BeautifulSoup(html, "lxml")
    out = {
        "title": _txt(soup.select_one(".job__title h1")),
        "location": _txt(soup.select_one(".job__location")),
        "description": _txt(soup.select_one(".job__description")),
    }
    return {k: v for k, v in out.items() if v}


def parse_greenhouse_api(payload: dict, company_id: str, company_name: str) -> list[Job]:
    """Greenhouse -> Job a partir do JSON público (/v1/boards/{token}/jobs?content=true).

    O board HTML novo mostra no máximo 50 vagas e não tem "carregar mais"; a API traz todas
    e já inclui a descrição. O campo `content` vem com HTML escapado (&lt;h3&gt;), por isso o unescape.
    Guarda também datas, id de requisição, escritórios, faixa salarial (pay_input_ranges) e o payload original.
    """
    jobs: list[Job] = []
    for j in payload.get("jobs", []) or []:
        content = j.get("content") or ""
        desc = _txt(BeautifulSoup(html_lib.unescape(content), "lxml")) if content else ""
        deps = j.get("departments") or []
        meta = {m.get("name"): m.get("value") for m in (j.get("metadata") or []) if isinstance(m, dict)}
        loc = (j.get("location") or {}).get("name") or ""
        offices = [o.get("location") or o.get("name") for o in (j.get("offices") or []) if isinstance(o, dict)]
        locs = list(dict.fromkeys(x for x in [loc] + offices if x))
        rng = next((r for r in (j.get("pay_input_ranges") or []) if isinstance(r, dict)), {})
        lo, hi = _num(rng.get("min_cents")), _num(rng.get("max_cents"))
        lo = lo / 100 if lo is not None else None
        hi = hi / 100 if hi is not None else None
        cur = rng.get("currency_type") or ""
        sal_txt = salary_text(cur, lo, hi, "")
        if sal_txt and rng.get("blurb"):
            sal_txt += f" ({_html_text(rng['blurb'])})"
        extra_meta = {k: v for k, v in (("language", j.get("language")), ("internal_job_id", j.get("internal_job_id")),
                                        ("departments", [d.get("name") for d in deps if d.get("name")]),
                                        ("company_name", j.get("company_name"))) if v}
        extra_meta.update({k: v for k, v in meta.items() if k and v})
        jobs.append(Job(
            company_id=company_id, company_name=company_name, source="greenhouse",
            job_id=str(j.get("id") or ""),
            title=_clean_trailing_dash((j.get("title") or "").strip()),
            url=j.get("absolute_url") or "",
            location=loc,
            area=(deps[0].get("name") or "") if deps else "",
            commitment=meta.get("Employment Type") or "",
            description=desc,
            workplace_type=_workplace(loc),
            apply_url=j.get("absolute_url") or "", locations=locs,
            salary_text=sal_txt, salary_min=lo, salary_max=hi, salary_currency=cur,
            posted_at=j.get("first_published") or "", updated_at=j.get("updated_at") or "",
            deadline=j.get("application_deadline") or "",
            requisition_id=str(j.get("requisition_id") or ""),
            description_html=clean_html(content), metadata=extra_meta, raw=j,
        ))
    return jobs


# ---------------------------------------------------------------- Workday
def parse_workday_jobs(payload: dict, company_id: str, company_name: str, base_url: str) -> list[Job]:
    """Workday (CXS) -> Job. externalPath é único e serve de id e de caminho do detalhe."""
    jobs: list[Job] = []
    for p in payload.get("jobPostings", []) or []:
        path = p.get("externalPath") or ""
        url = (base_url.rstrip("/") + path) if path.startswith("/") else path
        loc = p.get("locationsText") or ""
        meta = {k: v for k, v in (("postedOn", p.get("postedOn")), ("bulletFields", p.get("bulletFields"))) if v}
        jobs.append(Job(
            company_id=company_id, company_name=company_name, source="workday",
            job_id=path or (p.get("title") or ""),
            title=(p.get("title") or "").strip(),
            url=url, location=loc, locations=[loc] if loc else [],
            workplace_type=_workplace(loc), metadata=meta, raw={"list": p},
        ))
    return jobs


def parse_workday_detail(payload: dict) -> dict:
    info = payload.get("jobPostingInfo") or {}
    desc = _html_text(info.get("jobDescription") or "")
    out = {"description": desc, "description_html": clean_html(info.get("jobDescription") or ""),
           "raw_detail": payload}
    if info.get("location"):
        out["location"] = _clean_trailing_dash(str(info["location"]).strip())
    if info.get("title"):
        out["title"] = str(info["title"]).strip()
    locs = [x for x in [info.get("location")] + list(info.get("additionalLocations") or []) if x]
    if locs:
        out["locations"] = locs
    if info.get("startDate"):
        out["posted_at"] = str(info["startDate"])
    if info.get("jobReqId"):
        out["requisition_id"] = str(info["jobReqId"])
    if info.get("externalUrl"):
        out["apply_url"] = str(info["externalUrl"])
    if info.get("timeType"):
        out["commitment"] = str(info["timeType"])
    country = info.get("country")
    country = country.get("descriptor") if isinstance(country, dict) else country
    meta = {k: v for k, v in (("remoteType", info.get("remoteType")), ("country", country),
                              ("canApply", info.get("canApply"))) if v not in (None, "")}
    if meta:
        out["metadata"] = meta
    return {k: v for k, v in out.items() if v}


# ---------------------------------------------------------------- Gupy
_NEXT_DATA = re.compile(r'<script id="__NEXT_DATA__" type="application/json">(.*?)</script>', re.S)


def _next_data(html: str) -> dict:
    m = _NEXT_DATA.search(html or "")
    if not m:
        return {}
    try:
        return json.loads(m.group(1))
    except ValueError:
        return {}


def parse_gupy_list(html: str, company_id: str, company_name: str, base_url: str) -> list[Job]:
    """Gupy -> Job a partir do HTML do portal (as vagas vêm no __NEXT_DATA__, sem Selenium).

    Estrutura observada em 2026-11-16 (ex.: alpargatas.gupy.io):
      pageProps.jobs[] = {id, title, type, department, quickApply,
                          workplace:{address:{city,stateShortName,country}, workplaceType}}
    O detalhe fica em {base}/jobs/{id}, com pageProps.job (description, publishedAt, jobSteps...).
    """
    data = _next_data(html)
    raw = ((data.get("props") or {}).get("pageProps") or {}).get("jobs") or []
    jobs: list[Job] = []
    base = base_url.rstrip("/")
    for j in raw:
        wp = j.get("workplace") or {}
        addr = wp.get("address") or {}
        city = (addr.get("city") or "").strip()
        state = (addr.get("stateShortName") or "").strip()
        country = (addr.get("country") or "").strip()
        loc = ", ".join(x for x in (city, state) if x)
        if not loc:
            loc = country
        elif country and country.lower() not in ("brasil", "brazil"):
            loc = f"{loc} - {country}"
        jid = str(j.get("id") or "")
        meta = {k: v for k, v in (("type", j.get("type")), ("quickApply", j.get("quickApply"))) if v not in (None, "")}
        jobs.append(Job(
            company_id=company_id, company_name=company_name, source="gupy",
            job_id=jid, title=(j.get("title") or "").strip(),
            url=f"{base}/jobs/{jid}" if jid else "",
            location=loc, locations=[loc] if loc else [], area=j.get("department") or "",
            workplace_type=_workplace(wp.get("workplaceType") or ""), metadata=meta, raw={"list": j},
        ))
    return jobs


def parse_gupy_detail(html: str) -> dict:
    """Detalhe da vaga no Gupy (pageProps.job): descrição, responsabilidades, requisitos, etapas e datas."""
    data = _next_data(html)
    job = ((data.get("props") or {}).get("pageProps") or {}).get("job") or {}
    if not job:
        return {}
    parts = [job.get(k) or "" for k in ("description", "responsibilities", "prerequisites", "skills")]
    out = {"description": " ".join(_html_text(p) for p in parts if p), "raw_detail": job}
    if job.get("name"):
        out["title"] = str(job["name"]).strip()
    secs = [section("Descrição", job.get("description") or ""),
            section("Responsabilidades e atribuições", job.get("responsibilities") or ""),
            section("Requisitos e qualificações", job.get("prerequisites") or ""),
            section("Experiências relevantes", job.get("relevantExperiences") or ""),
            section("Competências", job.get("skills") if isinstance(job.get("skills"), str) else "")]
    steps = [s.get("name") for s in sorted(job.get("jobSteps") or [], key=lambda s: s.get("order", 0)) if s.get("name")]
    if steps:
        secs.append({"title": "Etapas do processo seletivo",
                     "html": "<ol>" + "".join(f"<li>{html_lib.escape(s)}</li>" for s in steps) + "</ol>"})
    secs = [s for s in secs if s]
    out["description_html"] = clean_html(job.get("description") or "") or (secs[0]["html"] if secs else "")
    out["sections"] = [s for s in secs if s["title"] != "Descrição"]
    out["posted_at"] = job.get("publishedAt") or ""
    out["deadline"] = job.get("expiresAt") or job.get("registerEndDate") or ""
    out["requisition_id"] = str(job.get("code") or "")
    addr = ", ".join(x for x in (job.get("addressCity"), job.get("addressStateShortName"),
                                 job.get("addressCountry")) if x)
    out["metadata"] = {k: v for k, v in (
        ("jobType", job.get("jobType")), ("publicationType", job.get("publicationType")), ("reason", job.get("reason")),
        ("pcd", job.get("handicapped")), ("quickApply", job.get("quickApply")), ("status", job.get("status")),
        ("address", addr), ("empresa", (job.get("careerPage") or {}).get("name")), ("videoUrl", job.get("videoUrl")),
        ("registerEndDate", job.get("registerEndDate"))) if v not in (None, "")}
    if job.get("workplaceType"):
        out["workplace_type"] = _workplace(str(job["workplaceType"]))
    return {k: v for k, v in out.items() if v not in (None, "", [], {})}


# ---------------------------------------------------------------- Stone
_STONE_ID = re.compile(r"/oportunidades/(?:.*-)?(\d+)$")

def parse_stone_list(html: str, company_id: str, company_name: str, base_url: str = "") -> list[Job]:
    """DOM real (2026-11-16): cada vaga é <a href="/times/.../oportunidades/ID"><article>...</article></a>.
    O 1º <article> da página é um wrapper (contém os cards) e é ignorado. O título aparece duplicado
    (bloco mobile + desktop): usamos o primeiro e deduplicamos por URL/(título, local)."""
    soup = BeautifulSoup(html, "lxml")
    jobs: list[Job] = []
    seen: set[str] = set()
    for art in soup.select("article"):
        if art.select_one("article"):
            continue
        h3 = next((_txt(h) for h in art.select("h3") if _txt(h)), "")
        if not h3:
            continue
        spans = [_txt(x) for x in art.select("span")]
        spans = [x for x in spans if x and x.lower() != "saiba mais"]
        location = spans[0] if spans else ""
        area = spans[1] if len(spans) > 1 else ""
        a = art.find_parent("a")
        href = a.get("href", "") if a else ""
        if href.startswith("/") and base_url:
            href = base_url.rstrip("/") + href
        key = href or f"{h3}|{location}"
        if key in seen:
            continue
        seen.add(key)
        m = _STONE_ID.search(href)
        wp = _workplace(h3) or _workplace(location)
        jobs.append(Job(company_id=company_id, company_name=company_name, source="stone_portal",
                        job_id=m.group(1) if m else "", title=h3, url=href,
                        location=location, area=area, workplace_type=wp))
    return jobs


def parse_stone_detail(html: str) -> dict:
    """Detalhe: <h1> título; o avô do h1 contém a linha de metadados (ex.: 'Tecnologia Home Office Brasil - BR')
    seguida das seções h2 (Sobre a Stone / O que esperamos de você / ...)."""
    soup = BeautifulSoup(html, "lxml")
    h1 = soup.select_one("h1")
    if not h1:
        return {}
    box = h1.parent.parent if h1.parent and h1.parent.parent else h1.parent
    title = _txt(h1)
    text = _txt(box)
    desc = text.replace(title, "", 1).strip()
    out = {"description": desc}
    wp = _workplace(desc[:80])
    if wp:
        out["workplace_type"] = wp
    h1.extract()                                            # o título já está no registro
    out["description_html"] = clean_html(str(box))
    return out


