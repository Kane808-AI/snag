#!/bin/zsh
# Launcher for the Snag web API (vault viewer backend, read-only).
# launchd does NOT inherit the shell PATH; homebrew must be added here
# (though server.py is stdlib-only, keep PATH parity with the bot).
export PATH="/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin:$PATH"
cd "$(dirname "$0")/.." || exit 1
exec /opt/homebrew/bin/python3 -u webview/server.py
