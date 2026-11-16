"""Filtro e pontuação (pesos em config/profile.json): título 30, tecnologia 35, senioridade 15, elegibilidade 20."""
from __future__ import annotations

import re
import unicodedata

from .models import Job

TECH_PATTERNS = {
    "SALESFORCE": r"salesforce|apex|\blwc\b|sfdx|service cloud|sales cloud|marketing cloud|experience cloud|cpq",
    "AWS": r"\baws\b|amazon web services|lambda|dynamodb|\bs3\b|cloudformation",
    "GO": r"\bgolang\b|\bgo\b(?= (developer|engineer|lang))|\bgo,",
    "PYTHON": r"\bpython\b|django|fastapi|flask",
    "TYPESCRIPT_NODE": r"typescript|node\.?js|\bnode\b|nestjs",
    "ANGULAR_REACT": r"angular|\breact\b|next\.?js",
    "GRAPHQL": r"graphql",
    "AI_GENAI": r"\bgenai\b|\bllm\b|generative ai|\bia generativa\b|agentic|\bagentes? de ia\b|machine learning",
    "INTEGRATION_ARCH": r"mulesoft|integra[cç][aã]o|integration|\bapi\b|event[- ]driven|kafka|microservi",
    "JAVA": r"\bjava\b|spring",
    "DOTNET": r"\.net|c#|dotnet",
}

# localização: o que dá para aplicar (Brasil/LATAM/mundial remoto) x o que é restrito a outro país
_BR_LOC = re.compile(r"brazil|brasil|sao paulo|são paulo|campinas|santo andre|santo andré|são bernardo|"
                     r"osasco|barueri|abc paulista|rio de janeiro|belo horizonte|curitiba|porto alegre|"
                     r"florianopolis|florianópolis|recife|fortaleza|salvador|brasilia|brasília|goiania|goiânia|"
                     r"manaus|joinville|camacari|camaçari|simoes filho|simões filho|candeias|"
                     r"dias d.avila|dias d.ávila|lauro de freitas|feira de santana|vitoria da conquista|"
                     r"vitória da conquista|ilheus|ilhéus|porto seguro|juazeiro|barreiras|alagoinhas|"
                     r"teixeira de freitas|iracemapolis|iracemápolis|maceio|maceió")
_LATAM_LOC = re.compile(r"latam|latin america|south america")
_WORLD_LOC = re.compile(r"worldwide|anywhere|global")
_REMOTE_LOC = re.compile(r"remote|remoto|home office")
_FOREIGN_LOC = re.compile(r"\b(usa|u\.s\.|united states|canada|mexico|méxico|argentina|colombia|chile|peru|perú|"
                          r"uruguay|paraguay|bolivia|ecuador|venezuela|india|poland|portugal|spain|germany|"
                          r"france|uk|united kingdom|ireland|israel|singapore|australia|japan|china|"
                          r"philippines|turkey|türkiye|"
                          r"bogota|bogotá|toronto|palo alto|miami|new york|san francisco|seattle|austin|boston|"
                          r"chicago|los angeles|london|madrid|lisbon|lisboa|berlin|paris|dublin|amsterdam|"
                          r"barcelona|mexico city|ciudad de méxico|buenos aires|santiago|lima|montevideo)\b")


def is_brazil_location(location: str) -> bool:
    """Local é Brasil? (cobre 'Brazil', 'Brasil', cidades brasileiras e 'Remoto' em português)."""
    loc = _norm(location or "")
    return bool(_BR_LOC.search(loc)) or loc.strip() in {"remoto", "home office"}


def classify_eligibility(location: str, workplace: str, profile: dict) -> tuple[str, float, str]:
    """Brasil, LATAM remoto e 'worldwide/anywhere' são aplicáveis; país estrangeiro é bloqueado.

    Antes, 'Remote - USA' caía como MAYBE (não casava com 'us only') e poluía a lista; agora vira
    BLOCKED, enquanto 'Remote - LATAM'/'Brazil' viram ELIGIBLE — inclusive vagas internacionais.
    """
    loc = _norm(f"{location} {workplace}")
    pts = profile["weights"]["eligibility"]
    if _BR_LOC.search(loc):
        return "ELIGIBLE", pts, "local: Brasil"
    if _LATAM_LOC.search(loc):
        return "ELIGIBLE", pts, "local: América Latina (remoto)"
    if _WORLD_LOC.search(loc):
        return "ELIGIBLE", pts, "local: mundial (remoto)"
    if _FOREIGN_LOC.search(loc):
        return "BLOCKED", 0, "local restrito a outro país"
    blocked = _has(loc, profile["eligibility_block"])
    allowed = _has(loc, profile["eligibility_allow"])
    if _REMOTE_LOC.search(loc):
        # 'Remoto' (PT) está na lista de elegíveis do profile; 'Remote' sozinho é ambíguo
        if blocked:
            return "BLOCKED", 0, f"local bloqueado: {', '.join(blocked)}"
        if allowed:
            return "ELIGIBLE", pts, f"local elegível: {', '.join(allowed[:2])}"
        return "MAYBE", pts * 0.5, "remoto sem país informado"
    if blocked:
        return "BLOCKED", 0, f"local bloqueado: {', '.join(blocked)}"
    if allowed:
        return "ELIGIBLE", pts, f"local elegível: {', '.join(allowed[:2])}"
    return "MAYBE", pts * 0.5, "local não informado/ambíguo"


def _norm(s: str) -> str:
    s = unicodedata.normalize("NFKD", s.lower())
    return "".join(c for c in s if not unicodedata.combining(c))


def _has(text: str, terms: list[str]) -> list[str]:
    out = []
    for t in terms:
        t = _norm(t)
        if re.search(rf"(?<![a-z0-9]){re.escape(t)}(?![a-z0-9])", text):
            out.append(t)
    return out


def detect_techs(text: str) -> list[str]:
    n = _norm(text)
    return [k for k, rx in TECH_PATTERNS.items() if re.search(rx, n)]


def score_job(job: Job, profile: dict) -> Job:
    w = profile["weights"]
    title = _norm(job.title)
    body = _norm(" ".join([job.title, job.area, job.description]))
    reasons: list[str] = []

    # título: exclusão dura
    excl = _has(title, profile["title_exclude"])
    area_hit = _has(title, profile["title_include_area"])
    if excl:
        reasons.append(f"título excluído: {', '.join(excl)}")
    pts_title = 0 if excl else (w["title"] if area_hit else w["title"] * 0.3)
    if area_hit:
        reasons.append(f"título na área: {', '.join(area_hit[:3])}")

    # tecnologia: título conta cheio; descrição conta fração (descrições têm texto institucional padrão);
    # techs "genéricas" (IA, integração, GraphQL) só contam se aparecerem no título.
    title_techs = set(detect_techs(job.title + " " + job.area))
    all_techs = set(detect_techs(body))
    tw = profile.get("tech_weights", {})
    generic = set(profile.get("generic_techs", []))
    # techs exibidas: as genéricas (IA/integração/GraphQL) só aparecem se estiverem no título
    job.techs = sorted(t for t in all_techs if t in title_techs or t not in generic)
    factor = profile.get("description_hit_factor", 0.4)
    raw = 0.0
    core_hits: list[str] = []
    for t in all_techs:
        if t not in profile["core_tech"]:
            continue
        if t in title_techs:
            raw += tw.get(t, 1)
            core_hits.append(t)
        elif t not in generic:
            raw += tw.get(t, 1) * factor
            core_hits.append(t + "(desc)")
    pts_tech = w["tech"] * min(raw / profile.get("tech_weight_cap", 3), 1)
    if core_hits:
        reasons.append(f"tecnologias do perfil: {', '.join(core_hits)}")

    # senioridade
    sen = _has(title, profile["title_include_seniority"])
    pts_sen = w["seniority"] if sen else w["seniority"] * 0.4
    if sen:
        reasons.append(f"senioridade: {', '.join(sen[:2])}")

    # elegibilidade
    elig, pts_el, why_loc = classify_eligibility(job.location, job.workplace_type, profile)
    reasons.append(why_loc)

    job.score = round(pts_title + pts_tech + pts_sen + pts_el, 1)
    job.reasons = reasons
    if excl or elig == "BLOCKED":
        job.verdict = "BLOCKED"
    elif job.score >= profile.get("eligible_min_score", 70) and elig == "ELIGIBLE" and core_hits:
        job.verdict = "ELIGIBLE"
    else:
        job.verdict = "MAYBE"
    return job
