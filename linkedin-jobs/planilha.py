"""Regras e formato da planilha da captura do LinkedIn (o mesmo formato que o Claude no Chrome entregou em 17/11).

Sem rede e sem navegador: só funções puras, para o script de busca e para os testes. O importador do app
(scraper/importer.py) lê este CSV direto.

A ADERÊNCIA e o CRITÉRIO de senioridade são regras transparentes, não o julgamento de um modelo. Contra a planilha
de 17/11 elas batem em 52 de 67 vagas (78%): as divergências são casos de fronteira (ex.: Salesforce só na descrição).
Ajustar as regras aqui muda a classificação das próximas capturas.
"""
from __future__ import annotations

import csv
import re
from datetime import date

COLUNAS = ["id", "url", "titulo", "empresa", "local", "origem_busca", "modalidade", "tipo_contrato", "publicada",
           "candidaturas", "candidatura_simplificada", "ja_candidatei", "salario_citado", "criterio_senioridade",
           "aderencia_salesforce", "espanhol", "elegibilidade_brasil", "descricao"]

STACK = re.compile(r"\bapex\b|\blwc\b|soql|sfdx|flosum|visualforce", re.I)
SENIOR = re.compile(r"s[êe]nior|\bsr\b|\bstaff\b|\bprincipal\b|\blead\b|arquitet|especialista|especialist", re.I)
SENIOR_DESC = re.compile(r"\b(5|6|7|8|10)\+?\s*(anos|years)", re.I)
WORKPLACE = [(re.compile(r"\bh[ií]brid", re.I), "Híbrido"), (re.compile(r"\bremot", re.I), "Remoto"),
             (re.compile(r"\bpresencial|\bon[- ]?site", re.I), "Presencial")]
CONTRACT = [(re.compile(r"tempo integral|full[- ]?time", re.I), "Tempo integral"),
            (re.compile(r"meio per[ií]odo|part[- ]?time", re.I), "Meio período"),
            (re.compile(r"contrato|contract", re.I), "Contrato"), (re.compile(r"est[aá]gio|intern", re.I), "Estágio")]
SPANISH = re.compile(r"espanhol|spanish|hispan", re.I)
BRAZIL = re.compile(r"brasil|brazil|\bbr\b|s[ãa]o paulo|curitiba|florian[oó]polis|rio de janeiro|belo horizonte", re.I)


def aderencia(titulo: str, descricao: str) -> str:
    """Alta: Salesforce no título com stack (Apex/LWC/SOQL) ou sinal de senioridade.
    Média: Salesforce no título ou no texto com algum desses sinais. Baixa: o resto."""
    t, d = titulo or "", descricao or ""
    sf_t = bool(re.search(r"salesforce", t, re.I))
    sf_any = sf_t or bool(re.search(r"salesforce", d, re.I))
    stack = bool(STACK.search(t + " " + d))
    senior = bool(SENIOR.search(t))
    if sf_t and (stack or senior):
        return "Alta"
    if sf_any and (stack or senior or sf_t):
        return "Média"
    return "Baixa"


def criterio_senioridade(titulo: str, descricao: str) -> str:
    if SENIOR.search(titulo or ""):
        palavra = re.search(SENIOR, titulo).group(0).lower()
        if re.search(r"arquitet", palavra):
            return "título: arquiteto"
        if re.search(r"lead", palavra):
            return "título: lead/gerência"
        if re.search(r"staff|principal", palavra):
            return "título: staff/principal"
        if re.search(r"especialist", palavra):
            return "título: especialista (equivalente)"
        return "título: sênior"
    if SENIOR_DESC.search(descricao or ""):
        return "descrição: 5+ anos de experiência"
    return "não identificado"


def modalidade(*textos: str) -> str:
    alvo = " ".join(t for t in textos if t)
    for rx, nome in WORKPLACE:
        if rx.search(alvo):
            return nome
    return ""


def tipo_contrato(*textos: str) -> str:
    alvo = " ".join(t for t in textos if t)
    for rx, nome in CONTRACT:
        if rx.search(alvo):
            return nome
    return ""


def espanhol(descricao: str) -> str:
    if not SPANISH.search(descricao or ""):
        return "não citado"
    return "obrigatório" if re.search(r"(obrigat[óo]rio|required|requerido)[^.]{0,40}(espanhol|spanish)", descricao, re.I) else "desejável"


def elegibilidade(local: str, origem: str) -> str:
    if BRAZIL.search(local or "") or origem == "Brasil":
        return "Vaga no Brasil"
    if re.search(r"only|somente|us citizen|eua|usa|united states|eu only", local or "", re.I):
        return "Restrito a outros países"
    return "Sem restrição detectada para brasileiros"


def linha(vaga: dict, origem: str) -> dict:
    """Uma vaga coletada (dict do scrape + detalhe) -> linha da planilha, com as colunas na ordem do formato."""
    titulo, desc = vaga.get("title", ""), vaga.get("description", "")
    loc = vaga.get("location", "")
    return {
        "id": vaga.get("job_id", ""), "url": vaga.get("url", ""), "titulo": titulo, "empresa": vaga.get("company", ""),
        "local": loc, "origem_busca": origem,
        "modalidade": modalidade(vaga.get("workplace", ""), loc, titulo, desc),
        "tipo_contrato": tipo_contrato(vaga.get("contract", ""), desc),
        "publicada": vaga.get("posted", ""), "candidaturas": vaga.get("applicants", ""),
        "candidatura_simplificada": "Sim" if vaga.get("easy_apply") else "Não",
        "ja_candidatei": "Sim" if vaga.get("applied") else "Não",
        "salario_citado": vaga.get("salary", ""),
        "criterio_senioridade": criterio_senioridade(titulo, desc),
        "aderencia_salesforce": aderencia(titulo, desc),
        "espanhol": espanhol(desc), "elegibilidade_brasil": elegibilidade(loc, origem), "descricao": desc,
    }


def escrever(caminho, linhas: list[dict]) -> None:
    """CSV em UTF-8 com BOM (o Excel abre), todos os campos entre aspas, como a planilha de 17/11."""
    with open(caminho, "w", encoding="utf-8-sig", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=COLUNAS, quoting=csv.QUOTE_ALL)
        w.writeheader()
        w.writerows(linhas)


def nome_arquivo(hoje: date | None = None) -> str:
    return f"vagas_salesforce_senior_{(hoje or date.today()).isoformat()}.csv"
