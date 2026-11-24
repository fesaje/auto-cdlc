@echo off
chcp 65001 >nul
setlocal
cd /d "%~dp0"
set "PATH=%USERPROFILE%\.local\bin;%PATH%"
set PYTHONUTF8=1
set AUTO_CDLC_BAT=auto-cdlc.bat
title auto-cdlc
call :read_language
if /i not "%LANG_UI%"=="en" set "LANG_UI=es"
call :texts_%LANG_UI%

where uv >nul 2>nul
if not errorlevel 1 goto run
echo %M_NOUV%
pause
exit /b 1

rem The interface. First a quick check for a new version, as process.bat does.
rem Exit code 10 = it has just updated itself: install the new libraries and launch again.
:run
uv run --frozen auto_cdlc.py --update-only
if errorlevel 11 goto ui
if errorlevel 10 goto updated
:ui
uv run --frozen ui.py
if errorlevel 1 pause
exit /b 0

:updated
echo.
echo %M_UPD%
uv sync --frozen
if exist "procesar.bat.nuevo" move /y "procesar.bat.nuevo" "procesar.bat" >nul
if exist "process.bat.nuevo" move /y "process.bat.nuevo" "process.bat" >nul
if not exist "auto-cdlc.bat.nuevo" goto run
rem this file is replaced while running: the move and the relaunch must stay on the same line
move /y "auto-cdlc.bat.nuevo" "auto-cdlc.bat" >nul & "%~f0" %*

rem Language: "language" in config.txt (or "idioma" in the old configuracion.txt)
:read_language
set "LANG_UI="
for /f "tokens=1,* delims==" %%a in ('findstr /b /r /c:"language *=" config.txt 2^>nul') do (
    for /f "tokens=*" %%c in ("%%b") do set "LANG_UI=%%c"
)
if defined LANG_UI goto language_found
for /f "tokens=1,* delims==" %%a in ('findstr /b /r /c:"idioma *=" configuracion.txt 2^>nul') do (
    for /f "tokens=*" %%c in ("%%b") do set "LANG_UI=%%c"
)
:language_found
if defined LANG_UI set "LANG_UI=%LANG_UI:~0,2%"
exit /b 0

:texts_es
set "M_NOUV=No encuentro uv. Ejecuta primero install.bat"
set "M_UPD=auto-cdlc actualizado. Preparando la version nueva..."
exit /b 0

:texts_en
set "M_NOUV=uv not found. Run install.bat first."
set "M_UPD=auto-cdlc updated. Preparing the new version..."
exit /b 0
