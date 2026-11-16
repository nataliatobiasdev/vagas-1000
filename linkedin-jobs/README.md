# linkedin-jobs — busca de vagas na SUA sessão do Chrome (modo seguro)

Usa o Chrome já logado no LinkedIn (via CDP, porta 9222) para listar as vagas **mais recentes**,
pontuar por aderência ao seu perfil e gerar um relatório. **Não abre a página de cada vaga, não se
candidata, não envia mensagem e não mexe na conta.**

## Modo seguro (padrão)

| Regra | Valor |
|---|---|
| Páginas por busca | **2** (25 vagas/página) |
| Teto por execução | **50 vagas** |
| Janela | **últimas 24h** (`f_TPR=r86400`, `sortBy=DD`) |
| Detalhes abertos | **0** (opcional: `--details N`, máx. 5) |
| Pausa entre páginas | **25–55 s** aleatórios |
| Pausa entre buscas | **60–120 s** aleatórios |
| Frequência | **1 execução por dia** (`--force` para repetir) |
| Bloqueio | para na hora em CAPTCHA/checkpoint/HTTP 999 e salva print em `out/debug/` |

O relatório é ordenado por **mais recente primeiro** (ordem do LinkedIn); com `--sort match` ele
volta a ordenar por % de match. O campo "Publicada" mostra o texto do card ("há 2 horas", "há 1 dia").

## Uso (Windows)

1. **Instalar uma vez:** dois cliques em `setup.bat`.
2. **Abrir o Chrome de depuração** (cópia do perfil, já logada):
   ```
   .venv\Scripts\python.exe launch_chrome.py
   ```
   Se pedir login, entre **uma vez** nessa janela. Os cookies ficam só na máquina.
   Ao terminar: `launch_chrome.py --clean`.
3. **Rodar:**
   ```
   .venv\Scripts\python.exe linkedin_jobs.py
   ```
   Ou, no app principal, o botão **Buscar no LinkedIn** (ele abre o Chrome de depuração se necessário,
   respeita o limite diário e mostra o progresso na barra de status).

## Saídas (`out/`)

| Arquivo | O que é |
|---|---|
| `linkedin-report.md` | vagas ordenadas (recentes por padrão), com match, pontos fortes/gaps e link |
| `linkedin-jobs.json` | todos os campos (inclusive `posted`) |
| `status.json` | progresso ao vivo (lido pelo app: página, busca, vagas, bloqueio) |
| `last-run.json` | data da última execução (controle de 1x/dia) |
| `run.log` | log com as pausas e falhas |
| `debug/` | HTML/screenshot quando algo falha |

## Ajustes

```
python linkedin_jobs.py                       # modo seguro padrão
python linkedin_jobs.py --sort match          # ordenar por match em vez de recente
python linkedin_jobs.py --details 2           # abrir 2 detalhes (mais lento/arriscado)
python linkedin_jobs.py --pages 1             # só a primeira página
python linkedin_jobs.py --no-intl             # sem o passe internacional
python linkedin_jobs.py --force               # ignorar o limite de 1x/dia
python linkedin_jobs.py --probe "https://www.linkedin.com/jobs/search/?keywords=Salesforce"
```

Buscas padrão: Salesforce sênior (BR), Eng/Backend Go/AWS/Python sênior (BR), Solutions
Architect/Tech Lead (BR) e um passe remoto internacional.

## Diagnóstico

- **"Não consegui falar com o Chrome"** → `launch_chrome.py` (ou `--status`).
- **"sessão não autenticada"** → entre na janela de depuração e rode de novo.
- **0 cards** → veja `out/debug/vazio-*.png` (HTML mudou ou busca sem resultado).
- **CAPTCHA** → o script para; faça a verificação manualmente e só rode no dia seguinte.

## Limites (leia)

- O LinkedIn **não permite automação** nos termos de uso. Mesmo em modo seguro, existe risco de
  restrição da conta; o modo seguro reduz, não elimina.
- O layout muda com frequência; os seletores são de novembro/2026 e têm fallbacks.
- A cópia de perfil só existe porque o Chrome 136+ bloqueia depuração remota no perfil padrão.
