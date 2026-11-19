"""Coletores: Selenium navega/espera/pagina; os parsers (parsers.py) extraem do HTML."""
from __future__ import annotations

import json
import logging
import random
import re
import time
import urllib.error
import urllib.request
from datetime import datetime, timedelta
from datetime import timezone
from email.utils import parsedate_to_datetime
import xml.etree.ElementTree as ET
from urllib.parse import urlencode, urlparse, urlunparse, parse_qsl, urljoin

from . import db, parsers
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
            parsers.apply_detail(j, detail_parser(driver.page_source))
            j.detail_at = _now()
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


class SourceUnavailable(Exception):
    """O serviço inteiro (host) não responde nesta execução: não adianta tentar as demais empresas dele."""


HTTP_TIMEOUT = 25            # segundos de leitura; as APIs respondem em ~1-7 s, então 25 já é folga
HOST_FAIL_LIMIT = 2          # timeouts seguidos (sem nenhuma resposta entre eles) que dão o host como fora do ar
_HOST_FAILS: dict[str, int] = {}
_HOST_DOWN: dict[str, str] = {}      # só vale nesta execução: cada execução do app é um processo novo


def reset_host_state() -> None:
    _HOST_FAILS.clear()
    _HOST_DOWN.clear()


def _retry_wait(e: Exception, i: int) -> float:
    """Quanto esperar antes da próxima tentativa. 429 (Too Many Requests) respeita `Retry-After` e dobra a cada
    tentativa; o resto (timeout, 5xx) espera pouco."""
    if isinstance(e, urllib.error.HTTPError) and e.code == 429:
        try:
            retry_after = float(e.headers.get("Retry-After", "") or 0)
        except (TypeError, ValueError, AttributeError):
            try:
                retry_after = max(0.0, (parsedate_to_datetime(e.headers.get('Retry-After', '')) - datetime.now(timezone.utc)).total_seconds())
            except (TypeError, ValueError, AttributeError, OverflowError):
                retry_after = 0.0
        return max(retry_after, min(10.0 * (2 ** i), 60.0))
    return 2.0


def _fetch(url: str, attempts: int, data: dict | None = None) -> bytes:
    """GET (ou POST JSON, com `data`) com tentativas e espera adequada.

    Disjuntor por host: se `HOST_FAIL_LIMIT` empresas seguidas do mesmo serviço estouram o tempo sem resposta (como
    quando a API da Lever sai do ar), as demais são puladas na hora em vez de gastar ~1 min cada."""
    host = urlparse(url).netloc
    if host in _HOST_DOWN:
        raise SourceUnavailable(_HOST_DOWN[host])
    if _HOST_FAILS.get(host, 0) >= 1:
        attempts = 1                                    # a empresa anterior já estourou o tempo neste host: sem 2ª tentativa
    last: Exception | None = None
    for i in range(attempts):
        try:
            headers = {"User-Agent": "Mozilla/5.0 (vagas1000)"}
            body = None
            if data is not None:
                body = json.dumps(data).encode()
                headers.update({"Content-Type": "application/json", "Accept": "application/json"})
            with urllib.request.urlopen(urllib.request.Request(url, data=body, headers=headers),
                                        timeout=HTTP_TIMEOUT) as resp:
                payload = resp.read()
            _HOST_FAILS[host] = 0
            return payload
        except Exception as e:
            last = e
            if isinstance(e, urllib.error.HTTPError) and e.code < 500:
                _HOST_FAILS[host] = 0                       # respondeu 4xx (inclui 429): o serviço está no ar
            if isinstance(e, urllib.error.HTTPError) and e.code == 403:
                break  # bloqueio de acesso: não insistir nem tentar contorná-lo
            if i + 1 < attempts:
                wait = _retry_wait(e, i)
                if isinstance(e, urllib.error.HTTPError) and e.code == 429 and wait > 60:
                    log.warning('%s pediu espera de %.0fs; adiando a fonte para outra execução', host, wait)
                    break
                log.warning("%s falhou (%s %s); tentando de novo em %.0fs", host, type(e).__name__, str(e)[:80], wait)
                time.sleep(wait)
    assert last is not None
    # Sem resposta (timeout, conexão) ou erro 5xx (500/502/504 da Lever numa queda) contam como "serviço fora do ar";
    # 4xx não: o servidor respondeu.
    down = isinstance(last, (TimeoutError, OSError)) and not (isinstance(last, urllib.error.HTTPError) and last.code < 500)
    if down:
        _HOST_FAILS[host] = _HOST_FAILS.get(host, 0) + 1
        if _HOST_FAILS[host] >= HOST_FAIL_LIMIT:
            _HOST_DOWN[host] = (f"{host} está fora do ar ({type(last).__name__}: {str(last)[:60]}); as demais empresas dele "
                                "foram puladas nesta execução — as vagas guardadas continuam")
            log.error("%s", _HOST_DOWN[host])
    raise last


def _get_text(url: str, attempts: int = 2) -> str:
    """GET HTML com uma retentativa (portais SSR, sem Selenium)."""
    return _fetch(url, attempts).decode("utf-8", "replace")


def _now() -> str:
    return datetime.now().isoformat(timespec="seconds")


def _detail_fresh(detail_at: str, days: float) -> bool:
    """O detalhe guardado ainda vale? (lido há menos de `days` dias)"""
    try:
        return datetime.now() - datetime.fromisoformat(detail_at) < timedelta(days=days)
    except (TypeError, ValueError):
        return False


def _fetch_details(jobs: list[Job], cfg: dict, fetch, max_new: int, pause: tuple[float, float], label: str) -> None:
    """Completa as vagas com o detalhe, reaproveitando o que o banco já tem.

    - Detalhe guardado há menos de `detail_refresh_days` (7): reutiliza, sem tocar na rede.
    - Novo ou velho: busca, no máximo `max_new` por execução (as demais ficam para a próxima, sem perder o que já havia).
    Assim a primeira execução guarda tudo e as seguintes só abrem o que mudou ou é novo.
    """
    known = cfg.get("_known") or {}
    days = float(cfg.get("detail_refresh_days", 7))
    fetched = 0
    failures = 0                                         # falhas seguidas: o site está limitando (429) ou fora do ar
    for j in jobs:
        cached = known.get(db.job_key(j))
        if cached and _detail_fresh(cached.get("detail_at", ""), days):
            parsers.apply_detail(j, cached)
            j.detail_at = cached["detail_at"]
            continue
        if fetched >= max_new or failures >= 3 or not j.url:
            if cached:                                   # sem orçamento agora: mantém o guardado, mesmo velho
                parsers.apply_detail(j, cached)
                j.detail_at = cached.get("detail_at", "")
            continue
        try:
            parsers.apply_detail(j, fetch(j))
            j.detail_at = _now()
            failures = 0
        except Exception as e:
            failures += 1
            log.warning("detalhe %s falhou %s: %s", label, j.url, e)
            if failures >= 3:
                log.warning("[%s] 3 detalhes seguidos falharam: parei de abrir detalhes nesta execução "
                            "(o resto fica para a próxima, reaproveitando o que o banco já tem)", cfg["company_id"])
            if cached:
                parsers.apply_detail(j, cached)
                j.detail_at = cached.get("detail_at", "")
        fetched += 1
        _pause(*pause)                                   # cortesia entre páginas de detalhe
    if fetched:
        log.info("[%s] %d detalhes novos/atualizados (resto reaproveitado do banco)", cfg["company_id"], fetched)


def collect_gupy(driver, cfg: dict, max_details: int = 150) -> list[Job]:
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
        _fetch_details(jobs, cfg, lambda j: parsers.parse_gupy_detail(_get_text(j.url)), max_details,
                       (0.4, 0.9), "Gupy")
    return jobs


# --------------------------------------------------- Workday (Salesforce etc.)
def _post_json(url: str, body: dict, attempts: int = 3):
    """POST JSON com backoff — o Workday da Salesforce responde 429 quando aceleramos."""
    return json.loads(_fetch(url, attempts, data=body).decode("utf-8"))


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
        wd = [j for j in jobs if (j.job_id or "").startswith("/")]
        _fetch_details(wd, cfg, lambda j: parsers.parse_workday_detail(
            _get_json(f"{base}/wday/cxs/{tenant}/{site}{j.job_id}", attempts=3)), max_details, (3.0, 5.0), "Workday")
    return jobs


def _get_json(url: str, attempts: int = 2):
    """GET JSON com uma retentativa — cobre timeout/hiccup de rede sem derrubar a empresa."""
    return json.loads(_fetch(url, attempts).decode("utf-8"))


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
    url = f"{base}/v1/boards/{token}/jobs?content=true&pay_transparency=true"
    log.info("[%s] API %s", cfg["company_id"], url)
    payload = _get_json(url)
    jobs = _post_process(parsers.parse_greenhouse_api(payload, cfg["company_id"], cfg["name"]), cfg)
    log.info("[%s] %d vagas na API", cfg["company_id"], len(jobs))
    _pause(0.5, 1.2)                       # cortesia: uma requisição por empresa
    return jobs


def collect_gft(driver, cfg: dict, max_details: int = 150) -> list[Job]:
    """Lista pública da GFT, com paginação validada antes de registrar sucesso."""
    from bs4 import BeautifulSoup
    url = cfg["board_url"]
    seen_pages, jobs = set(), {}
    expected = None
    while url:
        if url in seen_pages or len(seen_pages) >= 100:
            raise ValueError("paginação GFT repetida ou acima do limite")
        seen_pages.add(url)
        soup = BeautifulSoup(_get_text(url), "lxml")
        label = soup.select_one(".pagination-bottom .paginationLabel")
        rows = soup.select("tr.data-row")
        if not label:
            raise ValueError("GFT: contador de resultados ausente")
        counts = [int(x.get_text(strip=True).replace('.', '')) for x in label.select('b')[-1:] if x.get_text(strip=True).replace('.', '').isdigit()]
        if not counts:
            raise ValueError("GFT: total de resultados ilegível")
        if expected is None:
            expected = counts[0]
        elif expected != counts[0]:
            raise ValueError("GFT: total mudou durante a paginação")
        for row in rows:
            link = row.select_one('a.jobTitle-link[href]')
            if not link:
                raise ValueError("GFT: vaga sem link")
            href = urljoin(url, link['href'])
            jid = urlparse(href).path.rstrip('/').split('/')[-1]
            if not jid or jid in jobs:
                raise ValueError("GFT: identificador vazio ou repetido")
            location = row.select_one('.colLocation .jobLocation')
            workplace = row.select_one('.jobShifttype')
            jobs[jid] = Job(company_id=cfg['company_id'], company_name=cfg['name'], source='gft',
                            job_id=jid, title=link.get_text(' ', strip=True), url=href,
                            location=location.get_text(' ', strip=True) if location else '',
                            workplace_type=parsers._workplace(workplace.get_text(' ', strip=True) if workplace else ''))
        if len(jobs) >= expected:
            break
        next_link = soup.select_one('.pagination-bottom .current-page')
        parent = next_link.find_parent('li') if next_link else None
        sibling = parent.find_next_sibling('li') if parent else None
        next_link = sibling.find('a', href=True) if sibling else None
        if not rows or not next_link:
            raise ValueError("GFT: paginação incompleta")
        url = urljoin(url, next_link['href'])
        _pause(0.5, 1.0)
    if len(jobs) != expected:
        raise ValueError("GFT: quantidade coletada difere do total")
    result = _post_process(list(jobs.values()), cfg)
    def detail(job):
        soup = BeautifulSoup(_get_text(job.url), 'lxml')
        content = soup.select_one('[itemprop="description"] .jobdescription')
        if not content:
            raise ValueError('GFT: descrição ausente')
        return {'description': content.get_text(' ', strip=True), 'description_html': parsers.clean_html(str(content))}
    if cfg.get('fetch_details', True):
        _fetch_details(result, cfg, detail, int(cfg.get('max_details', max_details)), (0.4, 0.9), 'GFT')
    return result


def collect_gft_rss(driver, cfg: dict, max_details: int = 150) -> list[Job]:
    """Feed oficial complementar: amostra recente, nunca um retrato completo do portal."""
    payload = _get_text(cfg['board_url'])
    try:
        root = ET.fromstring(payload)
    except ET.ParseError as e:
        raise ValueError('GFT RSS: XML inválido') from e
    channel = root.find('channel')
    if root.tag != 'rss' or channel is None:
        raise ValueError('GFT RSS: feed inválido')
    result = []
    for item in channel.findall('item'):
        link = (item.findtext('link') or '').strip()
        title = (item.findtext('title') or '').strip()
        parsed = urlparse(link)
        if parsed.scheme != 'https' or parsed.netloc != 'jobs.gft.com' or not parsed.path.startswith('/job/') or not title:
            raise ValueError('GFT RSS: vaga sem título ou link válido')
        jid = parsed.path.rstrip('/').split('/')[-1]
        raw_description = item.findtext('description') or ''
        html = parsers.clean_html(raw_description)
        location = ''
        match = re.search(r'\(([^()]*(?:\bBR\b|Brasil|Brazil)[^()]*)\)\s*$', title, re.I)
        if match:
            location = match.group(1).strip()
            title = title[:match.start()].strip()
        date = item.findtext('pubDate') or ''
        try:
            posted_at = parsedate_to_datetime(date).isoformat()
        except (TypeError, ValueError, OverflowError):
            posted_at = ''
        result.append(Job(company_id=cfg['company_id'], company_name=cfg['name'], source='gft_rss',
                          job_id=jid, title=title, url=f'https://jobs.gft.com{parsed.path}',
                          location=location, workplace_type=parsers._workplace(title),
                          description=parsers.html_to_text(html), description_html=html,
                          posted_at=posted_at, raw={'feed_item': {x.tag: x.text for x in item}},
                          metadata={'cobertura': 'feed parcial: publicações recentes'}))
    log.info('[%s] feed parcial: %d vagas recentes; ausências não indicam encerramento', cfg['company_id'], len(result))
    return _post_process(result, cfg)


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
              "workday": collect_workday, "stone_portal": collect_stone, "gft": collect_gft,
              "gft_rss": collect_gft_rss}
