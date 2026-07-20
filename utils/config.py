import os

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
MIN_AVG_VOLUME       = 10_000       # הורד – 100K היה גבוה מדי
MIN_GAP_PCT          = 1.0          # הורד – 3% צר מדי
MAX_GAP_PCT          = 25.0
MIN_DOLLAR_VOLUME    = 200_000      # הורד – $1M גבוה מדי
MIN_RVOL             = 1.0          # הורד/בטל – 2.0 נוקשה

# ── SCORING ───────────────────────────────────────────────
MIN_SCORE            = 30           # הורד – 50 נוקשה מדי

# ── COOLDOWN ─────────────────────────────────────────────
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
