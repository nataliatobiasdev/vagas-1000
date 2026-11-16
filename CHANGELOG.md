# Changelog

Formato [Keep a Changelog](https://keepachangelog.com/pt-BR/1.1.0/); versões seguem [SemVer](https://semver.org/lang/pt-BR/).

## Não lançado

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

[1.0.0]: https://github.com/nataliatobiasdev/vagas-1000/releases/tag/v1.0.0
