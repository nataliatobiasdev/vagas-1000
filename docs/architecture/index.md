# Visões estruturais

Os diagramas descrevem a versão auditada; os `.d2` são as fontes editáveis e os SVGs foram gerados com D2 0.9.0, tema 200 e layout ELK. *Contêiner* em C4 indica unidade executável ou armazenamento, não Docker.

Para regenerar um diagrama na raiz do repositório, use `d2 docs/architecture/01-c4-context.d2 docs/public/architecture/01-c4-context.svg`; repita para os outros dois. O workflow existente compila os SVGs já versionados e não verifica automaticamente se estão sincronizados com as fontes D2.

## C4 nível 1 — contexto

![Contexto do vagas1000](/architecture/01-c4-context.svg)

[Fonte D2](https://github.com/nataliatobiasdev/vagas-1000/blob/main/docs/architecture/01-c4-context.d2) · [Coletores](https://github.com/nataliatobiasdev/vagas-1000/blob/v1.7.1/scraper/collectors.py) · [Ponte CAM](https://github.com/nataliatobiasdev/vagas-1000/blob/v1.7.1/scraper/panel_window.py)

A coleta lê portais pela rede. O CAM é local e opcional; o vagas1000 não envia candidaturas. A busca LinkedIn automatizada é um fluxo separado disponível a partir do código-fonte, não incluído no executável padrão.

## C4 nível 2 — contêineres

![Contêineres do vagas1000 no Windows](/architecture/02-c4-container.svg)

[Fonte D2](https://github.com/nataliatobiasdev/vagas-1000/blob/main/docs/architecture/02-c4-container.d2) · [Interface](https://github.com/nataliatobiasdev/vagas-1000/blob/v1.7.1/app.py) · [Runner](https://github.com/nataliatobiasdev/vagas-1000/blob/v1.7.1/scraper/runner.py) · [Caminhos](https://github.com/nataliatobiasdev/vagas-1000/blob/v1.7.1/scraper/paths.py)

No aplicativo empacotado, a própria imagem `vagas1000.exe` é iniciada novamente com `--scrape` ou `--janela-painel`. WebView2 é hospedado pelo processo de painel e sua janela é incorporada ao Tk via APIs Win32; se falhar, o HTML abre no navegador padrão. Stone usa Chrome/ChromeDriver sob demanda; as demais fontes configuradas não exigem Chrome.

## Sequência — atualizar base

![Sequência de captura](/architecture/03-sequence-core-flow.svg)

[Fonte D2](https://github.com/nataliatobiasdev/vagas-1000/blob/main/docs/architecture/03-sequence-core-flow.d2) · [Entrada CLI](https://github.com/nataliatobiasdev/vagas-1000/blob/v1.7.1/main.py) · [Persistência](https://github.com/nataliatobiasdev/vagas-1000/blob/v1.7.1/scraper/db.py)

A sequência representa uma execução com pelo menos uma fonte bem-sucedida. A falha de uma fonte é registrada sem interromper as outras; se todas falharem, o runner não grava uma execução no banco. A ausência de uma vaga em uma fonte parcial não confirma encerramento.
