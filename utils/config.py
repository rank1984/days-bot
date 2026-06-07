import os

# APIs
ALPACA_API_KEY    = os.getenv("ALPACA_API_KEY")
ALPACA_SECRET_KEY = os.getenv("ALPACA_SECRET_KEY")
POLYGON_API_KEY   = os.getenv("POLYGON_API_KEY")
FINNHUB_API_KEY   = os.getenv("FINNHUB_API_KEY")
FMP_API_KEY       = os.getenv("FMP_API_KEY")
TELEGRAM_TOKEN    = os.getenv("TELEGRAM_TOKEN")
TELEGRAM_CHAT_ID  = os.getenv("TELEGRAM_CHAT_ID")

# ── Universe Filters ──────────────────────────────────────
MIN_PRICE            = 1.0
MAX_PRICE            = 20.0
MAX_MARKET_CAP       = 2_000_000_000   # 2B
MIN_AVG_VOLUME       = 500_000         # נפח יומי מינימום

# שדרוג #1 — Float Filter
MAX_FLOAT            = 20_000_000      # עדיף מתחת ל-10M
PREFERRED_FLOAT      = 10_000_000

# ── Premarket Filters ─────────────────────────────────────
MIN_GAP_PCT          = 5.0
MIN_PREMARKET_VOL    = 50_000
MIN_RVOL             = 1.5

# שדרוג #5 — Dollar Volume
MIN_DOLLAR_VOLUME    = 1_000_000       # מינימום $1M traded בפרימרקט

# ── Scoring ───────────────────────────────────────────────
MIN_SCORE            = 60

# ── שדרוג #4 — Cooldown ──────────────────────────────────
COOLDOWN_HOURS       = 4               # לא לשלוח אותה מניה תוך 4 שעות

# ── שדרוג #2 — News Keywords ─────────────────────────────
POSITIVE_CATALYSTS   = [
    "fda", "approval", "approved", "contract", "acquisition",
    "acquires", "merger", "patent", "earnings", "revenue",
    "partnership", "grant", "award", "breakthrough", "positive",
    "phase", "trial", "clearance", "designation",
]
NEGATIVE_CATALYSTS   = [
    "offering", "direct offering", "shelf", "registration",
    "dilution", "warrant", "priced offering", "atm",
]
