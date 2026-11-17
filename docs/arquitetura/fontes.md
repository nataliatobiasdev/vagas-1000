# Fontes de vagas

54 empresas em `config/companies.json`, em 6 tipos de fonte. O campo `adapter` de cada empresa escolhe o coletor em `scraper/collectors.py`.

| Adaptador | Empresas | Como lê | Precisa de Chrome |
| --- | --- | --- | --- |
| `gupy` | 24 | Lista no `__NEXT_DATA__` do portal (SSR); descrição em `/jobs/{id}` só das vagas que passaram nos filtros | Não |
| `greenhouse_api` | 22 | API pública do board, com a descrição completa | Não |
| `lever_api` | 4 | API pública do Lever | Não |
| `ashby_api` | 2 | API pública do Ashby | Não |
| `workday` | 1 (Salesforce) | `POST /wday/cxs/.../jobs` paginado e descrição por `GET` | Não |
| `stone_portal` | 1 (Stone) | Selenium: portal próprio sem API, paginação por clique | **Sim** |

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

- **Workday responde 429** quando a velocidade sobe. O coletor usa recuo (8 a 24 s) e pausas de 3 a 6 s, e ainda assim algumas descrições falham (veja o [relatório de testes](/qualidade/relatorio)). A Salesforce leva ~85 s, a maior parte do tempo da captura sem navegador.
- **Gupy**: alguns portais migraram e hoje respondem 404 (`unico`, `picpay`, `atta`, `hiplatform`), por isso ficaram fora. Afya e Dock estão sem vaga técnica hoje.
- **Sem feed público**: Mercado Livre, OLX, Magalu, EPAM, BairesDev e outras usam portal próprio ou só LinkedIn. Entrar exigiria um scraper à parte, como o da Stone.
- **Coinbase** devolve 403; **Toptal** também.

## Acrescentar uma empresa

1. Descubra o ATS: `jobs.lever.co/x`, `job-boards.greenhouse.io/x`, `jobs.ashbyhq.com/x` ou `x.gupy.io`.
2. Acrescente uma entrada em `companies.json` com `company_id`, `name`, `adapter`, `board_url` (e `board_token` quando for API).
3. Rode `python main.py --only x --no-open` e confira o log; depois `python main.py --painel`.
