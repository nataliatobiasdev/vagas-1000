"""Coletores: Selenium navega/espera/pagina; os parsers (parsers.py) extraem do HTML."""
from __future__ import annotations

import json
import logging
import random
import re
import time
import urllib.request
from urllib.parse import urlencode, urlparse, urlunparse, parse_qsl

from . import parsers
from .driver import session_alive
from .models import Job

log = logging.getLogger("scraper")


def _wait(driver, css: str, timeout: float = 20):
    from selenium.webdriver.support.ui import WebDriverWait
    from selenium.webdriver.support import expected_conditions as EC
    from selenium.webdriver.common.by import By
    return WebDriverWait(driver, timeout).until(EC.presence_of_element_located((By.CSS_SELECTOR, css)))


def _pause(lo=1.0, hi=2.2):
    time.sleep(random.uniform(lo, hi))   # cortesia: espaçar requisições


def _with_query(url: str, extra: dict) -> str:
    p = urlparse(url)
    q = dict(parse_qsl(p.query))
    q.update({k: v for k, v in extra.items() if v})
    return urlunparse(p._replace(query=urlencode(q)))


def _accept_cookies(driver):
    from selenium.webdriver.common.by import By
    for label in ("Aceitar todos", "Aceitar", "Accept all", "Accept"):
        try:
            for b in driver.find_elements(By.XPATH, f"//button[normalize-space()='{label}']"):
                if b.is_displayed():
                    b.click()
                    _pause(0.4, 0.8)
                    return
        except Exception:
            pass


def _enrich(driver, jobs: list[Job], detail_parser, selector: str, max_details: int):
    total = min(len(jobs), max_details)
    for i, j in enumerate(jobs[:max_details], 1):
        if i == 1 or i % 10 == 0 or i == total:
            log.info("detalhes %d/%d", i, total)     # a etapa da CI&T leva minutos: mostra progresso
        if not j.url:
            continue
        try:
            driver.get(j.url)
            _wait(driver, selector, 15)
            data = detail_parser(driver.page_source)
            for k, v in data.items():
                if v and not getattr(j, k, ""):
                    setattr(j, k, v)
                elif k == "description":
                    j.description = v
        except Exception as e:                      # detalhe é opcional: não derruba a coleta
            if not session_alive(driver):           # ...mas se a janela/Chrome morreu, a empresa falha
                raise                               # e o runner recria o driver e tenta de novo
            log.warning("detalhe falhou %s: %s", j.url, e)
        _pause()


# ---------------------------------------------------------------- Lever
def collect_lever(driver, cfg: dict, max_details: int = 120) -> list[Job]:
    url = _with_query(cfg["board_url"], cfg.get("site_filters", {}))
    log.info("[%s] abrindo %s", cfg["company_id"], url)
    driver.get(url)
    _wait(driver, "div.posting, .postings-group, .no-postings", 25)
    jobs = parsers.parse_lever_list(driver.page_source, cfg["company_id"], cfg["name"])
    log.info("[%s] %d vagas na lista", cfg["company_id"], len(jobs))
    if cfg.get("fetch_details"):
        _enrich(driver, jobs, parsers.parse_lever_detail, '[data-qa="job-description"], .posting-headline', max_details)
    return jobs


# ----------------------------------------------------------- Greenhouse
def collect_greenhouse(driver, cfg: dict, max_details: int = 120) -> list[Job]:
    url = _with_query(cfg["board_url"], cfg.get("site_filters", {}))
    log.info("[%s] abrindo %s", cfg["company_id"], url)
    driver.get(url)
    _wait(driver, "tr.job-post, .job-posts__empty-state", 25)
    html = driver.page_source
    if parsers.greenhouse_is_empty(html):
        log.warning("[%s] board sem vagas abertas", cfg["company_id"])
        return []
    jobs = parsers.parse_greenhouse_list(html, cfg["company_id"], cfg["name"])
    log.info("[%s] %d vagas na lista", cfg["company_id"], len(jobs))
    if cfg.get("fetch_details"):
        _enrich(driver, jobs, parsers.parse_greenhouse_detail, ".job__description, .job__title", max_details)
    return jobs


# --------------------------------------------------- APIs públicas (sem Selenium)
def _filter_by_title(jobs: list[Job], cfg: dict) -> list[Job]:
    """Recorte opcional por título (cfg["title_include"]).

    Serve para boards grandes e genéricos (banco com 200 vagas de crédito/analista):
    entram só as de engenharia/Salesforce. Sem `title_include`, entra tudo.
    """
    pattern = cfg.get("title_include")
    if not pattern:
        return jobs
    rx = re.compile(pattern, re.I)
    kept = [j for j in jobs if rx.search(j.title or "")]
    log.info("[%s] filtro de título: %d de %d vagas", cfg["company_id"], len(kept), len(jobs))
    return kept


def _filter_by_location(jobs: list[Job], cfg: dict) -> list[Job]:
    """Recorte opcional por localização (cfg["location_include"]).

    Usado em board global: mantém só 'Brazil/LATAM/worldwide' e deixa de fora 'Remote - USA'.
    """
    pattern = cfg.get("location_include")
    if not pattern:
        return jobs
    rx = re.compile(pattern, re.I)
    kept = [j for j in jobs if rx.search(j.location or "")]
    log.info("[%s] filtro de local: %d de %d vagas", cfg["company_id"], len(kept), len(jobs))
    return kept


def _filter_by_title_exclude(jobs: list[Job], cfg: dict) -> list[Job]:
    """Remove títulos indesejados (cfg["title_exclude"]), ex.: júnior, vendas, product manager."""
    pattern = cfg.get("title_exclude")
    if not pattern:
        return jobs
    rx = re.compile(pattern, re.I)
    kept = [j for j in jobs if not rx.search(j.title or "")]
    log.info("[%s] exclusão de título: %d de %d vagas", cfg["company_id"], len(kept), len(jobs))
    return kept


def _dedupe_by_title(jobs: list[Job], cfg: dict) -> list[Job]:
    """Colapsa a mesma vaga publicada por país (ex.: Brazil/LATAM/Mexico) em uma só, preferindo Brasil."""
    if not cfg.get("dedupe_by_title"):
        return jobs

    def pref(j: Job) -> int:
        loc = (j.location or "").lower()
        if "brazil" in loc or "brasil" in loc:
            return 0
        if "latam" in loc or "latin america" in loc or "south america" in loc:
            return 1
        return 2

    best: dict[str, Job] = {}
    for j in jobs:
        key = (j.title or "").strip().lower()
        if key not in best or pref(j) < pref(best[key]):
            best[key] = j
    kept = list(best.values())
    if len(kept) != len(jobs):
        log.info("[%s] dedupe por título: %d de %d vagas", cfg["company_id"], len(kept), len(jobs))
    return kept


def _post_process(jobs: list[Job], cfg: dict) -> list[Job]:
    jobs = _filter_by_location(jobs, cfg)
    jobs = _filter_by_title(jobs, cfg)
    jobs = _filter_by_title_exclude(jobs, cfg)
    return _dedupe_by_title(jobs, cfg)


def _get_text(url: str, attempts: int = 2) -> str:
    """GET HTML com uma retentativa (portais SSR, sem Selenium)."""
    last = None
    for i in range(attempts):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 (vagas-scraper)"})
            with urllib.request.urlopen(req, timeout=45) as resp:
                return resp.read().decode("utf-8", "replace")
        except Exception as e:
            last = e
            if i + 1 < attempts:
                log.warning("GET falhou (%s %s); tentando de novo", type(e).__name__, str(e)[:80])
                time.sleep(2.0)
    raise last


def collect_gupy(driver, cfg: dict, max_details: int = 40) -> list[Job]:
    """Gupy: o portal entrega a lista de vagas no __NEXT_DATA__ (SSR) — sem Selenium.

    A descrição exige abrir /jobs/{id}; fazemos isso só para as vagas que passaram nos filtros.
    """
    base = cfg["board_url"].rstrip("/")
    max_details = cfg.get("max_details", max_details)
    log.info("[%s] portal %s", cfg["company_id"], base)
    jobs = parsers.parse_gupy_list(_get_text(base + "/"), cfg["company_id"], cfg["name"], base)
    log.info("[%s] %d vagas no portal", cfg["company_id"], len(jobs))
    jobs = _post_process(jobs, cfg)
    if cfg.get("fetch_details", True):
        for j in jobs[:max_details]:
            if not j.url:
                continue
            try:
                detail = parsers.parse_gupy_detail(_get_text(j.url))
                if detail.get("description"):
                    j.description = detail["description"]
            except Exception as e:
                log.warning("detalhe Gupy falhou %s: %s", j.url, e)
            _pause(0.4, 0.9)              # cortesia entre páginas de detalhe
    return jobs


# --------------------------------------------------- Workday (Salesforce etc.)
def _post_json(url: str, body: dict, attempts: int = 3):
    """POST JSON com backoff — o Workday da Salesforce responde 429 quando aceleramos."""
    last = None
    for i in range(attempts):
        try:
            req = urllib.request.Request(
                url, data=json.dumps(body).encode(),
                headers={"User-Agent": "Mozilla/5.0 (vagas-scraper)",
                         "Content-Type": "application/json", "Accept": "application/json"})
            with urllib.request.urlopen(req, timeout=45) as resp:
                return json.loads(resp.read().decode("utf-8"))
        except Exception as e:
            last = e
            if i + 1 < attempts:
                wait = 8 * (i + 1)
                log.warning("Workday respondeu %s; aguardando %ss", type(e).__name__, wait)
                time.sleep(wait)
    raise last


def collect_workday(driver, cfg: dict, max_details: int = 30) -> list[Job]:
    """Workday (CXS): lista paginada por POST; descrição por GET em externalPath."""
    host = cfg.get("workday_host") or urlparse(cfg["board_url"]).netloc
    tenant = cfg.get("workday_tenant") or host.split(".")[0]
    site = cfg.get("workday_site") or cfg["board_url"].rstrip("/").split("/")[-1]
    base = f"https://{host}"
    api = f"{base}/wday/cxs/{tenant}/{site}/jobs"
    max_jobs = int(cfg.get("max_jobs", 40))
    max_details = int(cfg.get("max_details", max_details))
    log.info("[%s] Workday %s", cfg["company_id"], api)
    items: list[dict] = []
    offset = 0
    while offset < max_jobs:
        data = _post_json(api, {"appliedFacets": {}, "limit": 20, "offset": offset,
                                "searchText": cfg.get("search_text", "")})
        batch = data.get("jobPostings") or []
        items.extend(batch)
        offset += 20
        if not batch or offset >= int(data.get("total", 0)):
            break
        _pause(4.0, 6.0)
    jobs = parsers.parse_workday_jobs({"jobPostings": items}, cfg["company_id"], cfg["name"],
                                      f"{base}/{site}")
    log.info("[%s] %d vagas no Workday", cfg["company_id"], len(jobs))
    jobs = _post_process(jobs, cfg)
    if cfg.get("fetch_details", True):
        for j in jobs[:max_details]:
            if not (j.job_id or "").startswith("/"):
                continue
            try:
                detail = parsers.parse_workday_detail(
                    _get_json(f"{base}/wday/cxs/{tenant}/{site}{j.job_id}", attempts=3))
                if detail.get("description"):
                    j.description = detail["description"]
            except Exception as e:
                log.warning("detalhe Workday falhou %s: %s", j.url, e)
            _pause(3.0, 5.0)
    return jobs


def _get_json(url: str, attempts: int = 2):
    """GET JSON com uma retentativa — cobre timeout/hiccup de rede sem derrubar a empresa."""
    last = None
    for i in range(attempts):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 (vagas-scraper)"})
            with urllib.request.urlopen(req, timeout=45) as resp:
                return json.loads(resp.read().decode("utf-8"))
        except Exception as e:
            last = e
            if i + 1 < attempts:
                log.warning("GET falhou (%s %s); tentando de novo", type(e).__name__, str(e)[:80])
                time.sleep(2.0)
    raise last


def collect_lever_api(driver, cfg: dict, max_details: int = 120) -> list[Job]:
    """Lever pela API pública: mesmas vagas/descrições do detalhe, em um request só."""
    token = cfg.get("board_token") or cfg["board_url"].rstrip("/").split("/")[-1]
    url = f"https://api.lever.co/v0/postings/{token}?mode=json"
    log.info("[%s] API %s", cfg["company_id"], url)
    payload = _get_json(url)
    jobs = _post_process(parsers.parse_lever_api(payload, cfg["company_id"], cfg["name"],
                                                 cfg.get("site_filters")), cfg)
    log.info("[%s] %d vagas na API (de %d no board)", cfg["company_id"], len(jobs), len(payload))
    _pause(0.5, 1.0)
    return jobs


def collect_ashby_api(driver, cfg: dict, max_details: int = 120) -> list[Job]:
    """Ashby pela API pública (JSON), com descrição e, quando publicada, faixa de compensação."""
    board = cfg.get("board_token") or cfg["board_url"].rstrip("/").split("/")[-1]
    url = f"https://api.ashbyhq.com/posting-api/job-board/{board}?includeCompensation=true"
    log.info("[%s] API %s", cfg["company_id"], url)
    payload = _get_json(url)
    jobs = _post_process(parsers.parse_ashby_api(payload, cfg["company_id"], cfg["name"]), cfg)
    log.info("[%s] %d vagas na API", cfg["company_id"], len(jobs))
    _pause(0.5, 1.0)
    return jobs


# --------------------------------------------------- Greenhouse (API pública)
def collect_greenhouse_api(driver, cfg: dict, max_details: int = 120) -> list[Job]:
    """Greenhouse pela API pública (JSON): traz TODAS as vagas e a descrição no mesmo request.

    O board HTML novo (job-boards.greenhouse.io) renderiza no máximo 50 vagas e não tem
    "carregar mais" — empresas com mais que isso perderiam vagas. Não usa Selenium.
    """
    base = cfg.get("api_base", "https://boards-api.greenhouse.io")
    token = cfg.get("board_token") or cfg["board_url"].rstrip("/").split("/")[-1]
    url = f"{base}/v1/boards/{token}/jobs?content=true"
    log.info("[%s] API %s", cfg["company_id"], url)
    payload = _get_json(url)
    jobs = _post_process(parsers.parse_greenhouse_api(payload, cfg["company_id"], cfg["name"]), cfg)
    log.info("[%s] %d vagas na API", cfg["company_id"], len(jobs))
    _pause(0.5, 1.2)                       # cortesia: uma requisição por empresa
    return jobs


# ---------------------------------------------------------------- Stone
def _stone_signature(driver) -> str:
    """Identifica a página atual pela lista de links das vagas (/oportunidades/ID)."""
    return driver.execute_script(
        "return [...document.querySelectorAll('a[href*=\"/oportunidades/\"]')]"
        ".map(a=>a.getAttribute('href')).join('|');") or ""


def collect_stone(driver, cfg: dict, max_pages: int = 15, max_details: int = 120) -> list[Job]:
    """Portal próprio (SPA). Filtros por URL (?times=Tecnologia&categories=Engenharia) e paginação por
    botões numerados. A extração dos cards usa o HTML renderizado de cada página."""
    from selenium.webdriver.common.by import By
    url = _with_query(cfg["board_url"], cfg.get("site_filters", {}))
    log.info("[%s] abrindo %s", cfg["company_id"], url)
    driver.get(url)
    _wait(driver, "article h3", 30)   # o 1º <article> é o wrapper da página; esperar os cards
    _accept_cookies(driver)
    all_jobs: dict[str, Job] = {}
    base = "{0.scheme}://{0.netloc}".format(urlparse(cfg["board_url"]))
    for page in range(1, max_pages + 1):
        for j in parsers.parse_stone_list(driver.page_source, cfg["company_id"], cfg["name"], base):
            all_jobs.setdefault(j.url or f"{j.title}|{j.location}", j)
        log.info("[%s] página %d: acumulado %d", cfg["company_id"], page, len(all_jobs))
        # próxima página: botão com o número seguinte, ou seta →
        nxt = None
        for xp in (f"//button[normalize-space()='{page + 1}']", "//button[normalize-space()='→']"):
            els = [e for e in driver.find_elements(By.XPATH, xp) if e.is_displayed() and e.is_enabled()]
            if els:
                nxt = els[0]
                break
        if not nxt:
            break
        before = _stone_signature(driver)
        driver.execute_script("arguments[0].scrollIntoView({block:'center'});", nxt)
        nxt.click()
        _pause(1.2, 2.0)
        # espera a lista de vagas (links) mudar; comparar títulos não serve: o 1º h3 é o bloco mobile, oculto
        for _ in range(50):                             # até 20 s: o SPA troca os cards sem recarregar a página
            if _stone_signature(driver) != before:
                break
            time.sleep(0.4)
        else:
            log.warning("[%s] lista não mudou em 20s após clicar na página %d; encerrando paginação "
                        "(pode faltar vaga)", cfg["company_id"], page + 1)
            break
    jobs = list(all_jobs.values())
    if cfg.get("fetch_details"):
        _enrich(driver, jobs, parsers.parse_stone_detail, "h2", max_details)
    return jobs


COLLECTORS = {"lever": collect_lever, "lever_api": collect_lever_api,
              "greenhouse": collect_greenhouse, "greenhouse_api": collect_greenhouse_api,
              "ashby_api": collect_ashby_api, "gupy": collect_gupy,
              "workday": collect_workday, "stone_portal": collect_stone}
