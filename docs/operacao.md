# Build, distribuição e operação

## Build e release

`vagas1000.spec` empacota `app.py` e inclui configurações, template do painel, fontes, Selenium e dependências do pywebview. O resultado é uma pasta com `vagas1000.exe` e dependências, sem Python separado para a pessoa usuária. O script NSIS instala por usuário em `%LOCALAPPDATA%/Programs/vagas1000` por padrão, permite alterar diretório e preserva `%APPDATA%/vagas1000` na desinstalação. [Spec](https://github.com/nataliatobiasdev/vagas-1000/blob/v1.7.1/vagas1000.spec) · [NSIS](https://github.com/nataliatobiasdev/vagas-1000/blob/v1.7.1/installer/vagas1000.nsi).

O workflow de release em Windows verifica a tag contra `scraper/version.py`, executa testes, gera metadados, empacota com PyInstaller e NSIS e anexa o instalador à GitHub Release. O código auditado não configura assinatura de código ou atualizador automático. A versão 1.7.1 está em [Releases](https://github.com/nataliatobiasdev/vagas-1000/releases/tag/v1.7.1). [Workflow](https://github.com/nataliatobiasdev/vagas-1000/blob/v1.7.1/.github/workflows/release.yml).

## Operação e falhas

- A atualização é iniciada pela pessoa usuária; não há agendamento automático identificado no aplicativo.
- `403` significa recusa de acesso do portal. `429` sinaliza limitação; o coletor respeita `Retry-After` e adia a fonte quando a espera solicitada supera um minuto. Essas respostas não comprovam que a fonte deixou de ter vagas.
- O Workday limita requisições e o portal GFT pode recusar acesso; o feed GFT é uma amostra recente, não substituto completo da listagem. Revise `logs/scraper.log` e use a função de refazer fontes com erro quando apropriado.
- A pontuação compara termos, senioridade e local com `profile.json`; não comprova todos os requisitos ou preferências. Vagas sem descrição ou com local ambíguo podem ficar como `MAYBE`. [Filtro](https://github.com/nataliatobiasdev/vagas-1000/blob/v1.7.1/scraper/filtering.py).

## GitHub Pages

O [workflow Docs](https://github.com/nataliatobiasdev/vagas-1000/blob/v1.7.1/.github/workflows/docs.yml) valida VitePress em PR e publica em `main` quando `docs/**` muda. Os SVGs D2 versionados são arquivos estáticos; D2 não é necessário em tempo de execução do site.
