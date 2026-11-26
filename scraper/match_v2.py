"""Motor experimental, local e explicável; nunca altera a base nem afirma probabilidade.

As regras são heurísticas: resultados inconclusivos exigem revisão humana. Este módulo
opera em paralelo ao filtro de produção até avaliação com vagas rotuladas.
"""
from __future__ import annotations

import re
import unicodedata


def norm(value):
    value = value or ''
    if value.isascii():
        return value.lower()
    return ''.join(c for c in unicodedata.normalize('NFKD', value) if not unicodedata.combining(c)).lower()


PATTERNS = {
    'salesforce': r'\bsalesforce\b', 'apex': r'\bapex\b', 'lwc': r'\blwc\b|lightning web components?',
    'aura': r'\baura\b', 'flow': r'\bflows?\b', 'experience_cloud': r'experience cloud|partner communit',
    'api': r'\bapis?\b|\brest\b|\bsoap\b|integrac|integration', 'cicd': r'ci\s*/\s*cd|pipelines?',
    'git': r'\bgit\b', 'architecture': r'arquitet|architect', 'leadership': r'\blead\b|lideran|mentoria|mentor',
    'testing': r'\btests?\b|testes?|\btdd\b', 'aws': r'\baws\b|amazon web services',
    'go': r'\bgolang\b|\bgo developer\b', 'python': r'\bpython\b', 'angular': r'\bangular\b',
    'typescript': r'\btypescript\b', 'sql': r'\bsql\b|\bsoql\b', 'docker': r'\bdocker\b',
    'ai': r'\bllms?\b|agentforce|generative ai|\bgenai\b|ia generativa',
    'marketing_cloud': r'marketing cloud|\bsfmc\b', 'personalization': r'personalization|interaction studio',
    'oms': r'order management|\boms\b', 'mulesoft': r'mulesoft|\bmule\b',
    'java': r'\bjava\b|\bspring\b', 'dotnet': r'\.net|\bc#\b|\bdotnet\b',
    'omni_studio': r'omnistudio|\bvlocity\b|omniscript|flexcards?',
    'sap': r'\bsap\b', 'react': r'\breact\b|next\.js', 'node': r'\bnode\.?js\b',
    'fastapi': r'\bfastapi\b', 'kotlin_android': r'\bandroid\b|\bkotlin\b', 'databricks': r'\bdatabricks\b',
    'messaging': r'\bkafka\b|\bsqs\b|\brabbitmq\b|queue systems|sistemas de filas',
    'cpq': r'\bcpq\b|revenue cloud', 'voice': r'service cloud voice|partner telephony|\bbyot\b|amazon connect',
    'life_sciences': r'life sciences cloud|health cloud',
}
COMPILED_PATTERNS = {key: re.compile(pattern) for key, pattern in PATTERNS.items()}
SPECIAL = {'marketing_cloud', 'personalization', 'oms', 'mulesoft', 'java', 'dotnet', 'omni_studio', 'sap', 'react', 'node', 'fastapi', 'kotlin_android', 'databricks'}
VERDICT_ORDER = {'ANÁLISE MANUAL': 4, 'CONDICIONAL': 3, 'INFORMAÇÕES INSUFICIENTES': 2, 'BAIXA ADERÊNCIA': 1, 'INCOMPATÍVEL': 0}


def ranking_key(verdict, track, score):
    """A categoria sempre prevalece sobre a nota; score nunca compensa impedimento."""
    return (VERDICT_ORDER.get(verdict, -1), track == 'principal', float(score or 0))


REQUIRED = re.compile(r'\b(required|requirements?|must|mandatory|essential|obrigatori[oa]s?|requisitos?|imprescindivel|necessari[oa]s?|exigimos|exigid[oa]s?)\b')
PREFERRED = re.compile(r'\b(preferred|nice to have|desirable|diferencia[il]s?|desejave[il]|preferencial)\b')
NEGATED = re.compile(r'\b(nao (?:e )?(?:necessari[oa]|obrigatori[oa]|exigid[oa])|not required|no (?:prior )?experience (?:is )?(?:required|necessary))\b')


def snippets(text):
    """Preserva linhas; assume cabeçalhos como contexto somente até próximo cabeçalho."""
    state = 'unknown'
    result = []
    # Algumas fontes achatam os cabeçalhos e o corpo numa única linha.
    text = re.sub(r'\b(Obrigat[oó]ri[oa]s?|Diferenciais|Preferred Qualifications|Requirements|Qualifications)\b(?=\s|:)', r'\n\1:\n', text or '', flags=re.I)
    for raw in re.split(r'[\r\n;|]+|(?<=[.!?])\s+', text):
        line = raw.strip(' \t•-')
        if not line:
            continue
        n = norm(line)
        if len(line) < 100 and (line.endswith(':') or len(line.split()) <= 4):
            if PREFERRED.search(n):
                state = 'preferred'
            elif REQUIRED.search(n) or re.search(r"what (?:we are|we're) looking for|o que (?:esperamos|voce precisa ter)", n):
                state = 'required'
            elif line.endswith(':'):
                state = 'unknown'
        if NEGATED.search(n):
            kind = 'not_required'
        elif PREFERRED.search(n):
            kind = 'preferred'
        elif REQUIRED.search(n):
            kind = 'required'
        else:
            kind = state
        result.append((line, n, kind))
    return result


def assess(job, profile):
    title = norm(job.title)
    desc = job.description or ''
    parts = snippets(desc)
    skills = profile['skills']
    evidence = []
    for line, n, kind in parts:
        alternative = bool(kind == 'required' and re.search(r'\b(?:ou|or)\b|\s/\s', n))
        for skill, pattern in COMPILED_PATTERNS.items():
            if pattern.search(n):
                evidence.append({'skill': skill, 'kind': kind, 'text': line[:350], 'alternative': alternative})
    required = {e['skill'] for e in evidence if e['kind'] == 'required'}
    mentioned = {e['skill'] for e in evidence if e['kind'] != 'not_required'}
    # Uma alternativa no mesmo trecho não deve virar exigência categórica.
    alternative_skills = {e['skill'] for e in evidence if e['alternative']}
    # Uma alternativa também requer revisão: o outro ramo pode não estar no perfil.
    # Não se afirma que a tecnologia isolada seja obrigatória.
    unknown_required = sorted(s for s in required if s not in skills or skills[s].startswith('não comprovada'))
    # Títulos descrevem o núcleo do trabalho, mas não provam requisitos específicos.
    sf = bool(re.search(r'\bsalesforce\b|\bapex\b|\blwc\b', title))
    specialist = bool(re.search(r'personalization|interaction studio|marketing cloud|\bsfmc\b|order management|\boms\b', title))
    administrator = bool(re.search(r'\badministrat(?:or|ion)\b|\badministrador', title))
    lead = bool(re.search(r'\blead\b|\bsenior\b|\bsr\b|especialista', title))
    aspirational = bool(re.search(r'\bstaff\b|\bprincipal\b|\barchitect\b|arquiteto', title))
    talent_pool = bool(re.search(r'banco de talentos|talent pool|talent network', title))
    adjacent = bool(re.search(r'\bsoftware\b|backend|back.end|integrat|integrac|cloud engineer', title))
    unrelated = bool(re.search(r'\b(data engineer|engenheir[oa] de dados|sales manager|recruiter|intern|estagiario|junior|trainee|product owner|scrum master|endpoint security|devops|head of|support engineer|infrastructure engineer|analista de qualidade)\b', title))
    midlevel = bool(re.search(r'\b(?:pleno|pl|mid.level)\b', title)) and not lead
    technical_role = bool(re.search(r'developer|desenvolvedor|desenvolvedora|engineer|engenheir|tech lead|technical lead|lideranca tecnica|integration|integrac|platform engineer|specialist|especialista|architect|arquiteto', title))
    # Um título genérico pode esconder uma função integralmente especializada.
    marketing_core = len(re.findall(PATTERNS['marketing_cloud'], norm(desc))) >= 3 and not (mentioned & {'apex', 'lwc'})
    if marketing_core:
        specialist = True
    # Especialista CRM pode ser um cargo de governança, não desenvolvimento.
    if re.search(r'especialista crm|crm specialist', title) and not re.search(r'desenvolver|development|desenvolvimento|programa[cç]|\bapex\b|\blwc\b', norm(desc)):
        technical_role = False
    track = 'principal' if sf and technical_role and not specialist and not administrator and not unrelated and not midlevel else ('aspiracional' if aspirational and adjacent and not unrelated else ('expansão' if adjacent and not unrelated and not midlevel else 'outra'))
    if sf and (specialist or administrator):
        track = 'outra'
    if sf and aspirational and not unrelated and not specialist and not administrator:
        track = 'aspiracional'
    role = 15 if track == 'principal' else 10 if track == 'expansão' else 8 if track == 'aspiracional' else 2
    activities = min(10, 2 * len(mentioned & {'apex','lwc','api','architecture','leadership','testing'}))
    trajectory = {'principal': 5, 'expansão': 3, 'aspiracional': 2, 'outra': 0}[track]
    professional = {s for s, level in skills.items() if level == 'profissional'}
    informed = {s for s, level in skills.items() if level in ('informada', 'experimenta e aplica')}
    # O denominador inclui requisitos identificados, não tecnologias ausentes da vaga.
    tech_req = required & set(PATTERNS)
    req_points = round(20 * sum(1 if s in professional else .5 if s in informed else 0 for s in tech_req) / len(tech_req)) if tech_req else 0
    complement = min(10, 2 * len(mentioned & (professional | informed)))
    desirable = {e['skill'] for e in evidence if e['kind'] == 'preferred'}
    bonus = min(5, len(desirable & (professional | informed)))
    seniority = 10 if lead else 6 if aspirational else 2
    leadership = 5 if 'leadership' in mentioned else 0
    experience = 3 if re.search(r'\b[3-7]\+?\s*(?:anos|years)', norm(desc)) else 0
    transfer = min(6, 2 * len(mentioned & {'api', 'architecture'})) + (3 if len(desc) >= 500 else 0) + min(4, 2 * len(mentioned & {'leadership','ai'}))
    points = {'função e atividades': role + activities + trajectory, 'requisitos técnicos': req_points + complement + bonus, 'senioridade e escopo': seniority + leadership + experience, 'experiência transferível': transfer}
    location = norm(' '.join([job.location or '', job.workplace_type or '']))
    full = norm(desc)
    blocked = bool(re.search(r'us citizens? only|must (?:be|already be) authorized to work in (?:the )?(?:us|united states)|only open to candidates (?:in |based in |in based in )?(?:the )?(?:us|united states)', full))
    brazil = bool(re.search(r'brasil|brazil|sao paulo|barueri|osasco|santo andre|sao bernardo', location))
    remote = bool(re.search(r'remoto|remote|home office', location + ' ' + full))
    explicit_brazil = bool(re.search(r'brasil|brazil', location))
    foreign = bool(re.search(r'\b(?:united states|usa|canada|portugal|germany|spain|ireland|uk|colombia|mexico|argentina|chile|peru|uruguay|costa rica|philippines|filipinas|manila|bogota|buenos aires|london|lisbon|lisboa|madrid)\b', location))
    other_city = bool(re.search(r'belo horizonte|curitiba|recife|rio de janeiro|porto alegre|florianopolis|salvador|brasilia|fortaleza|campinas', location))
    # A palavra Brasil não transforma trabalho presencial em outra cidade em remoto.
    remote_field = bool(re.search(r'\bremote\b|\bremoto\b|home office', location))
    location_uncertain = other_city and not remote_field
    local_sp = bool(re.search(r'sao paulo|barueri|osasco|santo andre|sao bernardo', location))
    outside_onsite = other_city and not local_sp and bool(re.search(r'(?:100%\s*)?presencial|on.site', full))
    conditional = bool(unknown_required) or track == 'expansão' or (track == 'aspiracional' and not sf)
    cert_pattern = re.compile(r'certifica|platform developer\s*(?:i{1,2}|1|2)\b|\bpd\s*(?:i{1,2}|1|2)\b')
    cert_evidence = [line for line, n, kind in parts if kind == 'required' and cert_pattern.search(n)]
    cert = bool(cert_evidence)
    incomplete = len(desc.strip()) < 300 or not evidence
    if blocked or outside_onsite:
        verdict = 'INCOMPATÍVEL'
    elif talent_pool:
        verdict = 'INFORMAÇÕES INSUFICIENTES'
    elif foreign:
        verdict = 'INFORMAÇÕES INSUFICIENTES'
    elif unrelated and not incomplete:
        verdict = 'BAIXA ADERÊNCIA'
    elif conditional or cert:
        verdict = 'CONDICIONAL'
    elif incomplete or not (brazil or (remote and explicit_brazil)) or foreign or location_uncertain:
        verdict = 'INFORMAÇÕES INSUFICIENTES'
    elif track == 'outra':
        verdict = 'BAIXA ADERÊNCIA'
    else:
        verdict = 'ANÁLISE MANUAL'
    # Heurística não confirma elegibilidade: falta validação de requisitos e local completo.
    confidence = 'baixa' if incomplete else 'média'
    warnings = []
    if unknown_required: warnings.append('Possível requisito ou alternativa sem evidência no perfil: ' + ', '.join(unknown_required))
    if cert: warnings.append('Possível certificação obrigatória: ' + cert_evidence[0][:180] + ' — conferir nome e status')
    if incomplete: warnings.append('Descrição insuficiente para análise confiável')
    if talent_pool: warnings.append('Banco de talentos: cargo e requisitos concretos não confirmados')
    if track == 'expansão': warnings.append('Trilha de expansão: profundidade profissional nos requisitos centrais precisa de revisão')
    if not brazil: warnings.append('Elegibilidade geográfica não confirmada')
    if foreign: warnings.append('Local internacional: contratação do Brasil ou patrocínio precisa de confirmação')
    if location_uncertain: warnings.append('Cidade fora da região preferida; modalidade precisa de confirmação')
    if outside_onsite: warnings.append('Presencial fora da região preferida')
    if marketing_core: warnings.append('Atividades indicam especialização central em Marketing Cloud, sem Apex/LWC identificado')
    if alternative_skills & SPECIAL: warnings.append('Alternativa técnica detectada: confirmar se é requisito obrigatório')
    if specialist or administrator: warnings.append('Função especializada ou administração: verificar atividades centrais')
    return {'score': sum(points.values()), 'components': points, 'verdict': verdict, 'confidence': confidence,
            'track': track, 'evidence': evidence, 'warnings': warnings, 'unknown_required': unknown_required}
