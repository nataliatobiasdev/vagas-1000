param(
  [switch]$RemoverVenv,
  [string]$NomeTarefa = "Vagas Scraper - atualizacao diaria"
)
$ErrorActionPreference = "Continue"
$root = Split-Path -Parent $MyInvocation.MyCommand.Path
$desktop = [Environment]::GetFolderPath("Desktop")

Write-Host "`n==> Removendo tarefa agendada" -ForegroundColor Cyan
try {
    Unregister-ScheduledTask -TaskName $NomeTarefa -Confirm:$false -ErrorAction Stop
    Write-Host "    tarefa removida"
} catch {
    & schtasks /Delete /F /TN $NomeTarefa 2>$null | Out-Null
    if ($LASTEXITCODE -eq 0) { Write-Host "    tarefa removida (schtasks)" }
    else { Write-Host "    tarefa nao encontrada (ok)" }
}

Write-Host "`n==> Removendo atalhos" -ForegroundColor Cyan
foreach ($n in @("Vagas - abrir app.lnk", "Vagas - atualizar agora.lnk", "Vagas - abrir painel.lnk")) {
    $p = Join-Path $desktop $n
    if (Test-Path $p) { Remove-Item $p -Force; Write-Host "    removido: $n" }
}

if ($RemoverVenv) {
    Write-Host "`n==> Removendo .venv" -ForegroundColor Cyan
    if (Test-Path (Join-Path $root ".venv")) { Remove-Item (Join-Path $root ".venv") -Recurse -Force }
    Write-Host "    .venv removido"
} else {
    Write-Host "`nOs dados ficaram intactos: data\vagas.db, out\, logs\." -ForegroundColor Green
    Write-Host "Para remover tambem o ambiente virtual: desinstalar.bat -RemoverVenv"
}
