# Contratos, rede e dados

## Comunicação entre processos

| Origem → destino | Contrato implementado |
| --- | --- |
| Tk → coleta | `subprocess.Popen` com `--scrape --no-open` e, quando aplicável, `--only <company_id>`. Saída redirecionada a `logs/app-run.log`. |
| Coleta → Tk | Arquivo `out/status.json`, gravado por substituição de arquivo temporário; inclui estado, fonte atual, resultados e erros. Não é uma chamada RPC. |
| Tk → painel | Processo com `--janela-painel --embutir <HWND> --rota <rota>`; janela filha Win32. `out/panel-cmd.json` transporta `n` e `route`. |
| JavaScript do painel → Python | `window.pywebview.api`: `cam_statuses()`, `cam_status(key)`, `add_to_cam(key, job, record)`, `refresh()` e `get_raw(key)`. Fora do WebView, a ponte não está disponível. |
| Painel → CAM | SQLite local `%APPDATA%/CAM/cam.db`, tabela `vagas1000_inbox`; `INSERT OR IGNORE` e consultas de estado. Não existe IPC Electron ou HTTP entre os aplicativos. |

Fontes: [app.py](https://github.com/nataliatobiasdev/vagas-1000/blob/v1.7.1/app.py), [runner](https://github.com/nataliatobiasdev/vagas-1000/blob/v1.7.1/scraper/runner.py) e [panel_window.py](https://github.com/nataliatobiasdev/vagas-1000/blob/v1.7.1/scraper/panel_window.py).

## Rede

O processo de coleta usa `urllib` por HTTPS. Lever usa `GET https://api.lever.co/v0/postings/{token}?mode=json`; Ashby usa `GET https://api.ashbyhq.com/posting-api/job-board/{board}?includeCompensation=true`; Greenhouse usa `GET /v1/boards/{token}/jobs` na API configurada; Workday usa `POST /wday/cxs/{tenant}/{site}/jobs` e GET de detalhes. Gupy e GFT são lidos por HTML; GFT tem também RSS parcial. A Stone usa Selenium e ChromeDriver com porta local atribuída pelo WebDriver, não uma porta fixa declarada no projeto. [Coletores](https://github.com/nataliatobiasdev/vagas-1000/blob/v1.7.1/scraper/collectors.py) · [Driver](https://github.com/nataliatobiasdev/vagas-1000/blob/v1.7.1/scraper/driver.py).

No fluxo opcional LinkedIn do código-fonte, `http://127.0.0.1:9222/json/version` verifica o Chrome de depuração; `LINKEDIN_CDP` pode alterar o endereço no coletor. A porta 9222 não é requisito da coleta padrão do instalador. [Cliente](https://github.com/nataliatobiasdev/vagas-1000/blob/v1.7.1/linkedin-jobs/linkedin_jobs.py) · [Inicialização do Chrome](https://github.com/nataliatobiasdev/vagas-1000/blob/v1.7.1/linkedin-jobs/launch_chrome.py).

## Dados e cobertura

Em execução empacotada, `%APPDATA%/vagas1000` contém `config/`, `data/vagas.db`, `out/`, `logs/`, `.webview` e os diretórios de trabalho do Chrome. `VAGAS1000_HOME` substitui a raiz; no código-fonte o padrão é a raiz do projeto. `vagas.db` mantém empresas, execuções, vagas, versões e histórico. O painel `out/dashboard.html` é gerado a partir do banco. [Caminhos](https://github.com/nataliatobiasdev/vagas-1000/blob/v1.7.1/scraper/paths.py) · [Banco](https://github.com/nataliatobiasdev/vagas-1000/blob/v1.7.1/scraper/db.py).

Fontes com erro não encerram vagas anteriormente vistas. O feed GFT é identificado como parcial; a ausência nele não encerra vagas e pode haver duplicidade com a listagem completa. O resultado de uma fonte acessível não garante que todos os requisitos de uma vaga sejam compatíveis com o perfil.
