@echo off
cd /d "%~dp0"
set "PY=python"
where py >nul 2>nul && set "PY=py -3"

if not exist ".venv\Scripts\python.exe" (
  echo Criando .venv com %PY% ...
  %PY% -m venv .venv
  if errorlevel 1 (
    echo Falhou ao criar o .venv. Instale o Python 3 e rode de novo.
    pause
    exit /b 1
  )
)

echo Instalando dependencias ^(playwright^)...
".venv\Scripts\python.exe" -m pip install --upgrade pip --quiet
".venv\Scripts\python.exe" -m pip install -r requirements.txt --quiet
if errorlevel 1 (
  echo Falhou o pip install. Veja a mensagem acima.
  pause
  exit /b 1
)

echo Rodando teste offline...
".venv\Scripts\python.exe" linkedin_jobs.py --self-test
if errorlevel 1 (
  echo Teste offline falhou.
  pause
  exit /b 1
)

echo.
echo Pronto. Agora:
echo   1^) python launch_chrome.py   ^(abre o Chrome de depuracao logado^)
echo   2^) python linkedin_jobs.py   ^(busca e gera o relatorio^)
pause
