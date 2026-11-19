# vagas1000

O vagas1000 é um aplicativo desktop para Windows que consulta fontes de vagas, normaliza e pontua resultados, grava histórico local e apresenta um painel HTML. A interface Tk, a coleta e o painel WebView2 são executados em processos distintos no modo empacotado. A integração opcional com o CAM escreve uma vaga pendente no SQLite local desse aplicativo.

**Linha de base auditada:** [`v1.7.1`](https://github.com/nataliatobiasdev/vagas-1000/tree/v1.7.1), commit `5beaa45`, em 19/11/2026. O documento descreve implementação observada, não uma arquitetura pretendida.

| Seção | Conteúdo |
| --- | --- |
| [Visões estruturais](/architecture/) | Contexto C4, contêineres e sequência em D2 |
| [Contratos e dados](/contratos) | Processos, arquivos, rede e integração CAM |
| [Build e operação](/operacao) | Empacotamento Windows, release e limites |
| [Decisões arquiteturais](/adr/) | ADRs retrospectivos separados das visões |

[Código-fonte](https://github.com/nataliatobiasdev/vagas-1000) · [Releases e instalador](https://github.com/nataliatobiasdev/vagas-1000/releases) · [Documentação do CAM](https://nataliatobiasdev.github.io/agregador-carreiras/)
