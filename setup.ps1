# Setup completo do vagas-scraper (Windows). Uso: dê dois cliques em setup.bat
$ErrorActionPreference = "Stop"
Set-Location -Path $PSScriptRoot

function Step($m) { Write-Host "`n==> $m" -ForegroundColor Cyan }

# 1) Python
Step "Procurando Python 3"
$py = $null
foreach ($c in @("py -3", "python")) {
    try { $v = & cmd /c "$c --version 2>&1"; if ($v -match "Python 3\.(\d+)" -and [int]$Matches[1] -ge 9) { $py = $c; Write-Host "  $v ($c)"; break } } catch {}
}
if (-not $py) {
    Step "Python não encontrado. Instalando via winget (Python 3.12)"
    winget install -e --id Python.Python.3.12 --accept-package-agreements --accept-source-agreements
    Write-Host "`nPython instalado. FECHE esta janela e execute setup.bat de novo (o PATH só atualiza em um terminal novo)." -ForegroundColor Yellow
    Read-Host "Enter para sair"; exit 0
}

# 2) Google Chrome
Step "Procurando Google Chrome"
$chrome = @("$env:ProgramFiles\Google\Chrome\Application\chrome.exe",
            "${env:ProgramFiles(x86)}\Google\Chrome\Application\chrome.exe",
            "$env:LocalAppData\Google\Chrome\Application\chrome.exe") | Where-Object { Test-Path $_ } | Select-Object -First 1
if ($chrome) { Write-Host "  encontrado: $chrome" }
else {
    Step "Chrome não encontrado. Instalando via winget"
    winget install -e --id Google.Chrome --accept-package-agreements --accept-source-agreements
}

# 3) venv + dependências
Step "Criando ambiente virtual (.venv)"
if (-not (Test-Path ".venv\Scripts\python.exe")) { & cmd /c "$py -m venv .venv" }
$vpy = Join-Path $PSScriptRoot ".venv\Scripts\python.exe"
Step "Instalando dependências"
& $vpy -m pip install --upgrade pip --quiet
& $vpy -m pip install -r requirements.txt

# 4) testes offline
Step "Rodando testes offline"
& $vpy -m unittest discover -s tests
if ($LASTEXITCODE -ne 0) { Write-Host "Testes falharam." -ForegroundColor Red; Read-Host "Enter para sair"; exit 1 }

# 5) primeira execução com janela visível
Step "Setup concluído. Primeira execução (Chrome visível)"
& $vpy main.py --show
Write-Host "`nPronto. Resultados em out\vagas-latest.csv e out\vagas-latest.json" -ForegroundColor Green
Write-Host "Próximas vezes: run.bat (headless) ou run.bat --show"
Read-Host "Enter para sair"
