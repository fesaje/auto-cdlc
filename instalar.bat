@echo off
chcp 65001 >nul
setlocal
cd /d "%~dp0"
set "PATH=%USERPROFILE%\.local\bin;%PATH%"

where uv >nul 2>nul
if errorlevel 1 (
    echo Instalando uv, el gestor de Python...
    powershell -NoProfile -ExecutionPolicy ByPass -Command "irm https://astral.sh/uv/install.ps1 | iex"
    if errorlevel 1 goto error
)

echo.
echo Preparando el entorno. La primera vez tarda unos minutos y descarga en torno a 1 GB.
uv sync --frozen
if errorlevel 1 goto error

echo.
echo ============================================================
echo  Listo. Mete tus mp3 en la carpeta "entrada" y ejecuta
echo  procesar.bat, o arrastra canciones encima de procesar.bat
echo ============================================================
pause
exit /b 0

:error
echo.
echo Algo ha fallado. Haz una captura de esta ventana.
pause
exit /b 1
