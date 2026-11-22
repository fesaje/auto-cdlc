@echo off
chcp 65001 >nul
setlocal
cd /d "%~dp0"
set "PATH=%USERPROFILE%\.local\bin;%PATH%"
set PYTHONUTF8=1
title auto-cdlc
call :read_language
if /i not "%LANG_UI%"=="en" set "LANG_UI=es"
call :texts_%LANG_UI%

where uv >nul 2>nul
if not errorlevel 1 goto run
echo %M_NOUV%
pause
exit /b 1

rem The interface. Updates are checked by process.bat, not here.
:run
uv run --frozen ui.py
if errorlevel 1 pause
exit /b 0

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
exit /b 0

:texts_en
set "M_NOUV=uv not found. Run install.bat first."
exit /b 0
