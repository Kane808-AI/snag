"""Central config. Reads from environment / .env. No secrets committed."""
import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent

# Load a sibling .env if present (no third-party deps).
def _load_env():
    env_path = BASE_DIR / ".env"
    if env_path.exists():
        for line in env_path.read_text().splitlines():
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, _, val = line.partition("=")
            # strip inline comments (" # ..."); keys never contain " #"
            if " #" in val:
                val = val[: val.index(" #")]
            os.environ.setdefault(key.strip(), val.strip().strip('"').strip("'"))

_load_env()

# --- Credentials (provided by Chris; never hardcode) ---
TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "")
DEEPSEEK_API_KEY = os.environ.get("DEEPSEEK_API_KEY", "")
SCRAPECREATORS_API_KEY = os.environ.get("SCRAPECREATORS_API_KEY", "")  # optional downloader
SCRAPTIK_API_KEY = os.environ.get("SCRAPTIK_API_KEY", "")              # optional failover (RapidAPI)
STRIPE_SECRET_KEY = os.environ.get("STRIPE_SECRET_KEY", "")
STRIPE_WEBHOOK_SECRET = os.environ.get("STRIPE_WEBHOOK_SECRET", "")
STRIPE_PRICE_ID = os.environ.get("STRIPE_PRICE_ID", "")               # the recurring Pro price
PUBLIC_BASE_URL = os.environ.get("PUBLIC_BASE_URL", "")               # for Stripe success/cancel + webhook

# --- Model config (DeepSeek, text-only) ---
DEEPSEEK_BASE_URL = os.environ.get("DEEPSEEK_BASE_URL", "https://api.deepseek.com")
DEEPSEEK_MODEL = os.environ.get("DEEPSEEK_MODEL", "deepseek-v4-flash")

# --- Product config ---
FREE_MONTHLY_LIMIT = int(os.environ.get("FREE_MONTHLY_LIMIT", "10"))
FREE_MAX_VIDEO_SECONDS = int(os.environ.get("FREE_MAX_VIDEO_SECONDS", "180"))  # protect margins
WHISPER_MODEL = os.environ.get("WHISPER_MODEL", "small")  # local transcription model size
DB_PATH = os.environ.get("DB_PATH", str(BASE_DIR / "data" / "app.db"))
WORK_DIR = os.environ.get("WORK_DIR", "/tmp/snag")
# Persistent browser profile for Instagram/Facebook capture (log in once).
SOCIAL_BROWSER_PROFILE = os.environ.get("SOCIAL_BROWSER_PROFILE", str(BASE_DIR / "data" / "browser-profile"))
BRAND_NAME = os.environ.get("BRAND_NAME", "Snag")
