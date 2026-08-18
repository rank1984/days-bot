"""
Configuration module for DAYS-BOT V2.3
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

# ── TRADING SCANNER PARAMETERS (RELAXED FOR TESTING & ALL-HOURS) ──
MIN_PRICE       = float(os.getenv("MIN_PRICE", 0.10))
MAX_PRICE       = float(os.getenv("MAX_PRICE", 50.00))
MIN_GAP_PCT     = float(os.getenv("MIN_GAP_PCT", -5.0))   # כולל ירידות קלות
MAX_GAP_PCT     = float(os.getenv("MAX_GAP_PCT", 100.0))  # הרחבת הטווח
MIN_AVG_VOLUME  = int(os.getenv("MIN_AVG_VOLUME", 5_000))  # הופחת לטובת מניות קטנות

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

# ── DAYS-BOT V2.3 LOGIC CONFIG ─────────────────────────────
# RVOL
MIN_READY_RVOL = 10.0

# Event Score thresholds
MIN_EVENT_SCORE = 30
MIN_READY_EVENT_SCORE = 70

# Spread
MAX_READY_SPREAD = 2.0

# Float
ENABLE_FLOAT_LOOKUP = True if FMP_API_KEY else False

# Entry limits
MAX_ACTIVE_TRADES = 2
MAX_TRADES_PER_DAY = 3

# Anti-chase
MAX_GAP_FOR_READY = 30.0        # gaps above this cannot go READY directly
PM_HIGH_DISTANCE_REJECT = 7.0   # % below PM High to reject
PM_HIGH_DISTANCE_WATCH = 2.0    # % below PM High for normal WATCH
