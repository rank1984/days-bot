import os

ALPACA_API_KEY    = os.getenv("ALPACA_API_KEY")
ALPACA_SECRET_KEY = os.getenv("ALPACA_SECRET_KEY")
POLYGON_API_KEY   = os.getenv("POLYGON_API_KEY")
FINNHUB_API_KEY   = os.getenv("FINNHUB_API_KEY")
FMP_API_KEY       = os.getenv("FMP_API_KEY")
TELEGRAM_TOKEN    = os.getenv("TELEGRAM_TOKEN")
TELEGRAM_CHAT_ID  = os.getenv("TELEGRAM_CHAT_ID")

# ── FILTERS (V2.2 FAST) ──────────────────────────────
MIN_PRICE            = 0.1
MAX_PRICE            = 50.0
MIN_AVG_VOLUME       = 10_000
MIN_GAP_PCT          = -5.0
MAX_GAP_PCT          = 30.0

# ── SCORING ───────────────────────────────────────────────
MIN_SCORE            = 20

# ── Cooldown ─────────────────────────────────────────────
COOLDOWN_HOURS       = 4

# ── News ─────────────────────────────────────────────────
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

# ── DISABLE SLOW FEATURES ──────────────────────────────
ENABLE_FLOAT_LOOKUP = False
ENABLE_PRE_RUNNER = False

# ── ENTRY LIMITS ──────────────────────────────────────────
MAX_ACTIVE_TRADES = 2
MAX_TRADES_PER_DAY = 3
