"""Onde ficam os arquivos do vagas1000.

- BUNDLE: recursos somente-leitura que vão junto com o programa (config padrão, modelo do painel).
- HOME:   pasta gravável do usuário (banco, saídas, logs e a cópia editável da configuração).

Em desenvolvimento (rodando do código-fonte) as duas são a raiz do projeto, como sempre foi.
Instalado (PyInstaller), HOME é %APPDATA%\\vagas1000 — o desinstalador nunca apaga essa pasta.
A variável VAGAS1000_HOME força outra pasta (usada nos testes e para um backup portátil).
"""
from __future__ import annotations

import os
import json
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
        # Uma única migração adiciona as novas fontes sem substituir edições do usuário.
        default_file, user_file = src / 'companies.json', CONFIG / 'companies.json'
        if default_file.exists() and user_file.exists():
            user = json.loads(user_file.read_text(encoding='utf-8'))
            migration = 'fontes_salesforce_20261119'
            applied = user.get('_migrations', [])
            if migration not in applied:
                defaults = json.loads(default_file.read_text(encoding='utf-8'))
                new_ids = {'caixavidaeprevidencia','4mk','claranet','compass','webjump','softdesign',
                           'vivodigital','gruposysmap','numen','vetta','gaugecarreiras','xfckvnq',
                           'brightwheel','leanlayer','collective','truelogic','go-nimbly','andela',
                           'sisense','creatoriq','gft'}
                have = {c['company_id'] for c in user['companies']}
                user['companies'].extend(c for c in defaults['companies'] if c['company_id'] in new_ids and c['company_id'] not in have)
                user['_migrations'] = [*applied, migration]
                backup = user_file.with_name('companies.pre-fontes-salesforce-20261119.json')
                if not backup.exists():
                    shutil.copy2(user_file, backup)
                tmp = user_file.with_suffix('.json.tmp')
                tmp.write_text(json.dumps(user, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
                tmp.replace(user_file)
            migration = 'gft_feed_parcial_20261119'
            applied = user.get('_migrations', [])
            if migration not in applied:
                defaults = json.loads(default_file.read_text(encoding='utf-8'))
                have = {c['company_id'] for c in user['companies']}
                user['companies'].extend(c for c in defaults['companies'] if c['company_id'] == 'gft_rss' and c['company_id'] not in have)
                user['_migrations'] = [*applied, migration]
                backup = user_file.with_name('companies.pre-gft-feed-20261119.json')
                if not backup.exists():
                    shutil.copy2(user_file, backup)
                tmp = user_file.with_suffix('.json.tmp')
                tmp.write_text(json.dumps(user, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
                tmp.replace(user_file)
    return CONFIG


def config_file(name: str) -> Path:
    ensure_config()
    return CONFIG / name
