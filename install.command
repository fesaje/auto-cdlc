#!/usr/bin/env bash
# macOS: double-click to run install.sh in a Terminal window.
cd "$(dirname "$0")" || exit 1
exec ./install.sh "$@"
