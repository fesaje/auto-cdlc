#!/usr/bin/env bash
# macOS: double-click to run auto-cdlc.sh in a Terminal window.
cd "$(dirname "$0")" || exit 1
exec ./auto-cdlc.sh "$@"
