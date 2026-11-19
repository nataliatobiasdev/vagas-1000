# Fontes de vagas

As 76 fontes do cadastro padrão da versão 1.7.1 estão em `config/companies.json`. O campo `adapter` escolhe o coletor em `scraper/collectors.py`; uma das fontes é o feed parcial adicional da GFT. Os cadastros existentes são preservados na migração do aplicativo instalado.

| Adaptador | Fontes | Como lê | Precisa de Chrome |
| --- | --- | --- | --- |
| `gupy` | 36 | Lista no `__NEXT_DATA__` do portal (SSR); descrição em `/jobs/{id}` só das vagas que passaram nos filtros | Não |
| `greenhouse_api` | 22 | API pública do board, com a descrição completa | Não |
| `lever_api` | 4 | API pública do Lever | Não |
| `ashby_api` | 10 | API pública do Ashby | Não |
| `workday` | 1 (Salesforce) | `POST /wday/cxs/.../jobs` paginado e descrição por `GET` | Não |
| `stone_portal` | 1 (Stone) | Selenium: portal próprio sem API, paginação por clique | **Sim** |
| `gft` | 1 (GFT) | Lista pública paginada, com validação do total e leitura dos detalhes | Não |
| `gft_rss` | 1 (GFT) | Feed público de publicações recentes; cobertura parcial | Não |

A Jobgether não foi ativada: seu retorno apresentou timeout na validação. O feed da GFT não é uma segunda listagem completa: as vagas ausentes nele não são automaticamente encerradas e uma vaga pode aparecer nas duas fontes. A listagem completa pode responder 403; nesse caso as vagas guardadas são preservadas.

Existem ainda os adaptadores `lever` e `greenhouse` (HTML via Selenium), mantidos como alternativa; nenhuma empresa os usa hoje.

## O que cada fonte entrega

Todas as fontes guardam o payload original em `raw`. Os campos padronizados dependem do que a fonte publica:

| Campo | Greenhouse | Lever | Ashby | Gupy | Workday |
| --- | --- | --- | --- | --- | --- |
| Data de publicação | `first_published` | `createdAt` | `publishedAt` | `publishedAt` | `startDate` |
| Última edição | `updated_at` | — | — | — | — |
| Prazo de inscrição | `application_deadline` | — | — | `expiresAt` | — |
| Faixa salarial | `pay_input_ranges` | `salaryRange` | `compensation` | — | — |
| Vários locais | escritórios | `allLocations` | `secondaryLocations` | — | `additionalLocations` |
| Requisição | `requisition_id` | — | — | `code` | `jobReqId` |
| Seções | — | listas (requisitos…) | — | requisitos, responsabilidades, **etapas do processo** | — |
| Descrição em HTML | `content` | `description` | `descriptionHtml` | `description` | `jobDescription` |

A Stone (Selenium) traz título, local, área e a descrição do detalhe.

## Filtros por empresa

Boards globais têm centenas de vagas fora do seu alcance. Cada empresa pode declarar:

| Campo | Efeito |
| --- | --- |
| `title_include` | Só entram vagas cujo título contenha um destes termos (BTG, Inter, XP, EBANX) |
| `title_exclude` | Descarta títulos com estes termos |
| `location_include` | Só entram vagas cujo local contenha um destes termos |
| `dedupe_by_title` | Colapsa vagas de mesmo título publicadas em vários países |
| `fetch_details` | Liga ou desliga a leitura do detalhe |

O bloco internacional (Sezzle, Clara, Homeward, Engine, Coderio, Luxury Presence, Bluelight) usa `location_include` + `title_exclude` + `dedupe_by_title`.

## Limites conhecidos

- **Workday pode responder 429**. O coletor aplica esperas e respeita `Retry-After`; esperas superiores a um minuto adiam a fonte para outra execução. Algumas descrições podem falhar mesmo quando a lista responde.
- **Gupy**: alguns portais migraram e hoje respondem 404 (`unico`, `picpay`, `atta`, `hiplatform`), por isso ficaram fora. Afya e Dock estão sem vaga técnica hoje.
- **Sem feed público**: Mercado Livre, OLX, Magalu, EPAM, BairesDev e outras usam portal próprio ou só LinkedIn. Entrar exigiria um scraper à parte, como o da Stone.
- **Coinbase** devolve 403; **Toptal** também.

## Acrescentar uma empresa

1. Descubra o ATS: `jobs.lever.co/x`, `job-boards.greenhouse.io/x`, `jobs.ashbyhq.com/x` ou `x.gupy.io`.
2. Acrescente uma entrada em `companies.json` com `company_id`, `name`, `adapter`, `board_url` (e `board_token` quando for API).
3. Rode `python main.py --only x --no-open` e confira o log; depois `python main.py --painel`.
