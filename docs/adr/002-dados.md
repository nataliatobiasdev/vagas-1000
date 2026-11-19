# ADR 002 — Persistência e falhas por fonte

**Estado:** observado na versão 1.7.1; registro retrospectivo.

**Contexto.** Portais podem falhar ou fornecer apenas uma amostra de publicações.

**Decisão observada.** O runner mantém status por fonte; o banco guarda vagas, versões e eventos. Uma fonte falha ou vazia não fecha vagas anteriores, e fontes marcadas `partial_feed` não fecham vagas ausentes. [Runner](https://github.com/nataliatobiasdev/vagas-1000/blob/v1.7.1/scraper/runner.py) · [Banco](https://github.com/nataliatobiasdev/vagas-1000/blob/v1.7.1/scraper/db.py).

**Consequências observáveis.** Uma fonte sem leitura deixa vagas anteriores sem confirmação; o feed parcial pode manter vagas que já não estão disponíveis. A ausência no feed não constitui prova de encerramento.
