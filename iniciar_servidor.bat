@echo off
title Student Scan Register - Servidor FastAPI
chcp 65001 > nul
cd /d "%~dp0"

echo ===============================================================
echo     INICIANDO SERVIDOR - STUDENT SCAN REGISTER
echo ===============================================================
echo.

if not exist "venv\Scripts\python.exe" (
    echo [ERROR] No se encontro el entorno virtual en 'venv'.
    echo Creando entorno virtual e instalando dependencias...
    python -m venv venv
    call venv\Scripts\activate.bat
    python -m pip install -r requirements.txt
) else (
    call venv\Scripts\activate.bat
)

echo.
echo Servidor iniciando en: http://localhost:8000
echo Para abrir el sistema: abre http://localhost:8000/clases en tu navegador.
echo Presiona Ctrl+C para detener el servidor.
echo.

python -m uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload

pause
