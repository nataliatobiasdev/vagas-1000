# Banco e arquivos

SQLite local em `data/vagas.db` (`%APPDATA%\vagas1000\data` no app instalado). Nada sai da sua máquina.

## Tabelas

| Tabela | Conteúdo |
| --- | --- |
| `companies` | As empresas da configuração, com adaptador e nota composta |
| `runs` | Uma linha por execução: total, elegíveis, novas e encerradas |
| `run_companies` | Resultado de cada empresa em cada execução (ok, quantidade, erro) |
| `jobs` | Uma linha por vaga (`job_key`), com nota, veredito, tecnologias, motivos, primeira e última vez vista |
| `job_snapshots` | Nota e veredito de cada vaga em cada execução (histórico) |
| `v_open_jobs` | Visão das vagas abertas, ordenadas por veredito e nota |

## Regras de ciclo de vida

```mermaid
stateDiagram-v2
  [*] --> open: aparece numa execução
  open --> open: continua aparecendo
  open --> closed: a empresa respondeu e a vaga não veio
  closed --> open: volta a aparecer
```

- Uma vaga só é marcada como **encerrada** se a empresa dela respondeu com sucesso naquela execução. Empresa fora do ar não encerra nada.
- Se **todas** as empresas falharem, a execução não é gravada.
- “Novas” são as de `first_run_id` igual ao da última execução.

## Saídas

| Arquivo | O que é |
| --- | --- |
| `out/dashboard.html` | Painel offline: dados, estilos e fontes embutidos (~3,6 MB) |
| `out/presenciais.md` | Vagas presenciais agrupadas por estado e cidade |
| `out/vagas-latest.json` e `.csv` | Captura completa, com `status` por empresa |
| `out/vagas-AAAAMMDD-HHMMSS.*` | Cópias de cada execução; o projeto guarda as **60 mais recentes** |
| `out/status.json` | Progresso da execução em andamento (a janela lê a cada 500 ms) |
| `logs/scraper.log` | Log detalhado de cada execução |

## Backup

Copie a pasta `%APPDATA%\vagas1000` (ou só `data\vagas.db` e `config\`). Para usar outra pasta, defina `VAGAS1000_HOME` antes de abrir o app.
