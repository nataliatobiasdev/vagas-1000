# Rodar e contribuir

Requisitos: **Python 3.9+** (o CI usa 3.12) e Google Chrome. Não há Node no app; Node só serve para esta documentação.

```bash
git clone https://github.com/nataliatobiasdev/vagas-1000.git
cd vagas-1000
python -m venv .venv
.venv\Scripts\pip install -r requirements-dev.txt
.venv\Scripts\python app.py          # abre a janela
```

| Comando | O que faz |
| --- | --- |
| `python -m unittest discover -s tests` | 51 testes offline (sem rede, sem Chrome) |
| `python main.py --only ciandt --no-open` | Captura uma empresa pela linha de comando |
| `python main.py --painel` | Regenera o painel a partir do banco |
| `python scripts/make_icon.py` | Redesenha o ícone e os favicons |
| `python scripts/build_fonts.py` | Regera os WOFF2 do painel |
| `pyinstaller vagas1000.spec` | Empacota em `dist/vagas1000/` |
| `makensis /DVERSION=X.Y.Z installer\vagas1000.nsi` | Monta o instalador |

## Onde mexer

| Quero… | Onde |
| --- | --- |
| Acrescentar uma empresa | `config/companies.json` (escolha um `adapter` existente) |
| Ajustar a nota | `config/profile.json` e `scraper/filtering.py` |
| Uma fonte nova de vagas | Função `collect_*` em `scraper/collectors.py`, registrada em `COLLECTORS`, com parser e fixture em `tests/` |
| Mudar uma cor ou fonte | `scraper/theme.py`, o CSS do painel e o CSS do site |
| Mudar o número da versão | `scraper/version.py` + `CHANGELOG.md` ([Versionamento](/versionamento)) |

## Fluxo de contribuição

Mesmo do CAM: trabalhe em um branch, abra um Pull Request e espere o **CI** ficar verde. Mudou algo em `docs/`? O workflow **Docs** valida o build do site no PR e publica no Pages depois do merge na `main`.

## Esta documentação

```bash
cd docs
pnpm install
pnpm dev            # http://localhost:5173/vagas-1000/
```
