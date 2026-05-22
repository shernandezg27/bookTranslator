@echo off
setlocal
title Instalador - Traductor EPUB

REM ============================================================
REM   EDITA ESTA LINEA con la URL de tu repositorio de GitHub
REM ============================================================
set "REPO_URL=https://github.com/TU_USUARIO/traductor-epub.git"

set "DEST=%USERPROFILE%\traductor-epub"

echo.
echo ============================================
echo    Instalando Traductor EPUB
echo ============================================
echo.

REM ── Verificar git ───────────────────────────────────────────
git --version >nul 2>&1
if errorlevel 1 (
    echo ERROR: Git no esta instalado.
    echo.
    echo Descargalo desde: https://git-scm.com/download/win
    echo Instalalo y vuelve a ejecutar este archivo.
    echo.
    pause
    exit /b 1
)

REM ── Verificar Python ────────────────────────────────────────
python --version >nul 2>&1
if errorlevel 1 (
    echo ERROR: Python no esta instalado.
    echo.
    echo Descargalo desde: https://www.python.org/downloads/
    echo IMPORTANTE: marca la casilla "Add Python to PATH" al instalar.
    echo Despues vuelve a ejecutar este archivo.
    echo.
    pause
    exit /b 1
)

REM ── Descargar o actualizar el programa ──────────────────────
if exist "%DEST%" (
    echo La carpeta ya existe, actualizando...
    cd /d "%DEST%"
    git pull
) else (
    echo Descargando el programa...
    git clone "%REPO_URL%" "%DEST%"
    if errorlevel 1 (
        echo.
        echo ERROR: No se pudo descargar el repositorio.
        echo Revisa que la URL sea correcta y que tengas conexion.
        pause
        exit /b 1
    )
    cd /d "%DEST%"
)

REM ── Instalar dependencias (setup.bat) ───────────────────────
call setup.bat

REM ── Crear acceso directo en el escritorio ───────────────────
echo Creando acceso directo en el escritorio...
powershell -NoProfile -Command ^
  "$s=(New-Object -ComObject WScript.Shell).CreateShortcut([System.IO.Path]::Combine([Environment]::GetFolderPath('Desktop'),'Traductor EPUB.lnk')); $s.TargetPath='%DEST%\run.bat'; $s.WorkingDirectory='%DEST%'; $s.Save()"

echo.
echo ============================================
echo    Todo listo!
echo ============================================
echo.
echo Tienes un acceso directo "Traductor EPUB" en el escritorio.
echo Hazle doble clic cada vez que quieras traducir un libro.
echo.
pause
