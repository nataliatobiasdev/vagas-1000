param(
  [string]$Hora = "",
  [switch]$SemTarefa,
  [switch]$SemAtalhos,
  [switch]$SemPrimeiraExecucao,
  [switch]$SemDeps,
  [string]$NomeTarefa = "Vagas Scraper - atualizacao diaria"
)
$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $root

function Passo($m) { Write-Host "`n==> $m" -ForegroundColor Cyan }
function Ok($m) { Write-Host "    OK: $m" -ForegroundColor Green }
function Aviso($m) { Write-Host "    AVISO: $m" -ForegroundColor Yellow }

Passo "1/6 Python"
$py = $null
foreach ($c in @("py -3", "python")) {
    try {
        $v = & cmd /c "$c --version 2>&1"
        if ($v -match "Python 3\.(\d+)" -and [int]$Matches[1] -ge 9) { $py = $c; Ok "$v ($c)"; break }
    } catch { }
}
if (-not $py) {
    Write-Host "Python 3.9+ nao encontrado. Instale em https://python.org e rode de novo." -ForegroundColor Red
    exit 1
}

Passo "2/6 Google Chrome"
$chrome = @("$env:ProgramFiles\Google\Chrome\Application\chrome.exe",
            "${env:ProgramFiles(x86)}\Google\Chrome\Application\chrome.exe",
            "$env:LocalAppData\Google\Chrome\Application\chrome.exe") | Where-Object { Test-Path $_ } | Select-Object -First 1
if ($chrome) { Ok $chrome } else { Aviso "Chrome nao encontrado - o Selenium Manager vai falhar na captura" }

Passo "3/6 Ambiente virtual (.venv)"
$vpy = Join-Path $root ".venv\Scripts\python.exe"
$pyw = Join-Path $root ".venv\Scripts\pythonw.exe"
if (-not (Test-Path $vpy)) {
    & cmd /c "$py -m venv .venv"
    if ($LASTEXITCODE -ne 0) { Write-Host "Falha ao criar o .venv." -ForegroundColor Red; exit 1 }
}
Ok $vpy

Passo "4/6 Dependencias"
if (-not $SemDeps) {
    & $vpy -m pip install --upgrade pip --quiet
    & $vpy -m pip install -r requirements.txt --quiet
    if ($LASTEXITCODE -ne 0) { Write-Host "Falha no pip install." -ForegroundColor Red; exit 1 }
    Ok "selenium, beautifulsoup4, lxml"
} else { Aviso "pip ignorado (-SemDeps)" }

Passo "5/6 Testes offline"
& $vpy -m unittest discover -s tests
if ($LASTEXITCODE -ne 0) {
    Write-Host "Testes falharam - instalacao abortada." -ForegroundColor Red
    exit 1
}
Ok "testes passaram"

Passo "6/6 Agendamento e atalhos"
if (-not $SemTarefa) {
    if (-not $Hora) {
        $Hora = Read-Host "    Horario da atualizacao diaria (HH:mm) [Enter = 08:00]"
        if (-not $Hora) { $Hora = "08:00" }
    }
    if ($Hora -notmatch "^\d{1,2}:\d{2}$") { Write-Host "Horario invalido: $Hora" -ForegroundColor Red; exit 1 }
    try {
        $action = New-ScheduledTaskAction -Execute $pyw -Argument "main.py --no-open" -WorkingDirectory $root
        $trigger = New-ScheduledTaskTrigger -Daily -At $Hora
        $settings = New-ScheduledTaskSettingsSet -StartWhenAvailable -AllowStartIfOnBatteries `
                    -DontStopIfGoingOnBatteries -ExecutionTimeLimit (New-TimeSpan -Hours 1)
        Register-ScheduledTask -TaskName $NomeTarefa -Action $action -Trigger $trigger -Settings $settings `
                    -Description "Atualiza a base de vagas (CI&T, Stone, Zup, bancos, setores, Salesforce...)" -Force | Out-Null
        Ok "tarefa '$NomeTarefa' agendada para $Hora (diario)"
    } catch {
        Aviso "Nao consegui registrar a tarefa ($($_.Exception.Message))"
        $tr = "`"$pyw`" `"$root\main.py`" --no-open"
        & schtasks /Create /F /SC DAILY /ST $Hora /TN $NomeTarefa /TR $tr | Out-Null
        if ($LASTEXITCODE -eq 0) { Ok "tarefa agendada via schtasks para $Hora" }
        else { Aviso "agende manualmente: python main.py --no-open" }
    }
} else { Aviso "agendamento ignorado (-SemTarefa)" }

if (-not $SemAtalhos) {
    $desktop = [Environment]::GetFolderPath("Desktop")
    $ws = New-Object -ComObject WScript.Shell
    $l1 = $ws.CreateShortcut((Join-Path $desktop "Vagas - atualizar agora.lnk"))
    $l1.TargetPath = Join-Path $root "run.bat"
    $l1.WorkingDirectory = $root
    $l1.Description = "Captura as vagas e abre o painel"
    $l1.Save()
    $l2 = $ws.CreateShortcut((Join-Path $desktop "Vagas - abrir painel.lnk"))
    $l2.TargetPath = Join-Path $root "out\dashboard.html"
    $l2.Description = "Abre o painel offline"
    $l2.Save()
    Ok "atalhos na Area de Trabalho"
} else { Aviso "atalhos ignorados (-SemAtalhos)" }

if (-not $SemPrimeiraExecucao) {
    $resp = Read-Host "    Rodar a primeira captura agora? (s/N)"
    if ($resp -match "^[sS]") {
        & $vpy main.py --no-open
    }
}

Write-Host "`nPronto." -ForegroundColor Green
Write-Host "  Atualizar agora : run.bat  (ou o atalho 'Vagas - atualizar agora')"
Write-Host "  Painel          : out\dashboard.html"
Write-Host "  Log             : logs\scraper.log"
Write-Host "  Reagendar       : instalar.bat   (escolha outro horario)"
Write-Host "  Desinstalar     : desinstalar.bat"
