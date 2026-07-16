@echo off
setlocal

cd /d "%~dp0"

rem Ignora configuracoes globais do pip (ex.: install.user=true em pip.ini)
set "PIP_CONFIG_FILE=NUL"
set "PIP_USER="

if not exist ".venv\Scripts\python.exe" (
    echo Criando ambiente virtual local .venv...
    python -m venv .venv
    if errorlevel 1 (
        echo.
        echo Falha ao criar o ambiente virtual.
        echo Verifique se o Python esta instalado e no PATH.
        pause
        exit /b 1
    )
)

echo Instalando dependencias...
.venv\Scripts\python.exe -m pip install --no-user --upgrade pip
if errorlevel 1 (
    echo.
    echo Falha ao atualizar o pip.
    pause
    exit /b 1
)
.venv\Scripts\python.exe -m pip install --no-user -r requirements.txt
if errorlevel 1 (
    echo.
    echo Falha ao instalar as dependencias do requirements.txt.
    pause
    exit /b 1
)

echo.
echo Ambiente pronto.
echo Para iniciar a aplicacao: iniciar_homolog_web.bat

endlocal