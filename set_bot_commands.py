"""Register the bot's slash-command menu in Telegram (the / popup users see)."""
import json
import urllib.request
import config

COMMANDS = [
    {"command": "start", "description": "What this bot does + how to use it"},
    {"command": "vault", "description": "Browse your saved ideas"},
    {"command": "search", "description": "Search your vault: /search <word>"},
    {"command": "upgrade", "description": "Go Pro for unlimited videos"},
]


def main():
    if not config.TELEGRAM_BOT_TOKEN:
        raise SystemExit("TELEGRAM_BOT_TOKEN not set")
    url = f"https://api.telegram.org/bot{config.TELEGRAM_BOT_TOKEN}/setMyCommands"
    data = json.dumps({"commands": COMMANDS}).encode()
    req = urllib.request.Request(url, data=data, headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=20) as r:
        resp = json.loads(r.read().decode())
    print("✅ bot command menu registered" if resp.get("ok") else f"⚠️  {resp}")


if __name__ == "__main__":
    main()
