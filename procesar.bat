@echo off
chcp 65001 >nul
setlocal
cd /d "%~dp0"
set "PATH=%USERPROFILE%\.local\bin;%PATH%"
set PYTHONUTF8=1

where uv >nul 2>nul
if errorlevel 1 (
    echo No encuentro uv. Ejecuta primero instalar.bat
    pause
    exit /b 1
)

rem Sin argumentos procesa la carpeta "entrada"; si arrastras archivos o carpetas encima, procesa esos.
uv run --frozen cdlc_bajo.py %*

echo.
pause
