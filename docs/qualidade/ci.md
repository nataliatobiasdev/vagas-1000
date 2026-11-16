# CI e GitHub Pages

Três workflows, cada um com um trabalho só. É o mesmo desenho do CAM: o CI valida, o Docs publica o site, o Release publica o instalador.

| Workflow | Quando roda | O que faz |
| --- | --- | --- |
| `ci.yml` | Todo PR e push na `main` | Testes, empacota, **teste de fumaça do `.exe`**, gera o instalador e o guarda como artefato |
| `docs.yml` | PR (só valida) e push na `main` que altere `docs/` | Build do VitePress e publicação no Pages |
| `release.yml` | Tag `v*` | Confere a versão, gera o instalador e cria a Release |

## ci.yml

Em `windows-latest`, timeout de 30 min:

```mermaid
flowchart LR
  A[checkout] --> B["Python 3.12<br/>+ requirements-dev"] --> C["unittest<br/>51 testes"] --> D[version_info] --> E["PyInstaller<br/>vagas1000.spec"] --> F["fumaça:<br/>vagas1000.exe --scrape --painel"] --> G["NSIS<br/>makensis"] --> H["artefato<br/>vagas1000-Setup-*.exe"]
```

O **teste de fumaça** abre o executável empacotado com `VAGAS1000_HOME` numa pasta temporária e exige que `out/dashboard.html` e `config/companies.json` existam. Ele pega o que o teste unitário não pega: arquivo de dados esquecido na spec, importação que só falha congelada.

Para obter o instalador: aba **Actions** → run verde → artefato `installer`.

## docs.yml e o Pages

Roda no Ubuntu e é **o único workflow que publica no Pages**.

```mermaid
flowchart LR
  P["PR que muda docs/"] --> B1["build VitePress<br/>(só valida)"]
  M["push na main<br/>em docs/ ou no workflow"] --> B2["configure-pages<br/>pnpm build"] --> U["upload-pages-artifact<br/>docs/.vitepress/dist"] --> D["deploy-pages<br/>ambiente github-pages"]
  W["Run workflow<br/>(manual)"] --> B2
```

| Configuração | Valor |
| --- | --- |
| Fonte do Pages (Settings → Pages) | **GitHub Actions** |
| Endereço | `https://nataliatobiasdev.github.io/vagas-1000/` |
| Concorrência | Um deploy por ref; o mais novo cancela o anterior |
| Histórico completo (`fetch-depth: 0`) | Necessário para o “Atualizado em” de cada página |

::: warning Um só publicador
Dois workflows publicando no mesmo ambiente `github-pages` se sobrescrevem: vence o último deploy. Foi o que aconteceu no CAM quando o modelo “Static HTML” do GitHub criou um `static.yml`. Ao ativar o Pages, **não aceite nenhum modelo sugerido**: o `docs.yml` já cobre o deploy.
:::

## Primeiro uso

1. Faça o push da `main`.
2. *Settings → Pages → Build and deployment → Source: **GitHub Actions***.
3. Rode o workflow **Docs** manualmente (*Actions → Docs → Run workflow*) na primeira vez, porque o push inicial pode ter acontecido antes de o Pages estar ativo.
