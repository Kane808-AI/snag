#!/bin/zsh
# One-command bootstrap for the Snag bot (Hermes build).
#   ./setup.sh            -> set up + run in foreground
#   ./setup.sh --install  -> also install the launchd service (auto-start/restart)
#
# Needs only TWO secrets for a working bot: TELEGRAM_BOT_TOKEN + DEEPSEEK_API_KEY.
# ScrapeCreators + Stripe are optional upgrades.
set -e
cd "$(dirname "$0")"

PY=/opt/homebrew/bin/python3

# 1. Ensure .env exists
if [[ ! -f .env ]]; then
  cp .env.example .env
  echo "📝 Created .env from template."
  echo "   Fill in at minimum:"
  echo "     TELEGRAM_BOT_TOKEN   (from @BotFather -> /newbot)"
  echo "     DEEPSEEK_API_KEY     (api.deepseek.com)"
  echo ""
  echo "   Open it now:  open -e .env"
  echo "   Then re-run:  ./setup.sh"
  exit 0
fi

# 2. Verify the two required keys are present
missing=0
grep -q '^TELEGRAM_BOT_TOKEN=.\+' .env || { echo "❌ TELEGRAM_BOT_TOKEN missing in .env"; missing=1; }
grep -q '^DEEPSEEK_API_KEY=.\+' .env || { echo "❌ DEEPSEEK_API_KEY missing in .env"; missing=1; }
[[ $missing -eq 1 ]] && { echo "Fill those in (open -e .env) and re-run."; exit 1; }

# 3. Init DB + register the bot's slash-command menu in Telegram
$PY -c "import db; db.init(); print('✅ database ready')"
$PY set_bot_commands.py || echo "⚠️  could not set command menu (bot still works)"

# 4. Optional: install launchd service
if [[ "$1" == "--install" ]]; then
  cp deploy/com.hermes.snag.plist ~/Library/LaunchAgents/
  chmod +x deploy/run.sh
  launchctl unload ~/Library/LaunchAgents/com.hermes.snag.plist 2>/dev/null || true
  launchctl load ~/Library/LaunchAgents/com.hermes.snag.plist
  echo "✅ installed + started as launchd service (com.hermes.snag)"
  echo "   logs: ~/.hermes/workspace/snag/logs/bot.log"
  exit 0
fi

# 5. Run in foreground
echo "🚀 starting bot (Ctrl-C to stop)…"
exec $PY bot.py
