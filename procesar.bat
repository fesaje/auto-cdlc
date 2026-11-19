@echo off
chcp 65001 >nul
setlocal
cd /d "%~dp0"
set "PATH=%USERPROFILE%\.local\bin;%PATH%"
set PYTHONUTF8=1
set AUTO_CDLC_BAT=1
title auto-cdlc
call :leer_idioma
if /i not "%LANG_UI%"=="en" set "LANG_UI=es"
call :textos_%LANG_UI%

where uv >nul 2>nul
if not errorlevel 1 goto lanzar
echo %M_NOUV%
pause
exit /b 1

rem Sin argumentos procesa la carpeta "entrada"; si arrastras archivos o carpetas encima, procesa esos.
rem Codigo de salida 10 = se acaba de actualizar: se preparan las librerias nuevas y se vuelve a lanzar.
:lanzar
uv run --frozen cdlc_bajo.py %*
if errorlevel 11 goto fin
if errorlevel 10 goto actualizado
:fin
echo.
pause
exit /b 0

:actualizado
echo.
echo %M_ACT%
uv sync --frozen
if exist "procesar.bat.nuevo" (move /y "procesar.bat.nuevo" "procesar.bat" >nul & "%~f0" %*)
goto lanzar

:leer_idioma
set "LANG_UI="
for /f "tokens=1,* delims==" %%a in ('findstr /b /r /c:"idioma *=" configuracion.txt 2^>nul') do (
    for /f "tokens=*" %%c in ("%%b") do set "LANG_UI=%%c"
)
if defined LANG_UI set "LANG_UI=%LANG_UI:~0,2%"
exit /b 0

:textos_es
set "M_NOUV=No encuentro uv. Ejecuta primero instalar.bat"
set "M_ACT=auto-cdlc actualizado. Preparando la version nueva..."
exit /b 0

:textos_en
set "M_NOUV=uv not found. Run instalar.bat first."
set "M_ACT=auto-cdlc updated. Preparing the new version..."
exit /b 0
