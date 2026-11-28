#!/usr/bin/env bash
# auto-cdlc installer for Linux and macOS (macOS: beta, Apple Silicon only). Same steps as install.bat:
# uv (Python manager), Python and the libraries, cdlc-pack, configuration (Wwise, Rocksmith's dlc folder).
cd "$(dirname "$0")" || exit 1
export PATH="$HOME/.local/bin:$HOME/.cargo/bin:$PATH" PYTHONUTF8=1
export AUTO_CDLC_INSTALL_LOG="$PWD/install_log.txt"

# 0. Language / Idioma (saved in config.txt; asked only the first time)
idioma=$(sed -n 's/^language *= *\(..\).*/\1/p' config.txt 2>/dev/null | head -1)
if [ "$idioma" != "en" ] && [ "$idioma" != "es" ]; then
    echo "  1 = English"
    echo "  2 = Español"
    read -r -p "Language / Idioma [1]: " opc
    idioma=en; [ "$opc" = "2" ] && idioma=es
fi
t() { if [ "$idioma" = "es" ]; then echo "$1"; else echo "$2"; fi; }

echo "============================================================"
t " auto-cdlc - instalación" " auto-cdlc - installation"
echo "============================================================"
echo "auto-cdlc install $(date '+%Y-%m-%d %H:%M')" > "$AUTO_CDLC_INSTALL_LOG"
uname -a >> "$AUTO_CDLC_INSTALL_LOG"

informe() {   # $1 = ok | error
    if command -v uv >/dev/null 2>&1; then
        uv run --no-project --quiet informe.py install "$1" "$AUTO_CDLC_INSTALL_LOG"
    fi
}
fallo() {
    echo
    t "Algo ha fallado. Abre una incidencia en https://github.com/fesaje/auto-cdlc/issues" \
      "Something went wrong. Open an issue at https://github.com/fesaje/auto-cdlc/issues"
    informe error
    exit 1
}

# What runs where: the libraries (PyTorch) exist for Linux x86_64 and for Macs with Apple Silicon and macOS 14+
sistema=$(uname -s); maquina=$(uname -m)
if [ "$sistema" = "Darwin" ]; then
    if [ "$maquina" != "arm64" ]; then
        t "auto-cdlc en Mac necesita un Mac con Apple Silicon (M1 o posterior)." \
          "auto-cdlc on Mac needs an Apple Silicon Mac (M1 or later)."
        echo "[0] mac $maquina: not supported" >> "$AUTO_CDLC_INSTALL_LOG"; fallo
    fi
    t "Aviso: la versión de Mac está en beta. Si algo falla, el informe de instalación ayuda a arreglarlo." \
      "Note: the Mac version is in beta. If something fails, the installation report helps fix it."
elif [ "$maquina" != "x86_64" ]; then
    t "auto-cdlc en Linux necesita un PC de 64 bits (x86_64)." "auto-cdlc on Linux needs a 64-bit PC (x86_64)."
    echo "[0] linux $maquina: not supported" >> "$AUTO_CDLC_INSTALL_LOG"; fallo
fi

# 1. uv
echo
if command -v uv >/dev/null 2>&1; then
    t "[1/4] uv ya está instalado." "[1/4] uv is already installed."
    echo "[1/4] uv: already there" >> "$AUTO_CDLC_INSTALL_LOG"
else
    t "[1/4] Instalando uv, el gestor de Python..." "[1/4] Installing uv, the Python manager..."
    if command -v curl >/dev/null 2>&1; then
        curl -LsSf https://astral.sh/uv/install.sh | sh
    else
        wget -qO- https://astral.sh/uv/install.sh | sh
    fi
    if ! command -v uv >/dev/null 2>&1; then
        echo "[1/4] uv: install failed" >> "$AUTO_CDLC_INSTALL_LOG"; fallo
    fi
    echo "[1/4] uv: installed now" >> "$AUTO_CDLC_INSTALL_LOG"
fi
uv --version >> "$AUTO_CDLC_INSTALL_LOG" 2>&1

# 2. Python and libraries
echo
t "[2/4] Preparando Python y las librerías. La primera vez tarda unos minutos" \
  "[2/4] Setting up Python and the libraries. The first time takes a few minutes"
if [ "$sistema" = "Darwin" ]; then t "      y descarga en torno a 1 GB." "      and downloads about 1 GB."
else t "      y descarga en torno a 4 GB (PyTorch para Linux trae las librerías de NVIDIA)." \
       "      and downloads about 4 GB (PyTorch for Linux brings NVIDIA's libraries)."; fi
if uv sync --frozen; then
    echo "[2/4] uv sync: ok" >> "$AUTO_CDLC_INSTALL_LOG"
else
    echo "[2/4] uv sync: FAILED, details:" >> "$AUTO_CDLC_INSTALL_LOG"
    uv sync --frozen --color never >> "$AUTO_CDLC_INSTALL_LOG" 2>&1
    fallo
fi

# 3 and 4. cdlc-pack, configuration, Wwise and Rocksmith's dlc folder (done by the program itself)
echo
t "[3/4] cdlc-pack, [4/4] configuración y comprobaciones" "[3/4] cdlc-pack, [4/4] configuration and checks"
chmod +x process.sh auto-cdlc.sh install.sh ./*.command 2>/dev/null
if ! uv run --frozen auto_cdlc.py --setup "$idioma"; then fallo; fi

echo
echo "============================================================"
if [ "$sistema" = "Darwin" ]; then
    t " Listo. Mete tus canciones en la carpeta input y abre auto-cdlc.command" \
      " Done. Put your songs in the input folder and open auto-cdlc.command"
else
    t " Listo. Mete tus canciones en la carpeta input y ejecuta ./auto-cdlc.sh" \
      " Done. Put your songs in the input folder and run ./auto-cdlc.sh"
fi
t " (o ./process.sh para procesarlas directamente)" " (or ./process.sh to process them straight away)"
echo "============================================================"
informe ok
