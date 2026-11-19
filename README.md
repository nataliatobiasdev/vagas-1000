# vagas1000

[![CI](https://github.com/nataliatobiasdev/vagas-1000/actions/workflows/ci.yml/badge.svg)](https://github.com/nataliatobiasdev/vagas-1000/actions/workflows/ci.yml)
[![Docs](https://github.com/nataliatobiasdev/vagas-1000/actions/workflows/docs.yml/badge.svg)](https://nataliatobiasdev.github.io/vagas-1000/)

App desktop para Windows que **captura as vagas de TI de 54 empresas**, pontua cada uma pelo seu perfil
(título, tecnologia, senioridade e se você pode aplicar do Brasil) e entrega um **painel offline** com o
que vale a pena. Quase tudo roda por API pública, sem abrir navegador; só a Stone usa Chrome.

**Documentação:** <https://nataliatobiasdev.github.io/vagas-1000/> · **Instalador:** [Releases](https://github.com/nataliatobiasdev/vagas-1000/releases)
· **Arquitetura e operação:** [docs/operacao.md](docs/operacao.md) · **Mudanças:** [CHANGELOG.md](CHANGELOG.md)

## Instalar

1. Baixe `vagas1000-Setup-X.Y.Z.exe` em [Releases](https://github.com/nataliatobiasdev/vagas-1000/releases) e execute
   (por usuário, sem administrador; o SmartScreen pode avisar “Editor desconhecido”: *Mais informações → Executar assim mesmo*).
2. Abra o **vagas1000** pelo atalho e clique em **Atualizar base**.

Seus dados ficam em `%APPDATA%\vagas1000` e **nunca** são apagados ao desinstalar. Precisa de Google Chrome só para a Stone.
Para rodar do código-fonte (Python 3.9+): `instalar.bat`. Detalhes em [Build e operação](docs/operacao.md).

## Interface e versões

A interface segue o design system **Nevora** (violeta e teal sobre neutros escuros; Space Grotesk, Inter e
JetBrains Mono empacotadas), igual ao [CAM](https://github.com/nataliatobiasdev/agregador-carreiras).
Versões em [SemVer](https://semver.org/lang/pt-BR/) com tag `vX.Y.Z`, CHANGELOG e instalador na Release; o fluxo é
branch → Pull Request → CI verde → merge ([Build e operação](docs/operacao.md)).

## Empresas

| Empresa | Portal | Adaptador | Nota composta |
|---|---|---|---|
| CI&T | jobs.lever.co/ciandt | `lever_api` | 99,0 |
| Stone | jornada.stone.com.br/vagas-abertas (portal próprio) | `stone_portal` | 96,5 |
| Zup Innovation | job-boards.greenhouse.io/linkedinzup | `greenhouse_api` | 96,0 |
| C6 Bank | job-boards.greenhouse.io/c6bank | `greenhouse_api` | 89,0 |
| Wellhub | job-boards.greenhouse.io/gympass | `greenhouse_api` | 85,0 |
| VTEX | job-boards.greenhouse.io/vtex | `greenhouse_api` | 62,0 |
| Nubank | jobs.ashbyhq.com/nubank | `ashby_api` | 86,5 |
| QuintoAndar | job-boards.greenhouse.io/quintoandar | `greenhouse_api` | 44,5 |
| Jusbrasil | job-boards.greenhouse.io/jusbrasil | `greenhouse_api` | 62,0 |
| BTG Pactual | job-boards.greenhouse.io/btgpactual | `greenhouse_api` | 87,5 |
| Banco Inter | job-boards.greenhouse.io/inter | `greenhouse_api` | 48,5 |
| XP Inc. | job-boards.greenhouse.io/xpinc | `greenhouse_api` | 46,0 |
| EBANX | job-boards.greenhouse.io/ebanx | `greenhouse_api` | 46,0 |
| Sezzle | job-boards.greenhouse.io/sezzle | `greenhouse_api` | 91,5 |
| Clara | job-boards.greenhouse.io/clara | `greenhouse_api` | 83,0 |
| Homeward | job-boards.greenhouse.io/homeward | `greenhouse_api` | 57,5 |
| Engine | job-boards.greenhouse.io/engine | `greenhouse_api` | 80,5 |
| Coderio | jobs.lever.co/coderio | `lever_api` | 54,0 |
| Luxury Presence | jobs.lever.co/luxurypresence | `lever_api` | 88,0 |
| Bluelight Consulting | jobs.lever.co/bluelightconsulting | `lever_api` | 87,0 |
| Infinity Constellation | jobs.ashbyhq.com/infinity-constellation | `ashby_api` | 81,5 |
| GIRO.TECH | girotech.gupy.io | `gupy` | 90,0 |
| ioasys | ioasys.gupy.io | `gupy` | 30,0 |
| Alpargatas | alpargatas.gupy.io | `gupy` | 27,0 |
| Afya | afya.gupy.io | `gupy` | 66,5 |
| Dock | dock.gupy.io | `gupy` | 30,0 |
| Canonical (fora da base) | job-boards.greenhouse.io/canonical | `greenhouse_api` | 75,0 |
| Turing (fora da base) | job-boards.greenhouse.io/turing | `greenhouse_api` | 70,5 |
| Nortal | job-boards.greenhouse.io/nortal | `greenhouse_api` | 64,0 |
| Inflect | job-boards.greenhouse.io/inflect | `greenhouse_api` | 60,0 |
| ília | job-boards.greenhouse.io/ilia | `greenhouse_api` | 60,0 |
| Sicredi | sicredi.gupy.io | `gupy` | 58,0 |
| PagSeguro | pagseguro.gupy.io | `gupy` | 57,0 |
| Porto Bank | porto.gupy.io | `gupy` | 70,0 |
| Stefanini | stefanini.gupy.io | `gupy` | 45,0 |
| Global Hitss | globalhitss.gupy.io | `gupy` | 40,0 |
| Softplan | softplan.gupy.io | `gupy` | 50,0 |
| Invillia | invillia.gupy.io | `gupy` | 45,0 |
| Valtech | job-boards.greenhouse.io/valtech | `greenhouse_api` | 65,0 |
| Monks | job-boards.greenhouse.io/monks | `greenhouse_api` | 60,0 |
| BYD Brasil | bydbrasil.gupy.io | `gupy` | 55,0 |
| Salesforce | salesforce.wd12.myworkdayjobs.com (Workday) | `workday` | 85,0 |
| Rede D'Or (saúde) | rededor.gupy.io | `gupy` | 55,0 |
| Assaí (atacado) | assai.gupy.io | `gupy` | 45,0 |
| Lojas Renner (varejo) | renner.gupy.io | `gupy` | 50,0 |
| PRIO (petróleo) | prio.gupy.io | `gupy` | 55,0 |
| Piracanjuba (alimentos) | piracanjuba.gupy.io | `gupy` | 35,0 |
| Bauducco (alimentos) | bauducco.gupy.io | `gupy` | 40,0 |
| iFood | boards.greenhouse.io/ifoodcarreiras | `greenhouse_api` | 80,0 |
| C&A Brasil | cea.gupy.io | `gupy` | 45,0 |
| Cogna Educação | cogna.gupy.io | `gupy` | 55,0 |
| Hospital Santa Helena | santahelena.gupy.io | `gupy` | 40,0 |
| AlmapBBDO (agência) | almapbbdo.gupy.io | `gupy` | 50,0 |
| Cacau Show (alimentos) | cacaushow.gupy.io | `gupy` | 45,0 |

**Salesforce** entra pelo **Workday** (`/wday/cxs/.../jobs`): lista paginada por POST e descrição por GET.
O Workday responde 429 quando aceleramos, então o coletor usa backoff (8–24 s) e pausas de 3–6 s.

### Busca externa (2026-11-16): quem tem vaga mas não tem feed público

A varredura na web confirmou mais empregadores. Alguns já entraram por feed público (**Salesforce** via
Workday, Canonical/Turing via Greenhouse); estes continuam sem feed automatizável:

- **EPAM** — Salesforce Architect, Remote in Brazil (careers.epam.com, sistema próprio).
- **BairesDev** — Go/Python sênior remoto (portal próprio; muitas vagas no LinkedIn).
- **EVT** — Desenvolvedor Salesforce Sênior PJ remoto (só LinkedIn).
- **BlueColtan** — Senior Salesforce Developer LATAM (Torre).
- **Airkit** — Salesforce Technical Architect Brazil Remote (board da Accel).
- **Argyle** — Software Engineer Europe/Brazil remote, USD 80–90k (board da Correlation Ventures).
- **Zucchetti** — software house italiana (Mogi Mirim/Limeira): site devolve 403 e não há board público;
  vagas aparecem no LinkedIn e no Remotive (ex.: Fullstack Developer remoto Brasil).
- **Toptal** (403), **Automattic/Deel** (sem feed), **GitLab** (sem vaga para Brasil).

**Marketplaces/e-commerce sem feed público** (checados em 2026-11-16): Mercado Livre, OLX, Enjoei,
Magalu, Americanas, Shopee, Dafiti, Netshoes, Rappi, Loggi e MadeiraMadeira usam portais próprios/JS
sem ATS público; a Shein publica só nos EUA. O **iFood** entrou pelo Greenhouse (`ifoodcarreiras`,
68 vagas, 30 no Brasil). Mercado Livre e OLX exigiriam scraper próprio (como a Stone).

**Setores checados em 2026-11-16:** educação (Cogna entrou; PUC-SP e Unifran sem vaga técnica; federais são
concurso), saúde (Rede D'Or e Santa Helena; Hapvida, Dasa, Amil, Omint e Unimed-POA sem board técnico),
convênios (Porto Saúde; Omint sem TI), agências (AlmapBBDO entrou; Ogilvy sem TI), restaurantes
(Cacau Show entrou; KFC e Bob's sem TI; McDonald's/Arcos Dorados sem board público) e órgãos públicos
(sem feed; SERPRO, DATAPREV e BNDES são concurso).

Boards agregadores úteis para acompanhar à mão: remote.com/jobs, remotive, Torre, Accel/Correlation
(e o LinkedIn da sua sessão). Eles listam “remote - Brazil only” em USD de empresas que não publicam ATS.

**Gupy:** a lista vem no `__NEXT_DATA__` do portal (SSR, sem Selenium) e a descrição em `/jobs/{id}` —
o adaptador abre o detalhe só das vagas que passaram nos filtros. Alguns portais da base já migraram
(`unico`, `picpay`, `atta`, `hiplatform` → 404) e ficaram fora; `Afya`/`Dock` estão sem vaga técnica hoje.
**Fora da base:** entraram Canonical e Turing (boards públicos com vaga worldwide/Brasil). GitLab tem 250
vagas, mas nenhuma para Brasil/Américas; BairesDev, Automattic, Toptal e Deel não têm feed público estável
(Toptal devolve 403) — exigiriam scraper próprio.

O bloco internacional (Sezzle, Clara, Homeward, Engine, Coderio, Luxury Presence, Bluelight) usa
`location_include` + `title_exclude` + `dedupe_by_title` para filtrar boards globais.

## Vagas internacionais (como aplicar)

A elegibilidade agora entende o formato dos boards globais:

| Local na vaga | Veredito | Por quê |
|---|---|---|
| `Brazil`, `São Paulo, SP`, `Remoto` | **ELIGIBLE** | você pode aplicar |
| `Remote - LATAM`, `Latin America`, `Worldwide/Anywhere` | **ELIGIBLE** | remoto contratando na região |
| `Remote - USA`, `Portugal`, `Bogota`, `Toronto`, `Palo Alto` | **BLOCKED** | exige presença em outro país |

No painel, abra **Filtros** e marque **“Só internacionais”** + veredito **“Só elegíveis”** (ou “Elegíveis + Talvez”) para ver
exatamente as vagas que dá para aplicar. Sem o filtro, o Brasil aparece junto. Na execução de 2026-11-16
eram **35 internacionais elegíveis** (a Canonical, com “Home based - Worldwide”, responde por boa parte;
Sezzle/Luxury Presence/Engine cobrem LATAM; Turing tem vagas no Brasil e “Global - Remote”).

BTG, Inter, XP e EBANX usam `title_include`: o board tem centenas de vagas de crédito/analista e o
filtro deixa entrar só engenharia/Salesforce (ex.: BTG 83 de 227, Inter 44 de 114). Sem o filtro, o
painel ficaria dominado por vaga que não é do seu perfil. As demais entram completas.

Todas vieram da base verificada (`tech_employer_base.json`) e foram checadas na fonte: o board precisa
estar vivo e listar vaga no Brasil. **Quase tudo roda por API pública** (Lever, Greenhouse, Ashby) — uma
requisição por empresa, com a descrição completa. Só a **Stone** usa Selenium (portal próprio, sem API).
Coinbase foi testada e ficou fora: o board devolve 403. Zup usa o board `linkedinzup` porque
`zupinnovation` estava sem vagas em 2026-11-16.

### Por que API e não o board HTML
O board novo do Greenhouse renderiza **no máximo 50 vagas** (sem "carregar mais") e a C6 tem 157 — a vaga
"Salesforce Sênior" ficava fora. A API traz todas e já inclui a descrição, o que também dispensa o passo
de abrir cada vaga (era o que fazia a CI&T gastar ~6 min).

## Rodar do código-fonte

**Instalador a partir do código:** dois cliques em **`instalar.bat`**: confere Python 3.9+ e Google Chrome, cria o
`.venv`, instala as dependências, roda os testes offline, cria os atalhos (**vagas1000 - abrir app** e
**vagas1000 - abrir painel**). Não agenda nada: a atualização é pelo botão.

**App (janela):** `app.bat` (ou o atalho). Botão **Atualizar base**, números da base e uma **barra estilo player**
com a empresa em extração, progresso (“12 de 54”), tempo e erros. Logs: `logs/scraper.log` e `logs/app-run.log`.

**Linha de comando:** `run.bat` (captura + painel), `run.bat --show --only stone`, `python main.py --painel`.

Saída em `out/`: `vagas-latest.json`, `vagas-latest.csv`, `dashboard.html` e cópias com data/hora
(as **60 execuções mais recentes**). Desenvolvimento, empacotamento e testes: [Build e operação](docs/operacao.md).

## LinkedIn (modo seguro, opcional)

O app tem o botão **Buscar no LinkedIn**. Ele usa o seu Chrome já logado (CDP, cópia do perfil em
`linkedin-jobs\.profile`), pega as **2 primeiras páginas** das buscas (últimas 24h, ordenadas por
data), **não abre a página de cada vaga**, faz pausas de 25–55 s entre páginas e 60–120 s entre buscas,
**1 execução por dia** (`--force` para repetir) e **para na hora em CAPTCHA/checkpoint**.

Relatório: `linkedin-jobs/out/linkedin-report.md` — por padrão **mais recente primeiro**
(`--sort match` para ordenar por aderência). Manual:
`linkedin-jobs\.venv\Scripts\python.exe linkedin-jobs\linkedin_jobs.py` (antes, `launch_chrome.py`).

> O LinkedIn não permite automação nos termos de uso. O modo seguro reduz o risco, não elimina; nunca
> clica em candidatura, mensagem ou perfil.

## Banco de dados e painel
Cada execução grava em `data/vagas.db` (SQLite) e regenera `out/dashboard.html`, que abre sozinho no navegador (funciona offline).
- **Vagas novas** e **encerradas** aparecem comparando com a execução anterior. Se uma empresa der erro ou trouxer 0 vagas, nenhuma vaga dela é marcada como encerrada.
- `python main.py --painel` regenera só o painel; `python main.py --reavaliar` reaplica o `config/profile.json` às vagas já gravadas (use depois de mexer em pesos/termos).
- Tabelas: `companies`, `runs`, `run_companies`, `jobs`, `job_snapshots` (nota/veredito por execução) e a view `v_open_jobs`. Abra o `.db` no DB Browser for SQLite ou use `sqlite3`.
- Importar um JSON antigo: `python -m scraper.db importar out\vagas-AAAAMMDD-HHMMSS.json`.

## Se alguma empresa falhar
- Uma empresa com erro não impede as outras: o erro dela fica em `out/vagas-latest.json` (campo `status`) e em `logs/scraper.log` (o log completo de cada execução, com data e hora).
- Se a janela do Chrome for fechada ou o navegador cair no meio, o robô abre um Chrome novo e repete **aquela** empresa uma vez.
- Se **todas** as empresas falharem, a execução **não** é gravada no banco: o painel continua mostrando a última execução boa.
- Se o Chrome nem abrir, só a Stone falha (as outras 53 seguem). Confira se o Google Chrome está instalado e veja o erro em `logs/scraper.log`.

## Testes (offline, sem Chrome)
```
python -m unittest discover -s tests -v
```
Os parsers rodam contra HTML capturado dos portais reais (`tests/fixtures`).

## Como funciona
- `scraper/collectors.py` — um coletor por fonte: API pública (Greenhouse, Lever, Ashby), Gupy (SSR), Workday e Selenium só para a Stone.
- `scraper/parsers.py` — HTML → `Job` (BeautifulSoup). Seletores estão só aqui.
- `scraper/filtering.py` — pontuação (título 30 / tecnologia 35 / senioridade 15 / elegibilidade 20) e veredito ELIGIBLE/MAYBE/BLOCKED.
- `scraper/paths.py` — onde ficam os arquivos (código-fonte × instalado). `scraper/theme.py` — tokens Nevora. `scraper/version.py` — versão.
- `scraper/db.py` — histórico em SQLite. `scraper/dashboard.py` + `scraper/templates/dashboard.html` — painel.
- `config/companies.json` — empresas e filtros de URL. `config/profile.json` — seu perfil e pesos.

## Vagas presenciais

No painel, o filtro de modalidade **“Presencial”** lista as vagas presenciais. (O relatório `presenciais.md` e o botão
“Abrir presenciais” foram removidos na 1.5.0.)

## Tempo de execução (medido em 2026-11-16, 54 empresas, 1.207 vagas)

| Empresa | Fonte | Tempo |
|---|---|---|
| Stone | Selenium (portal próprio) | 32,3 s (falhou nesta execução: portal devolveu 500; variou 30–75 s) |
| CI&T | Lever API | 28,3 s |
| Bluelight Consulting | Lever API | 11,1 s |
| Alpargatas | Gupy (SSR + detalhes) | 7,6 s |
| GIRO.TECH | Gupy (SSR + detalhes) | 7,3 s |
| ioasys | Gupy (SSR + detalhes) | 5,6 s |
| as outras 34 | APIs/Gupy | ~55 s no total |
| **Captura** | | **136 s** |
| **run.bat completo** | | **~2,5 min** |

Uma execução por dia custa **2–3 min** (varia com a rede e com a Stone); 7 dias ≈ 20 min. A Stone é o
único Selenium e domina o tempo; quando o portal dela responde 500 (aconteceu em 2026-11-16 16:00), a
empresa é marcada com erro e as vagas antigas **não** são encerradas — o próximo run recupera.

## Ampliar a base de empresas
A base verificada fica em `%USERPROFILE%\Downloads\tech_employer_base.json` (683 empresas, 219 portais, 17 ATS).
Para adicionar uma empresa em `config/companies.json`:
- **Lever / Greenhouse por API** (`lever_api` / `greenhouse_api` + `board_token`): uma requisição, lista completa
  e descrição. É o jeito preferido (rápido e estável).
- **Lever / Greenhouse pelo board** (`lever` / `greenhouse`): usa Selenium; só quando a API não servir.
- **Ashby** (`ashby_api` + `board_token`): API pública, também traz faixa de compensação quando publicada.
- **Boards grandes e genéricos**: use `title_include` (regex no título) para entrar só engenharia/Salesforce —
  é o que BTG, Inter, XP e EBANX fazem; sem isso o painel enche de vaga de crédito/vendas.
- **Board global (contrata no mundo/LATAM)**: use `location_include` (ex.: `brazil|latam|latin america`) para
  deixar de fora `Remote - USA`/Europa, `title_exclude` para cortar júnior/vendas e `dedupe_by_title: true`
  para colapsar a mesma vaga publicada em vários países (Sezzle, Clara, Homeward, Engine, Coderio, Luxury Presence).
- **Gupy** (`gupy` + `board_url`): portal SSR; a lista vem no `__NEXT_DATA__` e a descrição em `/jobs/{id}`.
- **Outros ATS** (SmartRecruiters, Workable, Workday...): exigem coletor novo. SmartRecruiters tem API
  pública e é o próximo mais barato; Workday/iCIMS são HTML/JS e os mais frágeis.

Regra prática: confira com `python main.py --only <company_id>` antes de rodar a base inteira.

## Limites conhecidos
- Portais mudam de layout sem aviso: se uma empresa vier com 0 vagas, rode `python main.py --show --only <empresa>` e confira os seletores em `scraper/parsers.py`; os fixtures em `tests/fixtures` mostram o HTML esperado.
- Stone: paginação (6 vagas + 4 na página 2 = 10) e abertura do detalhe foram exercitadas no Chrome real em 2026-11-16.
- O painel é um arquivo HTML único (offline), não precisa de servidor.
- Cortesia: pausas de 1–2 s entre páginas; sem login, sem burlar bloqueios. Respeite os termos dos sites.
