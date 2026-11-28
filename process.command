#!/usr/bin/env bash
# macOS: double-click to run process.sh in a Terminal window.
cd "$(dirname "$0")" || exit 1
exec ./process.sh "$@"
