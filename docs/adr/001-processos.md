# ADR 001 — Processos separados

**Estado:** observado na versão 1.7.1; registro retrospectivo.

**Contexto.** A coleta pode ser longa e o painel usa WebView2, enquanto a janela principal usa Tk.

**Decisão observada.** O app inicia processos filhos com `--scrape` e `--janela-painel`; o painel é incorporado via Win32 e há fallback para o navegador. Progresso e comandos usam arquivos locais. [App](https://github.com/nataliatobiasdev/vagas-1000/blob/v1.7.1/app.py) · [Painel](https://github.com/nataliatobiasdev/vagas-1000/blob/v1.7.1/scraper/panel_window.py).

**Consequências observáveis.** O ciclo de vida e as falhas do painel e da coleta precisam ser acompanhados pela janela. A escolha histórica entre alternativas não está documentada aqui.
