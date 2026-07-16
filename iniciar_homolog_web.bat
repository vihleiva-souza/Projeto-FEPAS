@echo off
setlocal

cd /d "%~dp0"

if exist ".venv\Scripts\python.exe" (
    set "PYTHON_CMD=.venv\Scripts\python.exe"
) else (
    set "PYTHON_CMD=python"
)

echo Iniciando API de homologacao em http://127.0.0.1:5000
%PYTHON_CMD% app_homolog_web.py

if errorlevel 1 (
    echo.
    echo Falha ao iniciar. Verifique se o Python e as dependencias estao instalados.
    echo Execute: python -m pip install -r requirements.txt
    pause
    exit /b 1
)

endlocal