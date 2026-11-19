# Decisões arquiteturais

Os ADRs são **registros retrospectivos da arquitetura observada** na tag `v1.7.1`. O código comprova o comportamento; alternativas consideradas e razões históricas não foram documentadas de forma suficiente para serem afirmadas.

| ADR | Estado observado |
| --- | --- |
| [001 — Processos separados](./001-processos) | Tk, coleta e painel com ciclos de vida próprios |
| [002 — Persistência e falhas](./002-dados) | SQLite e status por fonte preservam histórico |
| [003 — Integração local](./003-integracao) | Inbox no banco do CAM |
