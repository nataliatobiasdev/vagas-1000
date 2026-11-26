# Changelog

Formato [Keep a Changelog](https://keepachangelog.com/pt-BR/1.1.0/); versões seguem [SemVer](https://semver.org/lang/pt-BR/).

## [1.8.0] - 2026-11-26

### Adicionado
- O painel calcula uma triagem de match por função, requisitos, senioridade e competências, com trechos da descrição e alertas. Categorias separam análise, condições, dados insuficientes e incompatibilidades.
- A ordem prioriza a situação da vaga antes da nota. Notas são heurísticas, não probabilidades, e devem ser revisadas com a descrição original.
- Configuração editável em `config/match_profile.json` na pasta de dados; a avaliação do painel não altera vagas, notas anteriores ou histórico do banco.

### Limitações
- A extração usa regras locais e pode errar especialmente em requisitos alternativos, localidade e anúncios incompletos. A classificação precisa de revisão manual; não confirma autorização de trabalho, remuneração ou requisitos.
- As contagens históricas e exportações da captura continuam usando o filtro anterior; o novo match é calculado no painel.

## [1.7.1] - 2026-11-19

### Adicionado
- Feed público da GFT como fonte complementar parcial: traz as publicações recentes e não encerra vagas apenas porque deixaram de aparecer no feed. A listagem completa permanece separada; uma vaga pode aparecer nas duas fontes.

### Corrigido
- Uma resposta HTTP 403 encerra a tentativa sem insistência. Respostas 429 respeitam o `Retry-After`; quando a espera supera um minuto, a fonte é adiada para outra execução.
- Mensagens de erro indicam o bloqueio ou a limitação e informam que as vagas anteriores foram preservadas. A listagem completa da GFT pode continuar indisponível se o portal responder 403.

## [1.7.0] - 2026-11-19

### Adicionado
- 21 fontes de vagas, incluindo GFT, SysMap, Compass, Claranet e empresas com portais Gupy e Ashby.
- Coletor da GFT com paginação conferida e leitura dos detalhes. A atualização acrescenta as novas fontes à configuração existente e guarda uma cópia anterior.

### Corrigido
- Vagas sem descrição e locais remotos ambíguos ficam como **Talvez** para revisão. O termo Sales Cloud não causa mais exclusão indevida como vaga de vendas.
- A pontuação informa que requisitos obrigatórios e preferências ainda precisam de revisão.

## [1.6.0] - 2026-11-18

### Adicionado
- Botão **Atualizar** na aba LinkedIn do painel: relê o banco, regenera o painel e recarrega a página. Resolve o caso em que, depois de importar uma planilha, a aba seguia mostrando as vagas anteriores.
- Marcadores **No CAM** e **Candidatura enviada** nos cards e nas tabelas de vagas, atualizados a partir do banco local do CAM.

### Alterado
- Na aba LinkedIn, o título da vaga é um link para a página completa (como nos cards da aba Vagas) e a última coluna deixa claro que “abrir ↗” vai para o LinkedIn.
- O painel gerado por versões anteriores é refeito na primeira abertura, para ganhar o botão novo.
- Botão de integração, estado de sucesso e mensagens seguem o design system Nevora; a documentação descreve a integração e o histórico de entregas.

## [1.5.1] - 2026-11-17

### Adicionado
- **Adicionar ao CAM** na página da vaga do painel integrado: guarda a vaga e seus dados disponíveis como oportunidade pendente no Career Application Manager. A indicação permanece ao reabrir a vaga, e envios repetidos não criam duplicatas. Abra o CAM atualizado ao menos uma vez para preparar seu banco.

## [1.5.0] - 2026-11-17

> Histórico dia a dia (base), planilha do LinkedIn no formato do app e remoção do botão “Abrir presenciais”.

### Removido
- Botão **Abrir presenciais** da janela e o relatório `out/presenciais.md` (não eram usados). O filtro de modalidade “Presencial” no painel continua.

### Adicionado
- **Planilha da busca Salesforce sênior no formato do app**: a planilha da captura (17/11) entra com aderência Alta/Média/Baixa, senioridade e tipo de contrato na aba LinkedIn. Antes esses três campos não eram reconhecidos na importação.
- **Script de busca sem IA** (`linkedin-jobs/exportar_planilha.py`): gera a planilha do mesmo formato usando o Chrome já logado, sem tokens. A aderência e o critério de senioridade são regras transparentes (`linkedin-jobs/planilha.py`); contra a planilha de 17/11 batem em 78% das vagas. Abrir a descrição de cada vaga é opcional (`--detalhes`) e o padrão é não abrir, como no modo seguro.

### Alterado
- A importação de planilha grava as entradas do dia no histórico (antes a importação não resumia o dia).

### Adicionado (base do histórico dia a dia; a aba Histórico vem na próxima etapa)
- **Histórico por data**: o banco passa a guardar só o que mudou, uma linha por (dia, vaga, tipo, campo) em `job_events` (entrou, saiu, voltou, mudou), e um resumo por data em `day_summary` (abertas no fim do dia, entradas, saídas, mudanças, elegíveis, cobertura de fontes). Várias extrações no mesmo dia viram um dia só.
- **Indicadores modulares** (`config/historico.json`): bloco fixo mais módulos de relevância variável (empresa com grande movimento, elegíveis novas, mudança de veredito, nota, salário, modalidade, vagas reescritas, tecnologia em alta, vagas relâmpago, reaberturas, anomalias e fonte sem leitura).
- Na primeira abertura do banco o app reconstrói os dias já gravados e guarda antes uma cópia (`vagas.db.bak-antes-do-historico`).

### Alterado
- `job_snapshots` deixa de receber linhas novas (as existentes ficam). O histórico de nota e veredito vai em `job_events`.

## [1.4.1] - 2026-11-17

Polimento visual do painel e da documentação (últimos itens da crítica visual).

### Alterado
- **Campos de busca**: o texto-guia (placeholder) agora tem cor explícita, com contraste de 5,2:1; o padrão do navegador quase sumia no campo escuro.
- **Cards de vagas encerradas**: só o título e o selo ficam esmaecidos; o restante do card mantém o contraste (antes o card inteiro perdia opacidade e os metadados caíam abaixo de 4,5:1).
- **Colunas da tabela**: mostram "Ordenar por …" e a seta ↕ ao passar o mouse ou focar, e podem ser acionadas pelo teclado (Tab, Enter ou espaço).
- A imagem da janela na documentação foi refeita com a versão atual (abas Início e Painel de vagas, botão "Refazer com erro").

## [1.4.0] - 2026-11-17

### Adicionado
- **Botão "Refazer com erro"** na tela Início: refaz só as fontes cuja última leitura falhou (por exemplo, a Lever depois de uma queda), em segundos em vez dos ~9 min de uma busca inteira. Nada é fechado nem apagado nas outras fontes. Fica desativado quando não há fonte com erro ou enquanto uma busca roda.

### Corrigido
- **Indicadores do alto da tela Início desatualizados**: os cartões contavam o banco todo (1.201 vagas, 262 elegíveis), incluindo as vagas de fontes que não responderam na última busca, e divergiam da linha de baixo ("1110 vagas · 219 elegíveis"). Agora os cartões mostram o que a última leitura **confirmou**, e as vagas guardadas de fontes sem leitura aparecem à parte ("+91 de 4 fontes sem leitura"). O resumo do painel diz o mesmo.
- **Fontes do painel após uma execução parcial**: o painel lia o resultado de cada fonte só da última execução, então refazer só algumas fontes deixaria as outras como "sem leitura". Agora vale o resultado mais recente de cada fonte.
- Quando **nenhuma fonte responde**, a janela diz "Nenhuma fonte respondeu" e que as vagas guardadas foram mantidas, em vez de "Concluído · 0 vagas".

## [1.3.2] - 2026-11-17

### Corrigido
- **Queda de um serviço de vagas custa menos**: durante a queda da Lever (17/11) a API respondia erro 500/502/504 em ~15 s em vez de estourar o tempo, e o disjuntor só olhava timeout, então cada empresa dela seguia gastando duas tentativas. Agora erro 5xx também conta como "serviço fora do ar": depois de duas falhas seguidas as demais empresas do mesmo serviço são puladas na hora, com a mensagem do erro recebido, e as vagas já guardadas continuam. Erros 4xx (como o 429 do Workday) não contam. Num teste real, as 4 empresas da Lever passaram de dois minutos para ~15 s.

## [1.3.1] - 2026-11-17

Correções dos erros da busca de vagas, painel que se atualiza sozinho e janela só com as abas Início e Painel de vagas.

### Corrigido
- **Vagas da Stone sem descrição**: o limpador de HTML quebrava ("Cannot replace an element with its contents…") quando uma tag desconhecida vinha dentro de outra removida (um `<path>` dentro de `<svg>`); as 9 vagas ficavam sem detalhe a cada busca.
- **Lever fora do ar não trava mais a busca**: cada empresa gastava ~93 s em timeouts (6 min só em 4 empresas). O tempo de leitura caiu para 25 s e um disjuntor por serviço pula as demais empresas dele depois de duas falhas seguidas, com a mensagem "api.lever.co não respondeu… as vagas guardadas continuam" (4 empresas: de ~374 s para ~79 s).
- **Workday (Salesforce) com 429**: a espera entre tentativas agora respeita `Retry-After` e dobra (10, 20, 40 s), e depois de 3 detalhes seguidos com erro o app para de bater na porta e reaproveita o que o banco já tem.
- **Números velhos no painel**: o painel dentro da janela só recarregava ao trocar de aba; agora ele se atualiza sozinho quando a busca (ou uma importação) regrava o arquivo, mantendo a aba e a vaga em que você estava. O arquivo é gravado inteiro e trocado de uma vez, e nunca é lido pela metade.
- O log da execução pelo app (`app-run.log`) saía com os acentos quebrados; agora é UTF-8.

### Alterado
- A janela tem só as abas **Início** e **Painel de vagas**. A aba **LinkedIn** fica dentro do painel, que agora mostra as abas Vagas e LinkedIn também dentro do app. Voltar ao painel mantém a aba interna em que você estava.

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
