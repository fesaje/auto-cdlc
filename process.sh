#!/usr/bin/env bash
# auto-cdlc for Linux and macOS: processes the songs in input (or the files and folders given).
# Same as process.bat on Windows. Exit code 10 = it has just updated itself: install the new libraries
# and start again.
cd "$(dirname "$0")" || exit 1
export PATH="$HOME/.local/bin:$HOME/.cargo/bin:$PATH" PYTHONUTF8=1 AUTO_CDLC_BAT="$(basename "$0")"
if ! command -v uv >/dev/null 2>&1; then
    echo "No encuentro uv: ejecuta primero ./install.sh  |  uv not found: run ./install.sh first"
    exit 1
fi
uv run --frozen auto_cdlc.py "$@"
codigo=$?
if [ "$codigo" -eq 10 ]; then
    echo
    echo "auto-cdlc actualizado / updated..."
    uv sync --frozen
    exec "$0" "$@"
fi
exit "$codigo"
