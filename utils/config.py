import os

# APIs
ALPACA_API_KEY    = os.getenv("ALPACA_API_KEY")
ALPACA_SECRET_KEY = os.getenv("ALPACA_SECRET_KEY")
POLYGON_API_KEY   = os.getenv("POLYGON_API_KEY")
FINNHUB_API_KEY   = os.getenv("FINNHUB_API_KEY")
FMP_API_KEY       = os.getenv("FMP_API_KEY")
TELEGRAM_TOKEN    = os.getenv("TELEGRAM_TOKEN")
TELEGRAM_CHAT_ID  = os.getenv("TELEGRAM_CHAT_ID")

# ── HARD FILTERS (פוסלים מניה) ────────────────────────────
MIN_PRICE            = 1.0
MAX_PRICE            = 20.0
MIN_AVG_VOLUME       = 300_000      # נפח יומי מינימום
MAX_FLOAT            = 150_000_000  # float קשיח — מעל זה לא רץ
MIN_GAP_PCT          = 8.0          # גאפ מינימום 8%
MIN_PREMARKET_VOL    = 100_000      # נפח פרימרקט מינימום

# ── SOFT FILTERS (משפיעים על ציון בלבד) ──────────────────
MIN_DOLLAR_VOLUME    = 500_000
MIN_SCORE            = 50

# ── Cooldown ─────────────────────────────────────────────
COOLDOWN_HOURS       = 4

# ── News Keywords ─────────────────────────────────────────
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

# ── Weekly Report ─────────────────────────────────────────
WEEKLY_REPORT_DAY = 4
