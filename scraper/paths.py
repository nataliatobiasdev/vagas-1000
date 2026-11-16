"""Onde ficam os arquivos do vagas1000.

- BUNDLE: recursos somente-leitura que vão junto com o programa (config padrão, modelo do painel).
- HOME:   pasta gravável do usuário (banco, saídas, logs e a cópia editável da configuração).

Em desenvolvimento (rodando do código-fonte) as duas são a raiz do projeto, como sempre foi.
Instalado (PyInstaller), HOME é %APPDATA%\\vagas1000 — o desinstalador nunca apaga essa pasta.
A variável VAGAS1000_HOME força outra pasta (usada nos testes e para um backup portátil).
"""
from __future__ import annotations

import os
import shutil
import sys
from pathlib import Path

APP_NAME = "vagas1000"
FROZEN = bool(getattr(sys, "frozen", False))
BUNDLE = Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parent.parent))


def _home() -> Path:
    env = os.environ.get("VAGAS1000_HOME")
    if env:
        return Path(env)
    if FROZEN:
        return Path(os.environ.get("APPDATA", str(Path.home()))) / "vagas1000"
    return Path(__file__).resolve().parent.parent


HOME = _home()
DATA = HOME / "data"
OUT = HOME / "out"
LOGS = HOME / "logs"
CONFIG = HOME / "config"


def ensure_config() -> Path:
    """Garante config/ editável em HOME: copia os padrões do pacote na primeira execução."""
    CONFIG.mkdir(parents=True, exist_ok=True)
    src = BUNDLE / "config"
    if src.resolve() != CONFIG.resolve() and src.exists():
        for f in src.glob("*.json"):
            dst = CONFIG / f.name
            if not dst.exists():
                shutil.copy2(f, dst)
    return CONFIG


def config_file(name: str) -> Path:
    ensure_config()
    return CONFIG / name
