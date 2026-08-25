#!/bin/zsh
# Launcher for the Snag web frontend (production TanStack build).
# launchd does NOT inherit the shell PATH; node lives in /usr/local/bin.
export PATH="/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin:$PATH"
cd "$(dirname "$0")/../web" || exit 1
export PORT=8080
export HOST=127.0.0.1
exec node .output/server/index.mjs
