@echo off
chcp 65001 >nul
setlocal
cd /d "%~dp0"
set "PATH=%USERPROFILE%\.local\bin;%PATH%"
title auto-cdlc - instalacion

echo ============================================================
echo  auto-cdlc - instalacion
echo ============================================================
echo.

rem 1. uv: gestor de Python (instala Python y las librerias sin tocar el sistema)
where uv >nul 2>nul
if errorlevel 1 (
    echo [1/4] Instalando uv, el gestor de Python...
    powershell -NoProfile -ExecutionPolicy ByPass -Command "irm https://astral.sh/uv/install.ps1 | iex"
    if errorlevel 1 goto error
    set "PATH=%USERPROFILE%\.local\bin;%PATH%"
) else (
    echo [1/4] uv ya esta instalado.
)

rem 2. Python y librerias
echo.
echo [2/4] Preparando Python y las librerias. La primera vez tarda unos minutos
echo       y descarga en torno a 1 GB.
uv sync --frozen
if errorlevel 1 goto error

rem 3. cdlc-pack (el compilador de .psarc). Viene en el zip de la release; si no esta, se descarga.
echo.
if exist "herramientas\cdlc-pack\cdlc-pack.exe" (
    echo [3/4] cdlc-pack ya esta en herramientas\cdlc-pack.
) else (
    echo [3/4] Descargando cdlc-pack, el compilador de .psarc...
    powershell -NoProfile -ExecutionPolicy ByPass -Command ^
      "$ErrorActionPreference='Stop'; $z=Join-Path $env:TEMP 'cdlc-pack-win-x64.zip';" ^
      "Invoke-WebRequest -UseBasicParsing 'https://github.com/fesaje/auto-cdlc/releases/latest/download/cdlc-pack-win-x64.zip' -OutFile $z;" ^
      "Expand-Archive -Force $z 'herramientas\cdlc-pack'; Remove-Item $z"
    if errorlevel 1 (
        echo   No se ha podido descargar. Sin el no se generan los .psarc, solo los proyectos
        echo   de DLC Builder. Bajalo a mano de https://github.com/fesaje/auto-cdlc/releases
        echo   y descomprimelo en herramientas\cdlc-pack
    )
)

rem 4. Comprobaciones: Wwise y carpeta dlc de Rocksmith
echo.
echo [4/4] Comprobaciones
set "WW="
for /d %%D in ("%ProgramFiles(x86)%\Audiokinetic\Wwise*" "%ProgramFiles%\Audiokinetic\Wwise*") do (
    if exist "%%~D\Authoring\x64\Release\bin\WwiseConsole.exe" set "WW=%%~D"
)
if defined WWISEROOT set "WW=%WWISEROOT%"
if not defined WW goto sin_wwise
echo   Wwise encontrado: "%WW%"
goto fin_wwise
:sin_wwise
echo   AVISO: no encuentro Wwise. Hace falta para convertir el audio al formato de Rocksmith.
echo   Instala Wwise 2019, 2021, 2022 o 2023 desde https://ignition4.customsforge.com/tools/wwise
echo   o pon la ruta de WwiseConsole.exe en configuracion.txt, clave wwise.
:fin_wwise

set "DLC=%ProgramFiles(x86)%\Steam\steamapps\common\Rocksmith2014\dlc"
if not exist "%DLC%" goto fin_dlc
powershell -NoProfile -Command "if ((Get-Content -Encoding UTF8 configuracion.txt) -match '^carpeta_psarc\s*=\s*\S') { exit 1 } else { exit 0 }"
if errorlevel 1 goto fin_dlc
echo.
echo   He encontrado la carpeta dlc de Rocksmith:
echo     "%DLC%"
set /p RESP="  Dejar ahi los .psarc directamente? (s/n): "
if /i not "%RESP%"=="s" goto fin_dlc
powershell -NoProfile -Command "$p='configuracion.txt'; $t=[IO.File]::ReadAllText($p); $t=[regex]::Replace($t,'(?m)^carpeta_psarc *=[^\r\n]*','carpeta_psarc = ' + $env:DLC); [IO.File]::WriteAllText($p,$t,(New-Object Text.UTF8Encoding $false))"
echo   Hecho: los .psarc iran a la carpeta dlc de Rocksmith.
:fin_dlc

echo.
echo ============================================================
echo  Listo. Mete tus mp3 en la carpeta "entrada" y ejecuta
echo  procesar.bat, o arrastra canciones encima de procesar.bat
echo ============================================================
pause
exit /b 0

:error
echo.
echo Algo ha fallado. Haz una captura de esta ventana y abre una incidencia en
echo https://github.com/fesaje/auto-cdlc/issues
pause
exit /b 1
