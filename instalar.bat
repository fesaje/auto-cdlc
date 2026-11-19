@echo off
chcp 65001 >nul
setlocal
cd /d "%~dp0"
set "PATH=%USERPROFILE%\.local\bin;%PATH%"
title auto-cdlc

rem 0. Idioma / Language (se guarda en configuracion.txt; se pregunta solo la primera vez)
call :leer_idioma
if /i "%LANG_UI%"=="en" goto idioma_listo
if /i "%LANG_UI%"=="es" goto idioma_listo
echo.
echo   1 = Espanol
echo   2 = English
set "OPC="
set /p "OPC=Idioma / Language [1]: "
set "LANG_UI=es"
if "%OPC%"=="2" set "LANG_UI=en"
powershell -NoProfile -Command "$p='configuracion.txt'; $t=[IO.File]::ReadAllText($p); $nl=[Environment]::NewLine; if ($env:LANG_UI -eq 'en' -and $t -match '(?m)^idioma *= *\r?$' -and (Test-Path 'configuracion.en.txt')) { $t=[IO.File]::ReadAllText('configuracion.en.txt') }; if ($t -match '(?m)^idioma *=') { $t=[regex]::Replace($t,'(?m)^idioma *=[^\r\n]*','idioma = ' + $env:LANG_UI) } else { $t=$t.TrimEnd() + $nl + $nl + 'idioma = ' + $env:LANG_UI + $nl }; [IO.File]::WriteAllText($p,$t,(New-Object Text.UTF8Encoding $false))"
:idioma_listo
call :textos_%LANG_UI%

echo ============================================================
echo  %M_TITULO%
echo ============================================================
echo.

rem 1. uv
where uv >nul 2>nul
if not errorlevel 1 goto uv_ok
echo %M_UV1%
powershell -NoProfile -ExecutionPolicy ByPass -Command "irm https://astral.sh/uv/install.ps1 | iex"
if errorlevel 1 goto error
set "PATH=%USERPROFILE%\.local\bin;%PATH%"
goto uv_hecho
:uv_ok
echo %M_UV2%
:uv_hecho

rem 2. Python y librerias / Python and libraries
echo.
echo %M_PY1%
echo %M_PY2%
uv sync --frozen
if errorlevel 1 goto error

rem 3. cdlc-pack
echo.
if not exist "herramientas\cdlc-pack\cdlc-pack.exe" goto bajar_pack
echo %M_PACK1%
goto pack_hecho
:bajar_pack
echo %M_PACK2%
powershell -NoProfile -ExecutionPolicy ByPass -Command "$ErrorActionPreference='Stop'; $z=Join-Path $env:TEMP 'cdlc-pack-win-x64.zip'; Invoke-WebRequest -UseBasicParsing 'https://github.com/fesaje/auto-cdlc/releases/latest/download/cdlc-pack-win-x64.zip' -OutFile $z; Expand-Archive -Force $z 'herramientas\cdlc-pack'; Remove-Item $z"
if not errorlevel 1 goto pack_hecho
echo %M_PACK3%
echo %M_PACK4%
echo %M_PACK5%
:pack_hecho

rem 4. Wwise y carpeta dlc / Wwise and dlc folder
echo.
echo %M_CHK%
set "WW="
for /d %%D in ("%ProgramFiles(x86)%\Audiokinetic\Wwise*" "%ProgramFiles%\Audiokinetic\Wwise*") do (
    if exist "%%~D\Authoring\x64\Release\bin\WwiseConsole.exe" set "WW=%%~D"
)
if defined WWISEROOT set "WW=%WWISEROOT%"
if not defined WW goto sin_wwise
echo %M_WW1% "%WW%"
goto fin_wwise
:sin_wwise
echo %M_WW2%
echo %M_WW3%
echo %M_WW4%
:fin_wwise

set "DLC=%ProgramFiles(x86)%\Steam\steamapps\common\Rocksmith2014\dlc"
if not exist "%DLC%" goto fin_dlc
powershell -NoProfile -Command "if ((Get-Content -Encoding UTF8 configuracion.txt) -match '^carpeta_psarc\s*=\s*\S') { exit 1 } else { exit 0 }"
if errorlevel 1 goto fin_dlc
echo.
echo %M_DLC1%
echo     "%DLC%"
set "RESP="
set /p "RESP=%M_DLC2%"
if /i "%RESP%"=="s" goto poner_dlc
if /i "%RESP%"=="y" goto poner_dlc
goto fin_dlc
:poner_dlc
powershell -NoProfile -Command "$p='configuracion.txt'; $t=[IO.File]::ReadAllText($p); $t=[regex]::Replace($t,'(?m)^carpeta_psarc *=[^\r\n]*','carpeta_psarc = ' + $env:DLC); [IO.File]::WriteAllText($p,$t,(New-Object Text.UTF8Encoding $false))"
echo %M_DLC3%
:fin_dlc

echo.
echo ============================================================
echo  %M_FIN1%
echo  %M_FIN2%
echo ============================================================
pause
exit /b 0

:error
echo.
echo %M_ERR1%
echo https://github.com/fesaje/auto-cdlc/issues
pause
exit /b 1

:leer_idioma
set "LANG_UI="
for /f "tokens=1,* delims==" %%a in ('findstr /b /r /c:"idioma *=" configuracion.txt 2^>nul') do (
    for /f "tokens=*" %%c in ("%%b") do set "LANG_UI=%%c"
)
if defined LANG_UI set "LANG_UI=%LANG_UI:~0,2%"
exit /b 0

:textos_es
set "M_TITULO=auto-cdlc - instalacion"
set "M_UV1=[1/4] Instalando uv, el gestor de Python..."
set "M_UV2=[1/4] uv ya esta instalado."
set "M_PY1=[2/4] Preparando Python y las librerias. La primera vez tarda unos minutos"
set "M_PY2=      y descarga en torno a 1 GB."
set "M_PACK1=[3/4] cdlc-pack ya esta en herramientas\cdlc-pack."
set "M_PACK2=[3/4] Descargando cdlc-pack, el compilador de .psarc..."
set "M_PACK3=  No se ha podido descargar. Sin el no se generan los .psarc, solo los proyectos"
set "M_PACK4=  de DLC Builder. Bajalo a mano de https://github.com/fesaje/auto-cdlc/releases"
set "M_PACK5=  y descomprimelo en herramientas\cdlc-pack"
set "M_CHK=[4/4] Comprobaciones"
set "M_WW1=  Wwise encontrado:"
set "M_WW2=  AVISO: no encuentro Wwise. Hace falta para convertir el audio al formato de Rocksmith."
set "M_WW3=  Instala Wwise 2019, 2021, 2022 o 2023 desde https://ignition4.customsforge.com/tools/wwise"
set "M_WW4=  o pon la ruta de WwiseConsole.exe en configuracion.txt, clave wwise."
set "M_DLC1=  He encontrado la carpeta dlc de Rocksmith:"
set "M_DLC2=  Dejar ahi los .psarc directamente? s/n: "
set "M_DLC3=  Hecho: los .psarc iran a la carpeta dlc de Rocksmith."
set "M_FIN1=Listo. Mete tus mp3 en la carpeta entrada y ejecuta"
set "M_FIN2=procesar.bat, o arrastra canciones encima de procesar.bat"
set "M_ERR1=Algo ha fallado. Haz una captura de esta ventana y abre una incidencia en"
exit /b 0

:textos_en
set "M_TITULO=auto-cdlc - installation"
set "M_UV1=[1/4] Installing uv, the Python manager..."
set "M_UV2=[1/4] uv is already installed."
set "M_PY1=[2/4] Setting up Python and the libraries. The first time takes a few minutes"
set "M_PY2=      and downloads about 1 GB."
set "M_PACK1=[3/4] cdlc-pack is already in herramientas\cdlc-pack."
set "M_PACK2=[3/4] Downloading cdlc-pack, the .psarc builder..."
set "M_PACK3=  Download failed. Without it no .psarc files are built, only the DLC Builder"
set "M_PACK4=  projects. Download it by hand from https://github.com/fesaje/auto-cdlc/releases"
set "M_PACK5=  and unzip it into herramientas\cdlc-pack"
set "M_CHK=[4/4] Checks"
set "M_WW1=  Wwise found:"
set "M_WW2=  WARNING: Wwise not found. It's needed to convert the audio to Rocksmith's format."
set "M_WW3=  Install Wwise 2019, 2021, 2022 or 2023 from https://ignition4.customsforge.com/tools/wwise"
set "M_WW4=  or put the path to WwiseConsole.exe in configuracion.txt, key wwise."
set "M_DLC1=  Found Rocksmith's dlc folder:"
set "M_DLC2=  Save the .psarc files straight there? y/n: "
set "M_DLC3=  Done: the .psarc files will go to Rocksmith's dlc folder."
set "M_FIN1=Done. Put your mp3s in the entrada folder and run"
set "M_FIN2=procesar.bat, or drag songs onto procesar.bat"
set "M_ERR1=Something went wrong. Take a screenshot of this window and open an issue at"
exit /b 0
