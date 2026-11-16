@echo off
rem Instalador do vagas1000 (a partir do codigo-fonte; para o instalador .exe veja Releases): cria .venv, instala dependencias, roda testes,
rem agenda a atualizacao diaria e cria atalhos na Area de Trabalho.
cd /d "%~dp0"
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0instalar.ps1" %*
if errorlevel 1 (
  echo.
  echo Instalacao terminou com erro. Veja as mensagens acima.
)
pause
