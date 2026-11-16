#!/usr/bin/env python3
"""Busca vagas no LinkedIn Jobs usando a SUA sessão já logada do Chrome (via CDP), sem login novo.

Modo seguro (padrão): 2 páginas por busca, até 50 vagas, só as últimas 24h (sortBy=DD), sem abrir
detalhe (0 requests por vaga), pausas de 25–55 s entre páginas e 60–120 s entre buscas, no máximo
1 execução por dia (--force para repetir) e parada imediata em CAPTCHA/checkpoint. Somente leitura:
nunca clica em candidatura, mensagem ou perfil.

Uso:
    python launch_chrome.py            # 1) abre o Chrome de depuração com a sua sessão
    python linkedin_jobs.py            # 2) busca (modo seguro) e gera o relatório
    python linkedin_jobs.py --probe "https://www.linkedin.com/jobs/search/?keywords=Salesforce"
    python linkedin_jobs.py --self-test

Saídas em out/: linkedin-report.md, linkedin-jobs.json, status.json, last-run.json, run.log
"""
from __future__ import annotations

import argparse
import json
import logging
import os
import random
import re
import sys
import time
import unicodedata
from datetime import datetime
from pathlib import Path
from urllib.parse import urlencode

HERE = Path(__file__).resolve().parent
OUT = HERE / "out"
DEBUG = OUT / "debug"

CDP_URL = os.environ.get("LINKEDIN_CDP", "http://localhost:9222")
MIN_DELAY, MAX_DELAY = 7.0, 22.0

log = logging.getLogger("linkedin")

# modo seguro (padrão): 2 páginas, até 50 vagas, sem abrir detalhe, só últimas 24h
SAFE_PAGES = 2
SAFE_MAX_JOBS = 50
SAFE_TPR = "r86400"
PAGE_PAUSE = (25.0, 55.0)     # entre páginas
SEARCH_PAUSE = (60.0, 120.0)  # entre buscas
STATUS = OUT / "status.json"
LAST_RUN = OUT / "last-run.json"


class Blocked(Exception):
    """Desafio de segurança/CAPTCHA: parar na hora, sem tentar contornar."""


def write_status(**data) -> None:
    """Grava out/status.json para o app mostrar o progresso no player."""
    try:
        OUT.mkdir(parents=True, exist_ok=True)
        payload = {"updated_at": datetime.now().isoformat(timespec="seconds"), **data}
        tmp = OUT / ".status.tmp"
        tmp.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
        tmp.replace(STATUS)
    except Exception:
        pass


def last_run() -> dict | None:
    try:
        d = json.loads(LAST_RUN.read_text(encoding="utf-8"))
        return d if d.get("date") == datetime.now().strftime("%Y-%m-%d") else None
    except Exception:
        return None


def safe_pause(page=None, label: str = "", window: tuple[float, float] = PAGE_PAUSE) -> None:
    secs = random.uniform(*window)
    log.info("pausa de segurança: %.0fs (%s)", secs, label or "respiro")
    time.sleep(secs)
    if page:
        try:
            w = page.evaluate("() => Math.max(window.innerWidth, 800)")
            h = page.evaluate("() => Math.max(window.innerHeight, 600)")
            page.mouse.move(random.randint(40, int(w) - 40), random.randint(80, int(h) - 80))
        except Exception:
            pass


# ------------------------------------------------------------------ perfil alvo
PROFILE = {
    "seniority": ["senior", "sênior", "sr", "sr.", "staff", "lead", "lider", "líder", "principal",
                  "architect", "arquiteto", "especialista", "specialist", "tech lead"],
    "junior": ["junior", "júnior", "jr", "estagi", "intern", "trainee", "aprendiz"],
    "pleno": ["pleno", "mid level", "mid-level", "midlevel", "ii", "intermediate"],
    "techs": {
        "SALESFORCE": r"salesforce|apex|\blwc\b|lightning web|soql|sfdx|flosum|visualforce|sales cloud|service cloud",
        "AWS": r"\baws\b|amazon web services|\blambda\b|dynamodb|\bs3\b|cloudfront|api gateway|step functions",
        "GO": r"\bgolang\b|\bgo\b(?=\s*(?:developer|engineer|lang|backend|programmer))|\bgo\b\s*/",
        "PYTHON": r"\bpython\b",
        "NODE": r"node\.?js|\bnode\b",
        "ANGULAR": r"\bangular\b",
        "JAVA": r"\bjava\b|spring boot|spring\b",
        "DOTNET": r"\.net\b|c#|dotnet",
        "KOTLIN": r"\bkotlin\b",
        "REACT": r"\breact\b",
        "JAVASCRIPT": r"javascript|typescript",
        "SQL": r"\bsql\b|soql|\boracle\b|postgres",
    },
    "strengths_map": {
        "SALESFORCE": "Salesforce (Apex, LWC, SOQL, SFDX, Flosum, Jest) — seu stack principal",
        "AWS": "AWS (Lambda, DynamoDB, S3, CloudFront, API Gateway) + certificação Solutions Architect Associate",
        "GO": "Go/Golang em produção",
        "PYTHON": "Python",
        "NODE": "Node.js",
        "ANGULAR": "Angular",
        "SQL": "SQL/banco relacional",
    },
    "blocked_countries": ["us only", "usa only", "united states only", "canada only", "must be located in the us",
                          "must reside in the us", "eu only", "europe only", "uk only", "india only"],
    "latam_ok": ["brazil", "brasil", "latam", "latin america", "south america", "americas", "worldwide", "anywhere"],
    "sp_terms": ["são paulo", "sao paulo", "santo andré", "santo andre", "são bernardo", "sao bernardo",
                 "abc paulista", "osasco", "barueri", "campinas"],
    "certs": {
        "AWS_CERT": r"aws certified|aws certification|solutions architect associate|aws certified solutions architect",
        "SF_CERT": r"salesforce certified|salesforce certification|salesforce administrator|salesforce admin",
    },
}

# buscas padrão (as 3 pedidas + 1 passe internacional remoto)
SEARCHES = [
    {"id": "salesforce", "label": "Salesforce Sênior (BR)",
     "keywords": '("Salesforce Developer" OR "Salesforce Engineer" OR LWC OR Apex) AND (Senior OR Sênior)',
     "location": "Brazil", "tpr": "r604800", "wt": "2,3"},
    {"id": "eng", "label": "Software/Backend Engineer Sênior (Go/AWS/Python)",
     "keywords": '("Software Engineer" OR "Backend Engineer") AND (Go OR Golang OR AWS OR Python) AND (Senior OR Sênior)',
     "location": "Brazil", "tpr": "r604800", "wt": "2,3"},
    {"id": "arch", "label": "Solutions Architect / Technical Lead (Salesforce/AWS)",
     "keywords": '("Solutions Architect" OR "Technical Lead") AND (Salesforce OR AWS)',
     "location": "Brazil", "tpr": "r604800", "wt": "2,3"},
    {"id": "intl", "label": "Remoto internacional (EUR)",
     "keywords": '("Salesforce" OR "Golang" OR "AWS") AND (Senior OR Sênior) AND (Remote)',
     "location": "European Union", "tpr": "r604800", "wt": "2"},
]

CARD_SEL = ("li[data-occludable-job-id], div.job-card-container, li.jobs-search-results__list-item, "
            "div.job-search-card, li.scaffold-layout__list-item")
DETAIL_SEL = ("#job-details, .jobs-description__content, .jobs-description-content__text, "
              ".jobs-search__job-details--container, .show-more-less-html__markup, "
              ".description__text, .top-card-layout__title")


# ------------------------------------------------------------------ util
def norm(s: str) -> str:
    s = unicodedata.normalize("NFKD", (s or "").lower())
    return "".join(c for c in s if not unicodedata.combining(c))


def clean(s: str) -> str:
    return re.sub(r"\s+", " ", (s or "").replace("\xa0", " ")).strip()


def detect(text: str) -> dict[str, bool]:
    n = norm(text)
    return {k: bool(re.search(rx, n)) for k, rx in PROFILE["techs"].items()}


# ------------------------------------------------------------------ browser
def connect(pw):
    from playwright.sync_api import Error as PWError
    try:
        browser = pw.chromium.connect_over_cdp(CDP_URL)
    except PWError as e:
        raise SystemExit(
            f"Não consegui falar com o Chrome em {CDP_URL}.\n"
            "Rode primeiro:  python launch_chrome.py\n"
            f"(detalhe técnico: {e})")
    ctx = browser.contexts[0] if browser.contexts else browser.new_context()
    page = ctx.pages[0] if ctx.pages else ctx.new_page()
    page.set_default_timeout(20000)
    return browser, ctx, page


def human_delay(page=None, label: str = "") -> None:
    secs = random.uniform(MIN_DELAY, MAX_DELAY)
    log.info("aguardando %.1fs%s", secs, f" ({label})" if label else "")
    time.sleep(secs)
    if page:
        try:
            w = page.evaluate("() => Math.max(window.innerWidth, 800)")
            h = page.evaluate("() => Math.max(window.innerHeight, 600)")
            page.mouse.move(random.randint(40, int(w) - 40), random.randint(80, int(h) - 80))
        except Exception:
            pass


def gradual_scroll(page, steps: int | None = None) -> None:
    steps = steps or random.randint(4, 8)
    for _ in range(steps):
        try:
            page.mouse.wheel(0, random.randint(180, 420))
        except Exception:
            page.evaluate("window.scrollBy(0, 300)")
        time.sleep(random.uniform(0.35, 1.1))


def blocked_reason(page) -> str | None:
    u = page.url.lower()
    if any(x in u for x in ("/authwall", "/login", "/checkpoint", "/signup", "/uas/")):
        return f"o LinkedIn pediu login/verificação ({page.url})"
    try:
        if page.locator("#captcha-internal, .captcha, [data-test-id='captcha']").count():
            return "apareceu CAPTCHA"
    except Exception:
        pass
    try:
        if page.locator("form.login__form, .authwall").count():
            return "sessão não autenticada (tela de login)"
    except Exception:
        pass
    try:
        body = norm(page.locator("body").inner_text(timeout=1500)[:5000])
    except Exception:
        body = ""
    for term in ("captcha", "unusual activity", "atividade incomum", "security verification",
                 "verifique se voce", "verifique se você", "checkpoint", "acesso restrito",
                 "we've restricted", "restricted your account"):
        if term in body:
            return f"desafio de segurança na página ({term})"
    return None


def accept_cookies(page) -> None:
    for label in ("Aceitar", "Aceitar todos", "Accept", "Accept all"):
        try:
            b = page.get_by_role("button", name=label, exact=True)
            if b.count():
                b.first.click(timeout=1500)
                time.sleep(random.uniform(0.4, 0.9))
                return
        except Exception:
            continue


def save_debug(page, tag: str) -> None:
    DEBUG.mkdir(parents=True, exist_ok=True)
    try:
        (DEBUG / f"{tag}.html").write_text(page.content(), encoding="utf-8")
    except Exception:
        pass
    try:
        page.screenshot(path=str(DEBUG / f"{tag}.png"), full_page=False)
    except Exception:
        pass


# ------------------------------------------------------------------ busca
def search_url(s: dict, start: int = 0) -> str:
    q = {"keywords": s["keywords"], "location": s["location"], "f_TPR": s["tpr"],
         "sortBy": "DD", "start": start}
    if s.get("wt"):
        q["f_WT"] = s["wt"]
    return "https://www.linkedin.com/jobs/search/?" + urlencode(q)


def open_search(page, s: dict, start: int = 0) -> int:
    url = search_url(s, start)
    log.info("[%s] abrindo %s", s["id"], url)
    resp = page.goto(url, wait_until="domcontentloaded")
    if resp is not None and resp.status in (999, 429, 403):
        raise Blocked(f"HTTP {resp.status} do LinkedIn")
    accept_cookies(page)
    try:
        page.wait_for_selector(CARD_SEL, timeout=15000)
    except Exception:
        pass
    gradual_scroll(page, steps=random.randint(2, 4))
    n = page.locator(CARD_SEL).count()
    log.info("[%s] %d cards nesta página", s["id"], n)
    if n == 0:
        save_debug(page, f"vazio-{s['id']}")
    return n


def card_job_id(card) -> str:
    jid = card.get_attribute("data-occludable-job-id") or ""
    if jid:
        return jid.strip()
    urn = card.get_attribute("data-entity-urn") or ""
    m = re.search(r"jobPosting:(\d+)", urn)
    if m:
        return m.group(1)
    try:
        href = card.locator("a[href*='/jobs/view/']").first.get_attribute("href") or ""
        m = re.search(r"/jobs/view/(?:[^?]*?-)?(\d+)(?:\?|$)", href)
        if m:
            return m.group(1)
    except Exception:
        pass
    return ""


def scrape_cards(page) -> list[dict]:
    out, seen = [], set()
    cards = page.locator(CARD_SEL)
    for i in range(cards.count()):
        c = cards.nth(i)
        jid = card_job_id(c)
        if not jid or jid in seen:
            continue
        seen.add(jid)

        def pick(*sels):
            for sel in sels:
                try:
                    loc = c.locator(sel)
                    if loc.count():
                        t = clean(loc.first.inner_text())
                        if t:
                            return t
                except Exception:
                    continue
            return ""

        title = pick(".job-card-list__title--link", ".base-search-card__title",
                     ".job-card-container__link strong", ".artdeco-entity-lockup__title",
                     "a.job-card-container__link", "a[href*='/jobs/view/']")
        company = pick(".base-search-card__subtitle", ".artdeco-entity-lockup__subtitle",
                       ".job-card-container__company-name", ".artdeco-entity-lockup__subtitle span")
        location = pick(".job-search-card__location", ".job-card-container__metadata-item",
                        ".artdeco-entity-lockup__caption li", ".artdeco-entity-lockup__caption")
        footer = pick("time.job-search-card__listdate", "time.job-card-container__footer-item",
                      ".job-card-container__footer-item", ".job-search-card__listdate",
                      ".job-card-container__footer-wrapper")
        if not re.search(r"há|ago|reposted|dia|hora|minuto|semana|mês|mes|day|hour|week|month",
                         footer, re.I):
            footer = ""
        if not footer:
            try:
                items = c.locator(".job-card-container__footer-item, .job-card-container__footer-wrapper li")
                for k in range(min(items.count(), 5)):
                    t = clean(items.nth(k).inner_text())
                    if re.search(r"há|ago|reposted|dia|hora|minuto|semana|mês|mes|day|hour", t, re.I):
                        footer = t
                        break
            except Exception:
                pass
        if not footer:
            try:
                tm = c.locator("time").first
                if tm.count():
                    footer = clean(tm.inner_text()) or (tm.get_attribute("datetime") or "")
            except Exception:
                pass
        if not footer:
            try:                                  # último recurso: o texto do card traz "há 2 horas"
                full = clean(c.inner_text())
                m = re.search(r"(há\s+\d+\s+(?:minuto|hora|dia|semana|mês|mes)s?"
                              r"|reposted[^|]{0,40}"
                              r"|\d+\s+(?:minute|hour|day|week|month)s?\s+ago)", full, re.I)
                if m:
                    footer = m.group(1).strip()
            except Exception:
                pass
        out.append({
            "job_id": jid,
            "title": title or "(sem título)",
            "company": company,
            "location": location,
            "posted": footer,
            "url": f"https://www.linkedin.com/jobs/view/{jid}/",
        })
    return out


def _detail_title(page) -> str:
    return _txt(page, ".job-details-jobs-unified-top-card__job-title h1",
                ".job-details-jobs-unified-top-card__job-title", ".top-card-layout__title",
                "h1.topcard-layout__title", "h1")


def open_detail(page, job: dict) -> bool:
    """Abre o detalhe da vaga clicando no card; se o card não existir mais, vai pela URL.
    No layout de duas colunas o painel já existe antes do clique, então esperamos o título mudar
    (senão leríamos a descrição da vaga anterior)."""
    jid = job["job_id"]
    before_title = _detail_title(page)
    clicked = False
    try:
        card = page.locator(f"li[data-occludable-job-id='{jid}']").first
        if card.count():
            card.scroll_into_view_if_needed(timeout=4000)
            time.sleep(random.uniform(0.4, 1.0))
            link = card.locator("a[href*='/jobs/view/'], a.job-card-container__link").first
            target = link if link.count() else card
            target.click(timeout=5000)
            clicked = True
    except Exception as e:
        log.warning("clique no card %s falhou (%s); abrindo pela URL", jid, type(e).__name__)
    if not clicked:
        page.goto(job["url"], wait_until="domcontentloaded")
    deadline = time.time() + 15
    while time.time() < deadline:
        cur = _detail_title(page)
        if cur and cur != before_title:
            break
        if "/jobs/view/" in page.url and not clicked:
            break
        time.sleep(0.35)
    try:
        page.wait_for_selector(DETAIL_SEL, timeout=10000)
        return True
    except Exception:
        log.warning("detalhe %s não carregou", jid)
        save_debug(page, f"detalhe-{jid}")
        return False


def _txt(page, *sels) -> str:
    for sel in sels:
        try:
            loc = page.locator(sel)
            if loc.count():
                t = clean(loc.first.inner_text())
                if t:
                    return t
        except Exception:
            continue
    return ""


def expand_description(page) -> None:
    for sel in ("button.jobs-description__footer-button",
                "button.show-more-less-html__button--more",
                "button[aria-label*='Ver mais']", "button[aria-label*='See more']",
                "button.jobs-description__footer-button--expanded"):
        try:
            b = page.locator(sel).first
            if b.count() and b.is_visible():
                b.click(timeout=2000)
                time.sleep(random.uniform(0.4, 0.9))
                return
        except Exception:
            continue


def parse_detail(page, job: dict) -> dict:
    expand_description(page)
    desc = _txt(page, ".jobs-description__content", ".jobs-description-content__text",
                ".show-more-less-html__markup", "section.description", "#job-details",
                ".jobs-box__html-content", "article.jobs-description")
    if len(desc) < 80:                       # painel ainda montando: espera e tenta de novo
        time.sleep(1.0)
        desc = _txt(page, ".jobs-description__content", ".jobs-description-content__text",
                    ".show-more-less-html__markup", "section.description", "#job-details",
                    ".jobs-box__html-content", "article.jobs-description")
    d = dict(job)
    d["title_detail"] = _txt(page, ".job-details-jobs-unified-top-card__job-title h1",
                             ".job-details-jobs-unified-top-card__job-title", ".top-card-layout__title",
                             "h1.topcard-layout__title", "h1.t-24", "h1")
    d["company_detail"] = _txt(page, ".job-details-jobs-unified-top-card__company-name a",
                               ".job-details-jobs-unified-top-card__company-name",
                               ".topcard__org-name-link", ".topcard__flavor")
    d["location_detail"] = _txt(page, ".job-details-jobs-unified-top-card__primary-description-container .tvm__text",
                                ".job-details-jobs-unified-top-card__bullet",
                                ".topcard__flavor--bullet", ".topcard__flavor-row .topcard__flavor--bullet",
                                ".jobs-unified-top-card__bullet")
    d["posted_detail"] = _txt(page, ".job-details-jobs-unified-top-card__primary-description-container time",
                              "time.posted-time-ago__text", ".posted-time-ago__text",
                              ".jobs-unified-top-card__posted-date", "time")
    d["salary"] = _txt(page, ".jobs-unified-top-card__salary-info", ".job-details-jobs-unified-top-card__salary",
                       ".compensation__salary", ".salary",
                       ".jobs-unified-top-card__job-insight--highlight .tvm__text")
    d["apply"] = _txt(page, ".jobs-apply-button", "button.jobs-apply-button",
                      ".top-card-layout__cta", "a.topcard__link--apply")
    d["applicants"] = _txt(page, ".jobs-unified-top-card__applicant-count", ".num-applicants__caption")
    d["description"] = desc
    d["description_len"] = len(desc)
    d["scraped_at"] = datetime.now().isoformat(timespec="seconds")
    for k in ("title", "company", "location", "posted", "url"):
        if not d.get(k):
            d[k] = d.get(f"{k}_detail", "")
    return d


# ------------------------------------------------------------------ pontuação
def score_job(job: dict) -> dict:
    title = norm(job.get("title", "") + " " + job.get("title_detail", ""))
    desc = norm(job.get("description", ""))
    loc = norm(" ".join([job.get("location", ""), job.get("location_detail", ""), job.get("workplace", "")]))
    text = title + " " + desc
    techs = detect(text)
    pts, why = 0.0, []
    strengths, gaps = [], []

    # 1) senioridade / papel (25)
    if any(t in title for t in PROFILE["seniority"]):
        pts += 25; why.append("título sênior/lead (+25)"); strengths.append("senioridade compatível (sênior/lead)")
    elif any(t in title for t in PROFILE["junior"]):
        why.append("título júnior/estágio (+0)"); gaps.append("vaga de entrada, abaixo da sua senioridade")
    elif any(t in title for t in PROFILE["pleno"]):
        pts += 12; why.append("título pleno (+12)"); gaps.append("vaga pleno — pode pagar abaixo do seu nível")
    else:
        pts += 8; why.append("senioridade não explícita (+8)")

    # 2) stack (35): Salesforce pesa mais; AWS/Go/Python/Node/Angular somam
    sf_dev = techs["SALESFORCE"] and bool(re.search(r"apex|\blwc\b|soql|salesforce develop|desenvolvedor", text))
    stack = 0.0
    if sf_dev:
        stack += 20; strengths.append(PROFILE["strengths_map"]["SALESFORCE"])
    elif techs["SALESFORCE"]:
        stack += 12; strengths.append("experiência Salesforce")
    for t in ("AWS", "GO", "PYTHON", "NODE", "ANGULAR"):
        if techs[t]:
            stack += 5
            strengths.append(PROFILE["strengths_map"][t])
    stack = min(stack, 35)
    if stack:
        pts += stack; why.append(f"stack aderente (+{stack:.0f})")
    if not techs["SALESFORCE"] and not any(techs[t] for t in ("AWS", "GO", "PYTHON", "NODE", "ANGULAR")):
        gaps.append("stack pedida não bate com o seu (Salesforce/AWS/Go/Python/Node/Angular)")

    # 3) localização / modelo (20)
    remote = "remote" in loc or "remoto" in loc or "home office" in loc
    br = any(t in loc for t in PROFILE["latam_ok"])
    sp = any(t in loc for t in PROFILE["sp_terms"])
    blocked_country = any(t in loc or t in desc for t in PROFILE["blocked_countries"])
    if blocked_country:
        why.append("local restrito (+0)")
        gaps.append("vaga restrita a outro país (fora do seu alcance)")
    elif remote and (br or sp):
        pts += 20; why.append("remoto no Brasil (+20)"); strengths.append("remoto no Brasil")
    elif remote:
        pts += 16; why.append("remoto internacional (+16)"); strengths.append("remoto internacional (inglês fluente)")
        gaps.append("contratação internacional: confirmar visto/PJ e fuso")
    elif sp:
        pts += 16; why.append("híbrido/presencial em SP (+16)")
    elif br:
        pts += 9; why.append("presencial/híbrido no Brasil fora de SP (+9)")
        gaps.append("fora de São Paulo/ABC — verificar possibilidade de híbrido")
    else:
        pts += 4; why.append("localização indefinida (+4)")
        gaps.append("localização não informada")

    # 4) inglês (10)
    if re.search(r"ingles fluente|fluent english|english fluent|advanced english", text):
        pts += 10; why.append("inglês fluente (+10)"); strengths.append("inglês fluente exigido — você atende")

    # 5) certificações (10)
    if re.search(PROFILE["certs"]["AWS_CERT"], text):
        pts += 5; why.append("certificação AWS citada (+5)")
        strengths.append("certificação AWS Solutions Architect valorizada")
    if re.search(PROFILE["certs"]["SF_CERT"], text):
        pts += 5; why.append("certificação Salesforce citada (+5)")
        strengths.append("certificação Salesforce Administrator valorizada")

    # gaps de stack
    for t, label in (("JAVA", "Java/Spring"), ("DOTNET", ".NET/C#"), ("KOTLIN", "Kotlin"),
                     ("REACT", "React"), ("JAVASCRIPT", "JavaScript/TypeScript")):
        if techs[t]:
            gaps.append(f"pede {label} — não é seu foco (você tem TypeScript/Angular como diferencial parcial)")

    # anos de experiência
    m = re.findall(r"(\d+)\s*\+?\s*(?:years?|anos)", desc)
    years = max((int(x) for x in m), default=0)
    if years:
        if years > 4:
            gaps.append(f"pede {years}+ anos de experiência (você tem 4+ em ambiente bancário)")
        else:
            strengths.append(f"{years}+ anos exigidos — você atende")

    # vaga de administração (não de desenvolvimento)
    if re.search(r"salesforce admin(istrator)?", title) and not re.search(r"develop|engineer|apex|lwc", title):
        gaps.append("foco em administração Salesforce, não em desenvolvimento")

    pct = int(round(max(0, min(100, pts))))
    if pct >= 80:
        verdict = "ALTAMENTE ADERENTE"
    elif pct >= 65:
        verdict = "ADERENTE"
    elif pct >= 50:
        verdict = "PARCIAL"
    else:
        verdict = "BAIXA ADERÊNCIA"

    strengths = list(dict.fromkeys(strengths))
    gaps = list(dict.fromkeys(gaps))
    if not job.get("salary"):
        gaps.append("faixa salarial não informada na vaga")

    return {"match_pct": pct, "verdict": verdict, "why": "; ".join(why),
            "strengths": strengths, "gaps": gaps, "techs": [t for t, v in techs.items() if v],
            "years": years}


def salary_of(job: dict) -> str:
    if job.get("salary"):
        return clean(job["salary"])
    m = re.search(r"((?:R\$|US\$|USD|EUR|€)\s?[\d.,]+(?:\s?(?:mil|k|/mês|/mes|/ano|per year|per month|monthly|yearly))?)",
                  job.get("description", ""), re.I)
    return m.group(1) if m else "não informada"


def critical_requirements(job: dict) -> list[str]:
    req = []
    techs = [t for t, v in detect(job.get("title", "") + " " + job.get("description", "")).items() if v]
    if techs:
        req.append("Tecnologias: " + ", ".join(techs))
    m = re.findall(r"(\d+)\s*\+?\s*(?:years?|anos)", norm(job.get("description", "")))
    if m:
        req.append(f"Experiência: {max(int(x) for x in m)}+ anos")
    if re.search(r"ingles fluente|fluent english|advanced english", job.get("description", ""), re.I):
        req.append("Inglês fluente/avançado")
    req.append("Modelo/local: " + (job.get("location") or job.get("location_detail") or "não informado"))
    if job.get("apply"):
        req.append("Candidatura: " + job["apply"])
    return req


# ------------------------------------------------------------------ relatório
def render_report(jobs: list[dict], path: Path, order_note: str = "match") -> Path:
    ordem = ("mais recentes primeiro (ordem do LinkedIn com sortBy=DD; o match é a coluna ao lado)"
             if order_note == "recent" else "maior % de match primeiro")
    lines = [
        "# Vagas LinkedIn — relatório",
        "",
        f"Gerado em {datetime.now().strftime('%d/%m/%Y %H:%M')} · "
        f"{len(jobs)} vagas · ordenado por {ordem}",
        "",
        "> Match calculado por regras (título 25, stack 35, localização 20, inglês 10, certificações 10). "
        "Não é uma promessa de contratação — é um ranking para priorizar.",
        "",
        "| # | Match | Publicada | Vaga | Empresa | Local/modelo |",
        "|---|---|---|---|---|---|",
    ]
    for i, j in enumerate(jobs, 1):
        posted = (j.get("posted") or "—").replace("|", "/")[:18]
        lines.append(f"| {i} | **{j['score']['match_pct']}%** | {posted} | {j['title'][:70]} | "
                     f"{j['company'][:40]} | {(j.get('location') or j.get('location_detail') or '')[:55]} |")
    lines.append("")

    for i, j in enumerate(jobs, 1):
        s = j["score"]
        lines += [
            f"## {i}. {j.get('title_detail') or j['title']} — {j.get('company_detail') or j['company']}",
            "",
            f"- **Empresa:** {j.get('company_detail') or j['company'] or 'não informada'}",
            f"- **Modelo/local:** {j.get('location_detail') or j.get('location') or 'não informado'}",
            f"- **URL:** {j['url']}",
            f"- **Match:** **{s['match_pct']}%** ({s['verdict']}) — {s['why']}",
            f"- **Publicada:** {j.get('posted_detail') or j.get('posted') or 'não informado'}",
            f"- **Salário:** {salary_of(j)}",
            "",
            "**Pontos fortes**",
            "",
        ]
        lines += [f"- {x}" for x in (s["strengths"] or ["—"])]
        lines += ["", "**Gaps / atenção**", ""]
        lines += [f"- {x}" for x in (s["gaps"] or ["—"])]
        lines += ["", "**Requisitos críticos (detectados automaticamente)**", ""]
        lines += [f"- {x}" for x in critical_requirements(j)]
        excerpt = clean(j.get("description", ""))[:900]
        if excerpt:
            lines += ["", "**Trecho da descrição**", "", f"> {excerpt}{'…' if len(j.get('description', '')) > 900 else ''}"]
        lines.append("")

    path.write_text("\n".join(lines), encoding="utf-8")
    return path


def save_json(jobs: list[dict], path: Path) -> Path:
    path.write_text(json.dumps({"generated_at": datetime.now().isoformat(timespec="seconds"),
                                "count": len(jobs), "jobs": jobs}, ensure_ascii=False, indent=2),
                    encoding="utf-8")
    return path


# ------------------------------------------------------------------ fluxo principal
def run(args) -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    DEBUG.mkdir(parents=True, exist_ok=True)
    logging.basicConfig(
        level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s", datefmt="%H:%M:%S",
        handlers=[logging.StreamHandler(sys.stdout),
                  logging.FileHandler(OUT / "run.log", encoding="utf-8")])
    started = datetime.now().isoformat(timespec="seconds")
    pages = min(int(args.pages), SAFE_PAGES)
    max_jobs = min(int(args.max_jobs), SAFE_MAX_JOBS)
    details = min(int(args.details or 0), 5)
    log.info("modo seguro: %d página(s)/busca, até %d vagas, %d detalhe(s), TPR=%s",
             pages, max_jobs, details, args.tpr)

    if not args.force:
        prev = last_run()
        if prev:
            msg = f"já rodou hoje ({prev.get('found', 0)} vagas). Use --force para repetir."
            log.warning(msg)
            write_status(state="done", started_at=started, finished_at=started,
                         found=prev.get("found", 0), report=prev.get("report"),
                         message=msg, skipped=True)
            return 4

    searches = SEARCHES if args.intl else [s for s in SEARCHES if s["id"] != "intl"]
    if args.keywords:
        searches = [{"id": "custom", "label": "busca personalizada", "keywords": args.keywords,
                     "location": args.location, "tpr": args.tpr, "wt": args.wt}]
    for s in searches:
        s["tpr"] = args.tpr                     # sempre as mais recentes
    total_pages = pages * len(searches)
    done_pages = 0

    from playwright.sync_api import sync_playwright
    collected: dict[str, dict] = {}
    page = None
    write_status(state="running", started_at=started, pages=pages, found=0, page=0,
                 search=searches[0]["label"], details=details, total_pages=total_pages, done_pages=0)
    try:
        with sync_playwright() as pw:
            browser, ctx, page = connect(pw)
            try:
                for s_idx, s in enumerate(searches):
                    if len(collected) >= max_jobs:
                        break
                    if s_idx:
                        safe_pause(page, f"antes da busca '{s['label'][:30]}'", SEARCH_PAUSE)
                    for page_idx in range(pages):
                        if len(collected) >= max_jobs:
                            break
                        write_status(state="running", started_at=started, pages=pages,
                                     found=len(collected), page=page_idx + 1,
                                     search=s["label"], details=details,
                                     total_pages=total_pages, done_pages=done_pages)
                        open_search(page, s, start=page_idx * 25)
                        reason = blocked_reason(page)
                        if reason:
                            save_debug(page, f"bloqueio-{s['id']}-{page_idx + 1}")
                            raise Blocked(reason)
                        cards = scrape_cards(page)
                        log.info("[%s] página %d: %d cards", s["id"], page_idx + 1, len(cards))
                        if not cards:
                            break
                        for card in cards:
                            if len(collected) >= max_jobs:
                                break
                            if card["job_id"] in collected:
                                continue
                            job = dict(card)
                            job["description"] = ""
                            job["order"] = len(collected)      # ordem do LinkedIn ≈ mais recente primeiro
                            job["score"] = score_job(job)
                            collected[card["job_id"]] = job
                        if len(collected) < max_jobs and page_idx + 1 < pages:
                            safe_pause(page, f"antes da página {page_idx + 2} de '{s['id']}'")
                        done_pages += 1
                if details:
                    log.info("abrindo no máximo %d detalhes (pausa longa entre eles)", details)
                    for job in list(collected.values())[:details]:
                        write_status(state="running", started_at=started, pages=pages,
                                     found=len(collected), page=pages, search="detalhes",
                                     details=details, message=f"detalhe: {job['title'][:40]}")
                        safe_pause(page, "antes do detalhe")
                        if open_detail(page, job):
                            parsed = parse_detail(page, job)
                            job.update({k: v for k, v in parsed.items() if v})
                            job["score"] = score_job(job)
                        if "/jobs/view/" in page.url:
                            try:
                                page.go_back(wait_until="domcontentloaded")
                            except Exception:
                                pass
            finally:
                try:
                    pw.stop()                   # desconecta; NÃO fecha o seu Chrome
                except Exception:
                    pass
    except Blocked as e:
        write_status(state="blocked", started_at=started,
                     finished_at=datetime.now().isoformat(timespec="seconds"),
                     found=len(collected), message=str(e))
        log.error("PARANDO: %s. Não vou tentar contornar — verifique manualmente no Chrome.", e)
        return 3
    except SystemExit as e:
        write_status(state="error", started_at=started,
                     finished_at=datetime.now().isoformat(timespec="seconds"),
                     found=len(collected), message=str(e))
        log.error("erro: %s", e)
        return 5
    except Exception as e:
        write_status(state="error", started_at=started,
                     finished_at=datetime.now().isoformat(timespec="seconds"),
                     found=len(collected), message=f"{type(e).__name__}: {e}")
        log.exception("falha inesperada")
        return 5

    if args.sort == "match":
        jobs = sorted(collected.values(), key=lambda j: (-j["score"]["match_pct"], j["title"]))
    else:                                   # recente: ordem em que o LinkedIn devolveu (sortBy=DD)
        jobs = sorted(collected.values(),
                      key=lambda j: (j.get("order", 10 ** 9), -j["score"]["match_pct"]))
    if not jobs:
        log.error("nenhuma vaga coletada — veja out/debug/ (HTML e screenshot) para diagnosticar")
        write_status(state="error", started_at=started,
                     finished_at=datetime.now().isoformat(timespec="seconds"),
                     found=0, message="nenhuma vaga coletada")
        return 2

    report = render_report(jobs[: args.top], OUT / "linkedin-report.md", order_note=args.sort)
    data = save_json(jobs, OUT / "linkedin-jobs.json")
    LAST_RUN.write_text(json.dumps({"date": datetime.now().strftime("%Y-%m-%d"),
                                    "found": len(jobs), "report": str(report),
                                    "finished_at": datetime.now().isoformat(timespec="seconds")},
                                   ensure_ascii=False, indent=2), encoding="utf-8")
    write_status(state="done", started_at=started,
                 finished_at=datetime.now().isoformat(timespec="seconds"),
                 found=len(jobs), report=str(report), skipped=False,
                 top=[{"title": j["title"][:80], "company": j["company"][:60],
                       "location": j["location"][:60], "match_pct": j["score"]["match_pct"],
                       "url": j["url"]} for j in jobs[:10]])
    log.info("relatório: %s", report)
    log.info("dados:     %s", data)
    print(f"\n{len(jobs)} vagas no relatório. Abra: {report}")
    for i, j in enumerate(jobs[:10], 1):
        print(f"{i:2}. {j['score']['match_pct']:3}%  {j['title'][:58]:58} {j['company'][:28]}")
    return 0


def probe(args) -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    DEBUG.mkdir(parents=True, exist_ok=True)
    from playwright.sync_api import sync_playwright
    with sync_playwright() as pw:
        browser, ctx, page = connect(pw)
        try:
            log.info("abrindo %s", args.probe)
            page.goto(args.probe, wait_until="domcontentloaded")
            time.sleep(random.uniform(2, 4))
            accept_cookies(page)
            reason = blocked_reason(page)
            print("URL:", page.url)
            print("título:", page.title())
            print("cards:", page.locator(CARD_SEL).count())
            print("detalhe:", page.locator(DETAIL_SEL).count())
            print("bloqueio:", reason or "não detectado")
            save_debug(page, "probe")
            cards = scrape_cards(page)
            for c in cards[:5]:
                print("  -", c["job_id"], c["title"][:60], "|", c["company"][:30], "|", c["location"][:30])
            if cards:
                first = cards[0]
                page.goto(first["url"], wait_until="domcontentloaded")
                time.sleep(2)
                j = parse_detail(page, first)
                print("detalhe:", j.get("title_detail") or j.get("title"), "|", len(j.get("description", "")), "chars")
                save_debug(page, "probe-detalhe")
            print("HTML salvo em", DEBUG)
        finally:
            pw.stop()
    return 0


# ------------------------------------------------------------------ self-test
def self_test() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    base = {"posted": "há 1 dia", "applicants": "", "apply": "Candidatura simplificada",
            "workplace": "", "url": "https://www.linkedin.com/jobs/view/000/"}
    samples = [
        {**base, "job_id": "1", "title": "Senior Salesforce Developer", "company": "ACME",
         "location": "Brazil (Remote)",
         "description": "We need a Senior Salesforce Developer with Apex, LWC, SOQL, SFDX and AWS Lambda. "
                        "AWS Certified Solutions Architect is a plus. Fluent English required. 5+ years."},
        {**base, "job_id": "2", "title": "Senior Backend Engineer (Go/AWS)", "company": "Beta",
         "location": "Remote - Brazil",
         "description": "Go, Golang, AWS Lambda, DynamoDB, Python. 4+ years. Inglês fluente."},
        {**base, "job_id": "3", "title": "Desenvolvedor Java Sênior", "company": "Gama",
         "location": "São Paulo, SP (Híbrido)",
         "description": "Java 17, Spring Boot, Kotlin, AWS. 6+ anos. Presencial 2x por semana em SP."},
        {**base, "job_id": "4", "title": "Salesforce Administrator", "company": "Delta",
         "location": "São Paulo, SP (Híbrido)",
         "description": "Salesforce Administrator, declarative config, flows. Salesforce Certified Administrator."},
        {**base, "job_id": "5", "title": "Senior Backend Engineer", "company": "Epsilon",
         "location": "United States (Remote)",
         "description": "US only. Must reside in the US. Go, AWS. 8+ years."},
    ]
    scored = []
    for s in samples:
        s["score"] = score_job(s)
        scored.append(s)
    scored.sort(key=lambda j: -j["score"]["match_pct"])

    print("== pontuação ==")
    for s in scored:
        print(f"{s['score']['match_pct']:3}%  {s['title'][:45]:45} {s['location'][:30]}")
    report = render_report(scored, OUT / "selftest-report.md")
    print("relatório de teste:", report)

    pcts = [s["score"]["match_pct"] for s in scored]
    assert all(0 <= p <= 100 for p in pcts), pcts
    assert scored[0]["job_id"] == "1", scored[0]["title"]          # Salesforce sênior remoto deve liderar
    assert pcts[-1] < 40, pcts                                      # US-only deve ficar no fim
    assert any("restrita" in g for g in scored[-1]["score"]["gaps"])
    assert (OUT / "selftest-report.md").exists()
    print("OK: pontuação, ranking e relatório")
    return 0


def main() -> int:
    global OUT
    ap = argparse.ArgumentParser(description="LinkedIn Jobs via Chrome já logado (CDP), somente leitura")
    ap.add_argument("--probe", metavar="URL", help="só abre uma URL e mostra o que encontrou (diagnóstico)")
    ap.add_argument("--self-test", action="store_true", help="testa pontuação/relatório sem browser")
    ap.add_argument("--out", default=str(OUT), help="pasta de saída")
    ap.add_argument("--pages", type=int, default=SAFE_PAGES, help="páginas por busca (máx. 2)")
    ap.add_argument("--max-jobs", type=int, default=SAFE_MAX_JOBS, help="teto de vagas por execução (máx. 50)")
    ap.add_argument("--details", type=int, default=0, help="quantas vagas abrir no detalhe (0 = nenhuma)")
    ap.add_argument("--force", action="store_true", help="ignora o limite de 1 execução por dia")
    ap.add_argument("--top", type=int, default=30, help="quantas vagas entram no relatório")
    ap.add_argument("--sort", default="recent", choices=["recent", "match"],
                    help="ordem do relatório: recent (padrão) ou match")
    ap.add_argument("--no-intl", dest="intl", action="store_false", help="não fazer o passe internacional")
    ap.add_argument("--keywords", help="sobrescreve a busca (uma só)")
    ap.add_argument("--location", default="Brazil")
    ap.add_argument("--tpr", default=SAFE_TPR, choices=["r86400", "r604800"],
                    help="janela: 24h (padrão, mais recentes) ou última semana")
    ap.add_argument("--wt", default="2,3", help="1 presencial, 2 remoto, 3 híbrido (separar por vírgula)")
    args = ap.parse_args()

    OUT = Path(args.out)
    if args.self_test:
        return self_test()
    if args.probe:
        return probe(args)
    return run(args)


if __name__ == "__main__":
    sys.stdout.reconfigure(errors="replace")
    raise SystemExit(main())
