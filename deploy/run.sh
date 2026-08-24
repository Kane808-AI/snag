#!/bin/zsh
# Launcher for the Snag Telegram bot (Hermes build).
# launchd does NOT inherit the user's shell PATH — homebrew must be added here
# or subprocess calls (yt-dlp, ffprobe) fail with "No such file or directory".
export PATH="/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin:$PATH"
cd "$(dirname "$0")/.." || exit 1
exec /opt/homebrew/bin/python3 -u bot.py
