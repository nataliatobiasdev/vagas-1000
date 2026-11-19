# ADR 003 — Integração local com o CAM

**Estado:** observado na versão 1.7.1; registro retrospectivo.

**Contexto.** A pessoa usuária pode encaminhar uma vaga para acompanhamento sem criar automaticamente uma candidatura enviada.

**Decisão observada.** A ponte `pywebview.api.add_to_cam` valida a vaga e grava JSON em `vagas1000_inbox` no banco SQLite padrão do CAM. Os métodos de estado consultam a mesma tabela. [Ponte](https://github.com/nataliatobiasdev/vagas-1000/blob/v1.7.1/scraper/panel_window.py) · [Schema CAM](https://github.com/nataliatobiasdev/agregador-carreiras/blob/main/src/main/db/migrations/0002_vagas1000.sql).

**Consequências observáveis.** O banco e a migração do CAM precisam existir no caminho padrão. A integração por escrita direta acopla os dois aplicativos ao esquema; a confirmação de candidatura é feita no CAM, e não no portal de origem.
