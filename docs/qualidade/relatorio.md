# Relatório de testes

Rodada de 16/11/2026, antes do primeiro lançamento (V1.0). O objetivo foi descobrir o que **não funciona** e como resolver. Cada item diz se foi corrigido nesta rodada ou se segue aberto.

<div class="stats">
<div><b>82</b><span>testes offline passando (47 antes, 35 novos)</span></div>
<div><b>53 / 53</b><span>empresas sem navegador coletadas ao vivo, 0 erros</span></div>
<div><b>1.197</b><span>vagas na coleta ao vivo, 256 elegíveis</span></div>
<div><b>6</b><span>problemas corrigidos</span></div>
<div><b>5</b><span>pontos em aberto</span></div>
</div>

## O que foi testado

| Teste | Resultado |
| --- | --- |
| Suíte offline (`unittest`, fixtures de HTML e JSON) | <span class="ok">passou</span>, 47 → 82 testes |
| Coleta ao vivo das 53 empresas por API (sem Chrome) | <span class="ok">passou</span>: 1.197 vagas, 256 elegíveis, 0 erros |
| Stone (Selenium, Chrome real) | <span class="ok">passou</span> depois da correção 3: 9 vagas |
| Janela do app aberta e inspecionada | <span class="ok">passou</span> depois da correção 1 e do novo visual |
| Painel gerado, aberto num navegador e conferido nos temas | <span class="ok">passou</span>; fontes embutidas carregam |
| `vagas1000.exe` empacotado: captura real de 2 empresas, banco, painel, configuração | <span class="ok">passou</span> |
| Self-test do módulo LinkedIn (pontuação, ranking, relatório) | <span class="ok">passou</span> |
| Busca real no LinkedIn | <span class="bad">não testada</span> (veja A3) |
| Workflow CI no GitHub (testes, `.exe`, fumaça, instalador NSIS) | <span class="ok">passou</span> na 3ª tentativa (a 1ª falhou porque o teste não esperava o `.exe` gráfico; a 2ª achou o problema 5) |
| Workflow Docs (build + deploy no Pages) | <span class="ok">passou</span> depois de ativar o Pages: <https://nataliatobiasdev.github.io/vagas-1000/> |
| Workflow Release (tag `v1.0.0`) | <span class="ok">passou</span>: Release publicada com o instalador anexado |
| Instalação do `.exe` numa máquina limpa | <span class="bad">não testada</span> (veja A2) |

## Corrigido nesta rodada

### 1. A barra de status travava durante a atualização

| | |
| --- | --- |
| **Sintoma** | Ao clicar em Atualizar base, o primeiro resultado aparecia e a barra parava de se mover |
| **Causa** | `_flush_results` usava a variável `errors`, que nunca era definida: `NameError` a cada ciclo de 500 ms. Como o agendamento do próximo ciclo ficava depois da chamada, o laço de atualização morria |
| **Correção** | `errors = st.get("errors") or []` em `app.py`; teste de regressão `AppPollRegressionTests` |

### 2. Sem Chrome, a execução inteira abortava

| | |
| --- | --- |
| **Sintoma** | “Não foi possível abrir o Chrome” e nenhuma empresa coletada, embora 53 de 54 não usem Chrome |
| **Causa** | `main.py` abria o Chrome antes de qualquer coleta e saía se falhasse |
| **Correção** | Chrome **sob demanda** em `runner.py`: só abre quando uma empresa precisa (a Stone). Se faltar, a Stone aparece como erro e as outras 53 seguem. 3 testes novos (`LazyChromeTests`) |

### 3. Chrome falhava com “cannot create temp dir”

| | |
| --- | --- |
| **Sintoma** | `SessionNotCreatedException: cannot create temp dir for user data dir` em `logs/scraper.log` (17:25, 17:27, 19:43) |
| **Causa** | Em terminais com `%TEMP%` bloqueado, o chromedriver e o Chrome não conseguem criar pastas temporárias |
| **Correção** | `scraper/driver.py` passa a dar ao Chrome um perfil próprio (`.chrome-profile`) e um `TEMP`/`TMP` próprio (`.chrome-tmp`) dentro da pasta de dados. A Stone voltou a coletar 9 vagas no mesmo terminal em que falhava |

### 4. Não havia instalador

| | |
| --- | --- |
| **Sintoma** | A instalação exigia Python, `.venv` e `pip` na máquina |
| **Correção** | Empacotamento PyInstaller + instalador NSIS por usuário, gerado no CI e publicado a cada tag. Os dados passam a ficar em `%APPDATA%\vagas1000` (`scraper/paths.py`) em vez de dentro da pasta do código. Veja [Instalador Windows](/qualidade/instalador) |

### 5. A configuração só aparecia depois da primeira captura

| | |
| --- | --- |
| **Sintoma** | No app instalado, `%APPDATA%\vagas1000\config` não existia até a primeira atualização; quem queria editar o perfil antes não achava o arquivo. Foi o **CI** que pegou: o teste de fumaça do `.exe` exigia o arquivo e falhou |
| **Correção** | `paths.ensure_config()` roda ao abrir o app e o `main`; teste `PathsTests` (copia uma vez e nunca sobrescreve suas edições) |

### 6. Resíduos de versões anteriores

| | |
| --- | --- |
| **Sintoma** | Um dicionário `COMPANY` no `app.py` com 41 das 54 empresas, sem uso; `main.py` mandando “rodar setup.bat” e dizendo “3 empresas” |
| **Correção** | Removidos. Textos atualizados |

## Segunda rodada: o painel virou banco de vagas (V1.1)

Ao desenhar o banco que guarda cada vaga por inteiro, mais problemas apareceram. Todos corrigidos.

| # | Problema | Efeito | Correção |
| --- | --- | --- | --- |
| 7 | O painel cortava a descrição em **3.000 caracteres** e só guardava texto puro | A vaga em si só dava para ver entrando no link; formatação, listas e requisitos se perdiam | Descrição completa em **HTML limpo** (sem script, estilo nem imagem) e texto puro, página completa da vaga |
| 8 | A captura **descartava** quase tudo que a API envia: datas, salário, requisição, escritórios, etapas do processo, prazo, payload | Impossível montar um banco com o que a fonte informava | Cada fonte guarda os campos padronizados **e** o payload bruto (veja [Fontes](/arquitetura/fontes)) |
| 9 | A atualização **sobrescrevia** a vaga: se a empresa editava o texto, o anterior sumia; se o detalhe não fosse reaberto, a descrição ficava vazia | Perda de informação a cada execução | Histórico de **versões** (`job_versions`) e regra de que captura parcial nunca apaga o que já estava guardado |
| 10 | O Gupy só abria o detalhe das **40 primeiras vagas** de cada empresa e o Workday das 30 | Vagas além do limite ficavam sem descrição | Detalhes em cache no banco: a 1ª execução lê tudo (até 150 por empresa) e as seguintes só o que é novo ou tem mais de 7 dias |
| 11 | `ORDER BY` em tabelas grandes falhava com “unable to open database file” em terminais com `%TEMP%` bloqueado | A exportação e consultas pesadas quebravam | `PRAGMA temp_store=MEMORY` na abertura do banco |
| 12 | Painéis “Fontes”, “Vagas por empresa” e “Tecnologias” enormes | Rolar metros de página para chegar à lista | Painéis **recolhíveis**: resumo compacto fechado, lista rolável com busca aberto |
| 13 | “Abrir painel” abria o navegador | O painel parecia outro programa | Janela do painel dentro do app (WebView2), com fallback para o navegador |

Em aberto desta rodada: a janela do painel foi validada pelo autoteste do CI, não numa máquina limpa; e o **tamanho do banco** cresce (o registro completo pesa algumas dezenas de MB para mais de mil vagas).

## Em aberto

### A1. Workday limita a velocidade (429)

Na coleta ao vivo, a Salesforce recebeu **15 respostas 429** e **3 descrições falharam** depois das tentativas. A vaga entra, mas sem descrição, então a nota fica menor que a real. Leva ~85 s, a maior parte do tempo da coleta.

**Como resolver:** aumentar as pausas em `collect_workday` (hoje 3 a 6 s) ou reduzir `max_details`; ou rodar a Salesforce sozinha em horário calmo (`--only salesforce`). Um recuo exponencial com limite de tentativas e uma segunda passada só nas descrições que falharam resolveriam sem custo de tempo.

### A2. Instalador publicado, ainda sem teste de instalação em outra máquina

O **CI está verde**, o **site está no Pages** e a **Release v1.0.0** foi publicada pelo `release.yml` com o `vagas1000-Setup-1.0.0.exe` (23,4 MB) anexado. A primeira tentativa do Docs falhou em `configure-pages` só porque o Pages ainda não estava ativo; depois de *Settings → Pages → Source: GitHub Actions*, um re-run resolveu.

O que ainda não foi feito é **instalar o `.exe` do instalador numa máquina limpa** e abrir o app (o CI testa o executável empacotado, não o assistente de instalação).

**Como resolver:** baixe em [Releases](https://github.com/nataliatobiasdev/vagas-1000/releases), instale e confira atalhos, abertura e desinstalação (que deve manter `%APPDATA%\vagas1000`).

### A3. LinkedIn só testado offline

O self-test passa, mas a busca real exige a sua sessão logada num Chrome de depuração e traz risco de bloqueio da conta. O seletor de cartões foi atualizado (`componentkey`), o que mostra que o LinkedIn muda o HTML com frequência. O módulo **não vai no instalador**.

**Como resolver:** testar uma vez, à mão, com o modo seguro. Se quiser no instalador, o módulo usa Playwright e teria de entrar no pacote do PyInstaller, com mais um conjunto de dependências a validar; recomendo manter fora.

### A4. Perfil de exemplo é pessoal

`config/profile.json` traz Salesforce (6 anos), AWS, Go etc. Quem instalar sem editar recebe notas desse perfil.

**Como resolver:** editar `profile.json` (em `%APPDATA%\vagas1000\config`) e rodar `--reavaliar`. Em versão futura, um assistente de primeira execução.

### A5. Sem assinatura de código e sem teste automatizado da janela

O SmartScreen avisa “Editor desconhecido” (comum a instaladores sem certificado). A interface foi conferida à mão (abertura, captura de tela, regressão do `NameError`), sem teste de cliques.

**Como resolver:** certificado de assinatura (pago) ou ignorar o aviso; para a janela, testes de widget com `tkinter` em CI com display virtual.

## Observações

- O Python do ambiente de desenvolvimento era a versão **3.15.2**, bem à frente da 3.12 do CI. Funcionou, mas fixe a **3.12** (`.python-version`) para evitar dependências sem pacote pronto.
- Os arquivos antigos `setup.bat`/`setup.ps1` e `publicar-github.ps1` duplicavam o `instalar.bat` e ficaram obsoletos; foram removidos (continuam no histórico do git).
- Afya e Dock vieram com 0 vagas: sem vaga técnica hoje, não é falha.
