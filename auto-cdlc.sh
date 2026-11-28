#!/usr/bin/env bash
# auto-cdlc for Linux and macOS: the interface (songs, batch, settings). Same as auto-cdlc.bat on Windows:
# first a quick check for a new version, then the interface.
cd "$(dirname "$0")" || exit 1
export PATH="$HOME/.local/bin:$HOME/.cargo/bin:$PATH" PYTHONUTF8=1 AUTO_CDLC_BAT="$(basename "$0")"
if ! command -v uv >/dev/null 2>&1; then
    echo "No encuentro uv: ejecuta primero ./install.sh  |  uv not found: run ./install.sh first"
    exit 1
fi
uv run --frozen auto_cdlc.py --update-only
if [ "$?" -eq 10 ]; then
    echo
    echo "auto-cdlc actualizado / updated..."
    uv sync --frozen
    exec "$0" "$@"
fi
uv run --frozen ui.py
