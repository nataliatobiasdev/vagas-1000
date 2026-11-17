# Changelog

Formato [Keep a Changelog](https://keepachangelog.com/pt-BR/1.1.0/); versões seguem [SemVer](https://semver.org/lang/pt-BR/).

## Não lançado

## [1.3.0] - 2026-11-17

As abas do painel dentro da janela passam a funcionar de verdade, e o painel fica mais claro de ler e de usar (resultado de uma crítica visual).

### Corrigido
- **Painel dentro da janela**: o WebView2 entrega o fragmento da URL escapado (`#embed%7C%23/linkedin`), e o painel não reconhecia o modo embutido e mostrava as abas internas (Vagas / LinkedIn) duplicadas dentro do app. A página agora decodifica o fragmento e o autoteste do CI confere que o modo embutido ligou.
- O autoteste do painel embutido (CI) travava por 30 min quando o WebView2 não respondia: chamadas JavaScript ganharam prazo, o autoteste derruba a árvore de processos e o passo tem limite de 5 min. O log do processo filho agora sai em UTF-8.
- **Fontes sem leitura** deixam de aparecer com o ponto verde de "ok": ponto oco neutro e o resumo diz "N sem leitura".

### Alterado
- **Filtros**: a barra mostra só busca, veredito, ordenação e Cards/Tabela; o resto (empresa, modalidade, nota mínima, só novas, só internacionais, mostrar encerradas, buscar na descrição) fica no botão **Filtros**, que mostra quantos estão ativos e tem **Limpar filtros**. A barra fica fixa ao rolar a lista.
- **Números**: três cartões (vagas abertas, **elegíveis** em destaque, novas na execução); encerradas e empresas viraram uma linha de resumo.
- **Tecnologias**: a escolha é feita no painel Tecnologias; a lista só mostra, com ✕ para remover, as tecnologias ativas (antes havia duas listas com contagens diferentes).
- **Aba do LinkedIn**: tabela com 7 colunas em vez de 10; senioridade vai sob o nome da empresa, a observação em uma linha, e os requisitos ficam na página da vaga.
- Painéis recolhíveis com o resumo em destaque e a seta mais visível; rótulos em mono de 12 px.

### Acessibilidade
- Contornos de campos, seletores e chips com contraste mínimo de 3:1 (novo token `--border-strong`); checkboxes de 18 px, seletor de nota de 24 px e botões de 32 px.
- Tema claro: teal e texto terciário escurecidos para atingir 4,5:1 (`#0A7A74` e `#5F6985`).

## [1.2.0] - 2026-11-16

O painel passa a viver **dentro da janela do app**, ganha a aba do LinkedIn e fica mais compacto.

### Adicionado
- **Painel dentro da janela principal**: a janela ganha as abas **Início**, **Painel de vagas** e **LinkedIn**; o painel aparece nela (WebView2 como janela filha, do tamanho da área de conteúdo) em vez de abrir outra janela. Sem WebView2, abre no navegador, como antes.
- **Aba “LinkedIn · captura manual”** no painel: reúne as vagas importadas da captura manual, com as colunas da planilha (aderência, local, modelo, publicada, candidaturas, senioridade, requisitos, observações), busca, filtro por aderência e modelo, ordenação e link para o anúncio.

### Alterado
- Os painéis **Fontes**, **Por empresa** e **Tecnologias** ficam recolhidos em uma linha só, lado a lado; ao expandir, ocupam a largura inteira, com listas mais baixas.
- O CI ganhou um autoteste do painel embutido (janela filha com o tamanho e o conteúdo certos, troca de aba, fecha com a janela principal) e passa a rodar também em branches `ci/**`.

## [1.1.0] - 2026-11-16

O vagas1000 passa a ser um **banco de vagas**: cada vaga fica guardada por inteiro, mesmo depois de sair do ar.

### Adicionado
- **Registro completo por vaga**: campos padronizados (locais, contrato, área, time, salário, datas de publicação, edição e prazo, requisição, link de candidatura), descrição em HTML limpo, seções (requisitos, benefícios, etapas do processo) e o **payload bruto** de cada fonte.
- **Histórico de versões** (`job_versions`): se a fonte editar o texto, o salário ou o local, a versão anterior continua guardada; o painel mostra o que mudou e deixa ver a versão antiga.
- **Painel com cards padronizados** e **página completa de cada vaga** (resumo, descrição, seções, motivos da nota, dados do banco, versões, dados brutos), além da tabela; busca opcional na descrição; baixar o registro em JSON e imprimir.
- **Painéis recolhíveis**: Fontes, Vagas por empresa e Tecnologias mostram um resumo compacto e, abertos, uma lista rolável com busca e filtros que atuam na lista de vagas.
- **Painel dentro do app** (janela WebView2); abre no navegador se o WebView2 não estiver disponível.
- **Importar vagas de fora** (botão na janela e `python main.py --importar arquivo`): JSON, CSV ou tabela Markdown, como a captura do LinkedIn feita pelo Claude no Chrome. Entram como fonte própria, com nota, cards, página completa e registro bruto; importar de novo não duplica e nunca encerra vagas.
- `python main.py --exportar`: o banco inteiro (vagas abertas e encerradas, versões e payload bruto) em JSON.
- Janela com o acabamento macio do CAM: cantos arredondados anti-aliasados, sombras suaves, ícones, pílulas e card de progresso flutuante.

### Alterado
- Detalhes do Gupy e do Workday ficam em cache no banco (reabre só o que é novo ou tem mais de 7 dias); o limite de 40 vagas por empresa subiu para 150 por execução.
- A atualização nunca apaga o que já estava guardado: campo que a captura de hoje não trouxe mantém o valor anterior.
- Bancos antigos são migrados ao abrir (só acrescenta colunas e tabelas).
- Os JSON de cada execução ficam leves (sem HTML nem payload bruto); o completo é o `--exportar`.

### Corrigido
- Descrição cortada em 3.000 caracteres no painel.
- Vaga encerrada perdia a descrição quando o detalhe não era reaberto.
- Consultas com `ORDER BY` falhavam com `%TEMP%` bloqueado (`temp_store=MEMORY`).

## [1.0.0] - 2026-11-16

Primeira versão publicada em `nataliatobiasdev/vagas-1000`.

### Adicionado
- Captura de vagas de 54 empresas (Gupy, Greenhouse, Lever, Ashby, Workday e o portal da Stone), com nota, veredito de elegibilidade e histórico em SQLite.
- Janela do app com botão **Atualizar base**, números da base e barra de status estilo player; painel `dashboard.html` offline e relatório de vagas presenciais.
- Módulo opcional de busca no LinkedIn em modo seguro (instalação pelo código-fonte).
- Design system **Nevora** na janela, no painel, no site e no ícone, com Inter, Space Grotesk e JetBrains Mono empacotadas.
- Instalador Windows por usuário (PyInstaller + NSIS), com dados em `%APPDATA%\vagas1000`.
- CI (testes, empacotamento, teste de fumaça do `.exe` e instalador), Release por tag e documentação no GitHub Pages.
- Relatório de testes com os problemas encontrados e como resolvê-los.

### Corrigido
- A barra de status parava durante a atualização (`NameError` em `_flush_results`).
- Sem Chrome a execução inteira abortava; agora o Chrome abre só quando uma empresa precisa dele (Stone).
- Chrome falhava com “cannot create temp dir” em terminais com `%TEMP%` bloqueado; agora usa perfil e pasta temporária próprios.

### Removido
- Dicionário de empresas sem uso em `app.py` e scripts de instalação obsoletos (`setup.bat`, `setup.ps1`, `publicar-github.ps1`).

[1.2.0]: https://github.com/nataliatobiasdev/vagas-1000/releases/tag/v1.2.0
[1.1.0]: https://github.com/nataliatobiasdev/vagas-1000/releases/tag/v1.1.0
[1.0.0]: https://github.com/nataliatobiasdev/vagas-1000/releases/tag/v1.0.0
