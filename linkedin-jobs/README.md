# linkedin-jobs — busca de vagas na SUA sessão do Chrome

Ferramenta local que usa o Chrome já logado no LinkedIn (via CDP, porta 9222) para procurar vagas,
abrir as descrições, pontuar por aderência ao seu perfil e gerar um relatório em Markdown.

- **Somente leitura:** não clica em "Candidatura simplificada", não envia mensagem, não altera nada na conta.
- **Cadência humana:** 7 a 22 s aleatórios entre abrir busca, trocar página e abrir cada vaga; rolagem gradual.
- **Sem contornar bloqueio:** se aparecer login/CAPTCHA/checkpoint, o script para e salva um print em `out/debug/`.
- **Match por regras** (não é IA): título 25, stack 35 (Salesforce pesa mais; AWS/Go/Python/Node/Angular somam),
  localização 20, inglês 10, certificações 10. O relatório mostra a conta aberta ("justificativa técnica").

## Uso (Windows)

1. **Instalar uma vez:** dois cliques em `setup.bat` (cria `.venv`, instala Playwright, roda o teste offline).
2. **Abrir o Chrome de depuração com a sua sessão:**
   ```
   .venv\Scripts\python.exe launch_chrome.py
   ```
   Ele copia só o essencial do perfil (Local State + Preferences + cookies) para
   `%TEMP%\linkedin-debug-profile` e abre o Chrome na página de vagas do LinkedIn.
   Se pedir login, entre **uma vez** nessa janela (fica salvo nessa pasta). Seus cookies não saem da máquina.

   Alternativas: `--no-copy` abre um perfil vazio (você entra uma vez, sem copiar cookies);
   `--no-sandbox` só se o Chrome fechar sozinho no seu ambiente; `--refresh` recopia os cookies
   se a sessão tiver expirado.
3. **Rodar a busca:**
   ```
   .venv\Scripts\python.exe linkedin_jobs.py
   ```
   ou dois cliques em `run.bat`.

Ao terminar: `python launch_chrome.py --clean` (apaga a cópia do perfil, que contém cookies).

## Saídas (pasta `out/`)

| Arquivo | O que é |
|---|---|
| `linkedin-report.md` | as 10 melhores vagas em ordem decrescente de % de match, com pontos fortes, gaps, requisitos e salário |
| `linkedin-jobs.json` | todos os campos extraídos (descrição completa inclusive) |
| `run.log` | log da execução (tempos de espera, páginas, falhas) |
| `debug/` | HTML e screenshot quando algo falha (seletor mudou, bloqueio, página vazia) |

## Ajustes úteis

```
python linkedin_jobs.py --tpr r86400          # só últimas 24h (padrão: última semana)
python linkedin_jobs.py --no-intl             # só Brasil (sem o passe internacional)
python linkedin_jobs.py --pages 5 --max-details 40   # varredura maior (demora mais)
python linkedin_jobs.py --keywords '"Salesforce" AND "Remote"' --location "Brazil"
python linkedin_jobs.py --probe "https://www.linkedin.com/jobs/search/?keywords=Salesforce"
```

As buscas padrão são as 3 combinadas (Salesforce sênior, Eng/Backend Go/AWS/Python sênior,
Solutions Architect/Tech Lead Salesforce/AWS) + 1 passe remoto internacional (EUR).

## Diagnóstico

- **"Não consegui falar com o Chrome"** → rode `launch_chrome.py` (ou veja `--status`).
- **"sessão não autenticada"** → entre no LinkedIn na janela de depuração e rode de novo.
- **0 cards** → veja `out/debug/vazio-*.png`; o LinkedIn pode ter mudado o HTML ou a busca ficou sem resultado.
- **Seletores mudaram** → o script tenta vários por campo; se ainda faltar algo, o HTML salvo em `debug/`
  mostra o que usar em `CARD_SEL` / `parse_detail`.

## Limites

- O LinkedIn não permite automação nos termos de uso; use com moderação, em ritmo humano, e pare se
  aparecer verificação. O script não tenta burlar CAPTCHA, login ou bloqueio.
- O layout do LinkedIn muda com frequência; os seletores são os de novembro/2026 e têm fallbacks.
- A cópia de perfil só é necessária porque o Chrome 136+ bloqueia depuração remota no perfil padrão.
