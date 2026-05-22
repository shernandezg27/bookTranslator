@echo off
setlocal
cd /d "%~dp0"

echo.
echo ============================================
echo    Traductor EPUB - Instalacion
echo ============================================
echo.

:: ── Verificar Python ──────────────────────────────────────────────────────────
python --version >nul 2>&1
if errorlevel 1 (
    echo ERROR: Python no encontrado.
    echo.
    echo Descargalo desde: https://www.python.org/downloads/
    echo Al instalar, marca la casilla "Add Python to PATH".
    echo.
    pause
    exit /b 1
)

:: ── Verificar git ─────────────────────────────────────────────────────────────
git --version >nul 2>&1
if errorlevel 1 (
    echo ERROR: Git no encontrado.
    echo.
    echo Descargalo desde: https://git-scm.com/download/win
    echo.
    pause
    exit /b 1
)

:: ── Eliminar instalacion anterior si existe ───────────────────────────────────
if exist .venv (
    echo Eliminando instalacion anterior...
    rmdir /s /q .venv
)

if exist uploads (
    echo Limpiando archivos temporales...
    rmdir /s /q uploads
)

:: ── Crear entorno virtual ─────────────────────────────────────────────────────
echo Creando entorno virtual...
python -m venv .venv
if errorlevel 1 (
    echo ERROR al crear el entorno virtual.
    pause
    exit /b 1
)

:: ── Instalar dependencias ─────────────────────────────────────────────────────
echo Instalando dependencias (puede tardar un momento)...
call .venv\Scripts\activate.bat
python -m pip install --upgrade pip -q
pip install -r requirements.txt -q
if errorlevel 1 (
    echo ERROR al instalar dependencias.
    pause
    exit /b 1
)

:: ── Crear carpeta de uploads ──────────────────────────────────────────────────
if not exist uploads mkdir uploads

:: ── Crear API_KEY.txt si no existe ───────────────────────────────────────────
if not exist API_KEY.txt (
    echo TU_API_KEY_AQUI> API_KEY.txt
)

echo.
echo ============================================
echo    Instalacion completada correctamente!
echo ============================================
echo.
echo Siguiente paso: ejecuta run.bat para iniciar el traductor.
echo.

:: Abrir API_KEY.txt para que el usuario meta su clave si no la habia puesto
findstr /v "TU_API_KEY_AQUI" API_KEY.txt >nul 2>&1
if errorlevel 1 (
    echo IMPORTANTE: Se ha abierto el archivo API_KEY.txt.
    echo Borra el texto que hay dentro y escribe tu clave de Google AI Studio.
    echo Puedes obtenerla en: https://aistudio.google.com/app/apikey
    echo.
    notepad API_KEY.txt
)

pause
