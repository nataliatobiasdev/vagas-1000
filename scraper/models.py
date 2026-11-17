"""Modelo de dados de uma vaga capturada (campos alinhados ao schema v3 da base)."""
from __future__ import annotations

from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone


@dataclass
class Job:
    company_id: str
    company_name: str
    source: str                    # lever | greenhouse | stone_portal
    title: str
    url: str = ""
    location: str = ""
    area: str = ""                 # departamento / time
    workplace_type: str = ""       # remote | hybrid | onsite | "" (desconhecido)
    commitment: str = ""
    description: str = ""
    job_id: str = ""
    captured_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat(timespec="seconds"))
    # preenchidos pelo filtro
    score: float = 0.0
    verdict: str = ""              # ELIGIBLE | MAYBE | BLOCKED
    reasons: list[str] = field(default_factory=list)
    techs: list[str] = field(default_factory=list)
    # ---- registro completo (v1.1): tudo que a fonte informa, para a vaga continuar guardada depois que sair do ar
    apply_url: str = ""            # link de candidatura
    team: str = ""
    locations: list[str] = field(default_factory=list)       # todos os locais (a vaga pode ter vários)
    salary_text: str = ""          # como a fonte publicou ("US$ 800 – 800 / ano")
    salary_min: float | None = None
    salary_max: float | None = None
    salary_currency: str = ""
    salary_period: str = ""        # year | month | hour | ""
    posted_at: str = ""            # publicação (ISO)
    updated_at: str = ""           # última edição na fonte (ISO)
    deadline: str = ""             # prazo de inscrição
    requisition_id: str = ""
    description_html: str = ""     # descrição original, em HTML limpo (sem script, estilo nem imagens)
    sections: list[dict] = field(default_factory=list)       # [{"title", "html"}]: requisitos, benefícios, etapas...
    metadata: dict = field(default_factory=dict)             # outros campos rotulados que a fonte envia
    raw: dict = field(default_factory=dict)                  # payload original completo da fonte
    detail_at: str = ""            # quando o detalhe completo foi lido de verdade (a lista pode vir do cache)

    # campos pesados: ficam no banco, não nos JSON/CSV de cada execução
    HEAVY = ("raw", "description_html", "sections")

    def to_dict(self, full: bool = True) -> dict:
        d = asdict(self)
        if not full:
            for k in self.HEAVY:
                d.pop(k, None)
        return d
