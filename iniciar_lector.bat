@echo off
title Student Scan Register - Simulador / Lector
chcp 65001 > nul
cd /d "%~dp0"

echo ===============================================================
echo     INICIANDO SCRIPT DEL ESCANER / LECTOR DE CODIGO
echo ===============================================================
echo.

if exist "venv\Scripts\activate.bat" (
    call venv\Scripts\activate.bat
)

python scanner/lector.py

pause
