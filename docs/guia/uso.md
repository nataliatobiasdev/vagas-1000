# Como usar

## A janela

<img class="shot" src="/img/janela.png" alt="Janela do vagas1000 com os números da base, os botões e a barra de status">

| Elemento | O que faz |
| --- | --- |
| Cartões | Vagas abertas, elegíveis e empresas, lidos do banco local |
| **Atualizar base** | Captura as 54 empresas, grava no banco e regenera o painel |
| Abas **Início**, **Painel de vagas** e **LinkedIn** | Trocam o conteúdo da própria janela: o painel (`out/dashboard.html`) aparece dentro dela, sem abrir outra |
| **Abrir painel** | Atalho para a aba **Painel de vagas** |
| **Abrir presenciais** | Abre o relatório de vagas presenciais por estado |
| **Abrir pasta** | Abre a pasta de dados |
| **Importar vagas** | Traz vagas captadas fora do app (LinkedIn, planilha) para o banco: veja [Seu banco de vagas](/guia/banco-de-vagas#trazer-vagas-de-fora-linkedin-planilha) |
| Barra inferior | Empresa em extração, progresso (“12 de 54”), tempo e erros, ao vivo |

A atualização leva alguns minutos. A maior parte do tempo é a Salesforce (Workday limita a velocidade) e a Stone (navegador). O app acompanha também uma execução iniciada pela linha de comando, lendo `out/status.json`.

## O painel

A aba **Painel de vagas** (ou o botão **Abrir painel**) mostra o painel **dentro da janela do vagas1000**, sem abrir outra janela nem o Chrome. Se o WebView2 do Windows não estiver disponível, ele abre no navegador padrão, e o conteúdo é o mesmo. Fora do app, o `dashboard.html` tem as mesmas abas no topo da página.

No topo ficam os números e **três painéis curtos, lado a lado, que recolhem e expandem** (a escolha fica guardada). Recolhidos, cada um é uma linha só; ao expandir, o painel ocupa a largura inteira:

| Painel | Recolhido | Expandido |
| --- | --- | --- |
| **Fontes** | Quantas empresas, quantas com vagas e quantas com erro | Lista rolável com filtro por nome e por “com erro” ou “sem vagas” |
| **Por empresa** | Barra com a distribuição de vereditos e o total de vagas | Todas as empresas, com busca e ordenação; clicar numa empresa filtra a lista |
| **Tecnologias** | As 3 principais, com a contagem | Todas, com “elegíveis/abertas”; clicar numa tecnologia filtra a lista |

### Aba LinkedIn

A aba **LinkedIn** reúne as vagas da **captura manual** (a planilha que o Claude monta no Chrome e você traz com **Importar vagas**). Mostra as colunas da planilha (aderência, local, modelo, publicada, candidaturas, senioridade, requisitos e observações), com busca, filtro por aderência (Alta, Média, Baixa) e por modelo, e ordenação. Clicar numa linha abre a página completa da vaga; **abrir** leva ao anúncio no LinkedIn.

Abaixo, a lista de vagas em **cards** (ou tabela), com filtros: **só elegíveis** e **só internacionais** (vagas fora do Brasil em que você *pode* aplicar), **só novas**, nota mínima, empresa, modalidade, tecnologia e busca (inclusive na descrição). Clique numa vaga para abrir a **página completa**: veja [Seu banco de vagas](/guia/banco-de-vagas).

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
run.bat --exportar              # banco inteiro em out/banco-vagas.json
run.bat --importar captura.json # vagas de fora (LinkedIn, planilha) para o banco
```

No app instalado o equivalente é `vagas1000.exe --scrape ...` (por exemplo `--scrape --painel`).

## Ajustar o perfil

Edite `config/profile.json` (em `%APPDATA%\vagas1000\config` no app instalado) e rode `--reavaliar`; não precisa capturar de novo. Os campos principais: `weights` (peso de título, tecnologia, senioridade e elegibilidade), `core_tech`, `title_include_*`, `title_exclude`, `eligibility_allow/block` e `eligible_min_score`. A lógica está em [Pontuação](/arquitetura/pontuacao).

## LinkedIn {#linkedin}

Só na instalação pelo código-fonte. O botão **Buscar no LinkedIn** usa a **sua** sessão já logada do Chrome (porta de depuração 9222), em modo seguro: 2 páginas por busca, últimas 24 horas, sem abrir o detalhe de cada vaga, pausas longas, **no máximo uma vez por dia** e parada imediata em CAPTCHA. É somente leitura: nunca clica em candidatura nem em mensagem. O relatório fica em `linkedin-jobs/out/linkedin-report.md`.

::: warning Termos do LinkedIn
Automatizar o LinkedIn pode contrariar os termos de uso da plataforma e levar a restrições na conta. O modo seguro reduz o risco, não o elimina.
:::
