import os
from pathlib import Path

# נסה לטעון את python-dotenv אם הוא קיים (לשימוש מקומי)
try:
    from dotenv import load_dotenv
    # טעינה מקובץ .env שנמצא בתיקיית השורש של הפרויקט
    env_path = Path(__file__).resolve().parent.parent / '.env'
    load_dotenv(dotenv_path=env_path)
except ImportError:
    pass

# ── API KEYS ──────────────────────────────────────────────
ALPACA_API_KEY    = os.getenv("ALPACA_API_KEY")
ALPACA_SECRET_KEY = os.getenv("ALPACA_SECRET_KEY")
POLYGON_API_KEY   = os.getenv("POLYGON_API_KEY")
FINNHUB_API_KEY   = os.getenv("FINNHUB_API_KEY")
FMP_API_KEY       = os.getenv("FMP_API_KEY")
TELEGRAM_TOKEN    = os.getenv("TELEGRAM_TOKEN")
TELEGRAM_CHAT_ID  = os.getenv("TELEGRAM_CHAT_ID")

# ── FILTERS (גמישים ללמידה) ──────────────────────────────
MIN_PRICE            = 0.5
MAX_PRICE            = 20.0
MIN_AVG_VOLUME       = 1_000       # נפח מסחר מינימלי
MIN_GAP_PCT          = 1.0         # אחוז גאפ מינימלי
MAX_GAP_PCT          = 25.0
MIN_RVOL             = 0.0         # בוטל
MIN_DOLLAR_VOLUME    = 0           # בוטל

# ── SCORING ───────────────────────────────────────────────
MIN_SCORE            = 20          # ניקוד מינימלי לסריקה

# ── COOLDOWN & TIMING ─────────────────────────────────────
ENABLE_COOLDOWN      = True        # הפעלת מנגנון צינון
COOLDOWN_HOURS       = 4
WEEKLY_REPORT_DAY    = 4

# ── NEWS & CATALYSTS ──────────────────────────────────────
POSITIVE_CATALYSTS = [
    "fda", "approval", "approved", "contract", "acquisition",
    "acquires", "merger", "patent", "earnings", "revenue",
    "partnership", "grant", "award", "breakthrough", "positive",
    "phase", "trial", "clearance", "designation",
]
NEGATIVE_CATALYSTS = [
    "offering", "direct offering", "shelf", "registration",
    "dilution", "warrant", "priced offering", "atm",
]

# ── BACKTEST ──────────────────────────────────────────────
BACKTEST_LOOKBACK_DAYS = 30
BACKTEST_MIN_TRADES = 50

# ── EVENT ENGINE ──────────────────────────────────────────
MIN_READY_RVOL = 10.0
MIN_EVENT_SCORE = 30
MIN_READY_EVENT_SCORE = 70
MAX_READY_SPREAD = 2.0

ENABLE_FLOAT_TURNOVER = True
ENABLE_RISK_ENGINE = True

RVOL_EVENT_THRESHOLD = 20.0
RVOL_EXTREME_THRESHOLD = 50.0

FLOAT_TURNOVER_EVENT_THRESHOLD = 3.0
FLOAT_TURNOVER_EXTREME_THRESHOLD = 10.0
