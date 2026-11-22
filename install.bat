@echo off
chcp 65001 >nul
setlocal
cd /d "%~dp0"
set "PATH=%USERPROFILE%\.local\bin;%PATH%"
set PYTHONUTF8=1
title auto-cdlc

rem 0. Language / Idioma (saved in config.txt; asked only the first time)
call :read_language
if /i "%LANG_UI%"=="en" goto language_ready
if /i "%LANG_UI%"=="es" goto language_ready
echo.
echo   1 = English
echo   2 = Espanol
set "OPC="
set /p "OPC=Language / Idioma [1]: "
set "LANG_UI=en"
if "%OPC%"=="2" set "LANG_UI=es"
:language_ready
call :texts_%LANG_UI%

echo ============================================================
echo  %M_TITLE%
echo ============================================================
echo.

rem 1. uv
where uv >nul 2>nul
if not errorlevel 1 goto uv_ok
echo %M_UV1%
powershell -NoProfile -ExecutionPolicy ByPass -Command "irm https://astral.sh/uv/install.ps1 | iex"
if errorlevel 1 goto error
set "PATH=%USERPROFILE%\.local\bin;%PATH%"
goto uv_done
:uv_ok
echo %M_UV2%
:uv_done

rem 2. Python and libraries
echo.
echo %M_PY1%
echo %M_PY2%
uv sync --frozen
if errorlevel 1 goto error

rem 3. cdlc-pack (also picked up from the old "herramientas" folder)
echo.
if exist "tools\cdlc-pack\cdlc-pack.exe" goto pack_present
if exist "herramientas\cdlc-pack\cdlc-pack.exe" goto pack_present
echo %M_PACK2%
powershell -NoProfile -ExecutionPolicy ByPass -Command "$ErrorActionPreference='Stop'; $z=Join-Path $env:TEMP 'cdlc-pack-win-x64.zip'; Invoke-WebRequest -UseBasicParsing 'https://github.com/fesaje/auto-cdlc/releases/latest/download/cdlc-pack-win-x64.zip' -OutFile $z; Expand-Archive -Force $z 'tools\cdlc-pack'; Remove-Item $z"
if not errorlevel 1 goto pack_done
echo %M_PACK3%
echo %M_PACK4%
echo %M_PACK5%
goto pack_done
:pack_present
echo %M_PACK1%
:pack_done

rem 4. Configuration, Wwise and Rocksmith's dlc folder (done by the program itself)
echo.
echo %M_CHK%
uv run --frozen auto_cdlc.py --setup %LANG_UI%
if errorlevel 1 goto error

echo.
echo ============================================================
echo  %M_END1%
echo  %M_END2%
echo ============================================================
pause
exit /b 0

:error
echo.
echo %M_ERR1%
echo https://github.com/fesaje/auto-cdlc/issues
pause
exit /b 1

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
set "M_TITLE=auto-cdlc - instalacion"
set "M_UV1=[1/4] Instalando uv, el gestor de Python..."
set "M_UV2=[1/4] uv ya esta instalado."
set "M_PY1=[2/4] Preparando Python y las librerias. La primera vez tarda unos minutos"
set "M_PY2=      y descarga en torno a 1 GB."
set "M_PACK1=[3/4] cdlc-pack ya esta en tools\cdlc-pack."
set "M_PACK2=[3/4] Descargando cdlc-pack, el compilador de .psarc..."
set "M_PACK3=  No se ha podido descargar. Sin el no se generan los .psarc, solo los proyectos"
set "M_PACK4=  de DLC Builder. Bajalo a mano de https://github.com/fesaje/auto-cdlc/releases"
set "M_PACK5=  y descomprimelo en tools\cdlc-pack"
set "M_CHK=[4/4] Configuracion y comprobaciones"
set "M_END1=Listo. Mete tus canciones en la carpeta input y ejecuta"
set "M_END2=process.bat, o arrastra canciones encima de process.bat"
set "M_ERR1=Algo ha fallado. Haz una captura de esta ventana y abre una incidencia en"
exit /b 0

:texts_en
set "M_TITLE=auto-cdlc - installation"
set "M_UV1=[1/4] Installing uv, the Python manager..."
set "M_UV2=[1/4] uv is already installed."
set "M_PY1=[2/4] Setting up Python and the libraries. The first time takes a few minutes"
set "M_PY2=      and downloads about 1 GB."
set "M_PACK1=[3/4] cdlc-pack is already in tools\cdlc-pack."
set "M_PACK2=[3/4] Downloading cdlc-pack, the .psarc builder..."
set "M_PACK3=  Download failed. Without it no .psarc files are built, only the DLC Builder"
set "M_PACK4=  projects. Download it by hand from https://github.com/fesaje/auto-cdlc/releases"
set "M_PACK5=  and unzip it into tools\cdlc-pack"
set "M_CHK=[4/4] Configuration and checks"
set "M_END1=Done. Put your songs in the input folder and run"
set "M_END2=process.bat, or drag songs onto process.bat"
set "M_ERR1=Something went wrong. Take a screenshot of this window and open an issue at"
exit /b 0
