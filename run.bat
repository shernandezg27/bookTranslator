@echo off
setlocal
cd /d "%~dp0"

:: ── Verificar instalacion ─────────────────────────────────────────────────────
if not exist .venv (
    echo El traductor no esta instalado.
    echo Ejecuta setup.bat primero.
    echo.
    pause
    exit /b 1
)

:: ── Actualizar desde GitHub ───────────────────────────────────────────────────
echo Comprobando actualizaciones...
git pull -q 2>nul

:: ── Activar entorno virtual ───────────────────────────────────────────────────
call .venv\Scripts\activate.bat

:: ── Abrir navegador (con retardo para que Flask arranque primero) ─────────────
start /b cmd /c "timeout /t 2 >nul && start http://localhost:5000"

:: ── Iniciar servidor ──────────────────────────────────────────────────────────
echo.
echo  Traductor EPUB iniciado.
echo  Abre el navegador en: http://localhost:5000
echo.
echo  Para cerrarlo, cierra esta ventana.
echo.
python app.py

pause
