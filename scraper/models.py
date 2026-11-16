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

    def to_dict(self) -> dict:
        return asdict(self)
