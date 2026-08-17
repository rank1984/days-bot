"""
Configuration module for DAYS-BOT
Loads environment variables and sets system defaults.
"""
import os
from pathlib import Path
from dotenv import load_dotenv

# טעינת קובץ .env במידה וקיים
BASE_DIR = Path(__file__).resolve().parent.parent
env_path = BASE_DIR / ".env"
if env_path.exists():
    load_dotenv(dotenv_path=env_path)

# ── TELEGRAM CONFIG ─────────────────────────────────────────
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN", "")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "")

# ── API KEYS ──────────────────────────────────────────────
ALPACA_API_KEY    = os.getenv("ALPACA_API_KEY", "")
ALPACA_SECRET_KEY = os.getenv("ALPACA_SECRET_KEY", "")
POLYGON_API_KEY   = os.getenv("POLYGON_API_KEY", "")
FINNHUB_API_KEY   = os.getenv("FINNHUB_API_KEY", "")
FMP_API_KEY       = os.getenv("FMP_API_KEY", "")

# ====== HARDCODED FOR TESTING (Remove or comment out after test) ======
FINNHUB_API_KEY = os.getenv("FINNHUB_API_KEY") or "zEWD5UCJZmlXTmNnvzGm1pKIyiSRGRqK"
FMP_API_KEY     = os.getenv("FMP_API_KEY") or "YOUR_FMP_KEY_HERE"
POLYGON_API_KEY = os.getenv("POLYGON_API_KEY") or "YOUR_POLYGON_KEY_HERE"

# ── TRADING SCANNER PARAMETERS ─────────────────────────────
MIN_PRICE = 0.50
MAX_PRICE = 20.00
MIN_GAP_PCT = 10.0
MAX_GAP_PCT = 200.0
MIN_AVG_VOLUME = 500_000

# ── V2 CRITERIA ─────────────────────────────────────────────
MIN_READY_EVENT_SCORE = 60
MIN_READY_RVOL = 1.5
MAX_READY_SPREAD = 3.0

# ── CATALYST DICTIONARIES ───────────────────────────────────
POSITIVE_CATALYSTS = [
    "fda", "approval", "earnings", "revenue", "guidance", "contract",
    "patent", "phase 3", "phase 2", "acquisition", "merger", "buyout",
    "offering completed", "partnership", "collaboration", "bitcoin", "crypto"
]

NEGATIVE_CATALYSTS = [
    "dilution", "direct offering", "public offering", "atm", "bankruptcy",
    "investigation", "delisting", "reverse split", "sec subpoena"
]
