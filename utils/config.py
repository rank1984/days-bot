import os

# API Keys
ALPACA_API_KEY    = os.getenv("ALPACA_API_KEY")
ALPACA_SECRET_KEY = os.getenv("ALPACA_SECRET_KEY")
POLYGON_API_KEY   = os.getenv("POLYGON_API_KEY")
FINNHUB_API_KEY   = os.getenv("FINNHUB_API_KEY")
FMP_API_KEY       = os.getenv("FMP_API_KEY")
TELEGRAM_TOKEN    = os.getenv("TELEGRAM_TOKEN")
TELEGRAM_CHAT_ID  = os.getenv("TELEGRAM_CHAT_ID")

# ── FILTERS ──────────────────────────────────────────────
MIN_PRICE            = 0.5
MAX_PRICE            = 20.0
MIN_GAP_PCT          = 3.0
MAX_GAP_PCT          = 25.0
MIN_PREMARKET_VOL    = 200_000
MIN_DOLLAR_VOLUME    = 1_000_000
MIN_RELATIVE_VOLUME  = 2.0
MAX_SPREAD_PCT       = 2.0
MAX_FLOAT            = 50_000_000  # אם יהיו נתונים
MIN_AVG_VOLUME       = 5_000   # זמני - כדי לראות אם יש נתונים
# ── SCORING WEIGHTS ──────────────────────────────────────
WEIGHT_GAP           = 25
WEIGHT_VOLUME        = 25
WEIGHT_RVOL          = 20
WEIGHT_DOLLAR_VOL    = 15
WEIGHT_CATALYST      = 10
WEIGHT_FLOAT         = 5

# ── SCORING ───────────────────────────────────────────────
MIN_SCORE            = 15          # סף מעבר

# ── COOLDOWN ─────────────────────────────────────────────
COOLDOWN_HOURS       = 4

# ── NEWS ─────────────────────────────────────────────────
POSITIVE_CATALYSTS = [
    "fda","approval","approved","contract","acquisition",
    "acquires","merger","patent","earnings","revenue",
    "partnership","grant","award","breakthrough","positive",
    "phase","trial","clearance","designation",
]
NEGATIVE_CATALYSTS = [
    "offering","direct offering","shelf","registration",
    "dilution","warrant","priced offering","atm",
]

WEEKLY_REPORT_DAY = 4

# ── BACKTEST ─────────────────────────────────────────────
BACKTEST_LOOKBACK_DAYS = 30
BACKTEST_MIN_TRADES = 50
