# Como usar

## A janela

<img class="shot" src="/img/janela.png" alt="Janela do vagas1000 com os números da base, os botões e a barra de status">

| Elemento | O que faz |
| --- | --- |
| Cartões | Vagas abertas, elegíveis e empresas, lidos do banco local |
| **Atualizar base** | Captura as 54 empresas, grava no banco e regenera o painel |
| **Abrir painel** | Abre `out/dashboard.html` no navegador |
| **Abrir presenciais** | Abre o relatório de vagas presenciais por estado |
| **Abrir pasta** | Abre a pasta de dados |
| Barra inferior | Empresa em extração, progresso (“12 de 54”), tempo e erros, ao vivo |

A atualização leva alguns minutos. A maior parte do tempo é a Salesforce (Workday limita a velocidade) e a Stone (navegador). O app acompanha também uma execução iniciada pela linha de comando, lendo `out/status.json`.

## O painel

Filtros que importam no dia a dia:

- **Só elegíveis** + **Só internacionais**: vagas fora do Brasil em que você *pode* aplicar (remoto LATAM ou mundial).
- **Só novas**: o que apareceu desde a execução anterior.
- Nota mínima, empresa, modalidade (remoto, híbrido, presencial) e tecnologia.
- Clique numa linha para ver os motivos da nota e a descrição.

| Veredito | Significado |
| --- | --- |
| **ELIGIBLE** | Nota de pelo menos 70, local em que você pode aplicar e uma tecnologia do seu perfil |
| **MAYBE** | Abaixo do corte, sem tecnologia do perfil, ou com local ambíguo |
| **BLOCKED** | Título excluído ou local que exige estar em outro país |

## Linha de comando

Com o código-fonte (`run.bat` repassa os argumentos):

```bash
run.bat                         # captura tudo + painel
run.bat --only ciandt stone     # só algumas empresas
run.bat --painel                # só regenera o painel a partir do banco
run.bat --reavaliar             # reaplica o profile.json às vagas já salvas
run.bat --show --only stone     # com a janela do Chrome visível (depurar)
```

No app instalado o equivalente é `vagas1000.exe --scrape ...` (por exemplo `--scrape --painel`).

## Ajustar o perfil

Edite `config/profile.json` (em `%APPDATA%\vagas1000\config` no app instalado) e rode `--reavaliar`; não precisa capturar de novo. Os campos principais: `weights` (peso de título, tecnologia, senioridade e elegibilidade), `core_tech`, `title_include_*`, `title_exclude`, `eligibility_allow/block` e `eligible_min_score`. A lógica está em [Pontuação](/arquitetura/pontuacao).

## LinkedIn {#linkedin}

Só na instalação pelo código-fonte. O botão **Buscar no LinkedIn** usa a **sua** sessão já logada do Chrome (porta de depuração 9222), em modo seguro: 2 páginas por busca, últimas 24 horas, sem abrir o detalhe de cada vaga, pausas longas, **no máximo uma vez por dia** e parada imediata em CAPTCHA. É somente leitura: nunca clica em candidatura nem em mensagem. O relatório fica em `linkedin-jobs/out/linkedin-report.md`.

::: warning Termos do LinkedIn
Automatizar o LinkedIn pode contrariar os termos de uso da plataforma e levar a restrições na conta. O modo seguro reduz o risco, não o elimina.
:::
