# Publica o repositorio no GitHub.
# Uso: duplo clique com parametro, ou:
#   powershell -ExecutionPolicy Bypass -File publicar-github.ps1
#   powershell -ExecutionPolicy Bypass -File publicar-github.ps1 -RepoUrl https://github.com/USUARIO/vagas-scraper.git
param([string]$RepoUrl = "")
$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $root

if (-not (Test-Path ".git")) {
    git init -b main
    git add -A
    git commit -m "Initial commit: vagas-scraper (captura, score, banco, painel e agendamento)"
}
if (-not $RepoUrl) {
    Write-Host "`nVou abrir o GitHub para voce criar o repositorio (sem README/.gitignore)." -ForegroundColor Cyan
    Start-Process "https://github.com/new"
    $RepoUrl = Read-Host "Cole a URL do repositorio (ex.: https://github.com/USUARIO/vagas-scraper.git)"
}
if (-not $RepoUrl) { Write-Host "URL vazia - nada a fazer." -ForegroundColor Red; exit 1 }

git remote remove origin 2>$null
git remote add origin $RepoUrl
git push -u origin main
Write-Host "`nPublicado. Abra: $RepoUrl" -ForegroundColor Green
