#!/bin/zsh
# Weekly yt-dlp upgrade. TikTok changes its page markup every 1-3 months and
# breaks yt-dlp. Both the Snag bot (Hermes) and the OpenClaw tokaction bot call
# /opt/homebrew/bin/yt-dlp, so keeping the Homebrew formula current is the fix.
# Scheduled by ~/Library/LaunchAgents/com.hermes.ytdlp-upgrade.plist (Sun 9 AM PT).
export PATH="/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin"
LOG="$HOME/.hermes/workspace/snag/logs/ytdlp-upgrade.log"
mkdir -p "$(dirname "$LOG")"
{
  echo "=== $(date '+%Y-%m-%d %H:%M:%S %Z') ==="
  echo "before: $(/opt/homebrew/bin/yt-dlp --version 2>&1)"
  /opt/homebrew/bin/brew update --quiet 2>&1 | tail -3
  /opt/homebrew/bin/brew upgrade yt-dlp 2>&1 | tail -3
  echo "after:  $(/opt/homebrew/bin/yt-dlp --version 2>&1)"
} >> "$LOG" 2>&1
