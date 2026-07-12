import os

ALPACA_API_KEY    = os.getenv("ALPACA_API_KEY")
ALPACA_SECRET_KEY = os.getenv("ALPACA_SECRET_KEY")
POLYGON_API_KEY   = os.getenv("POLYGON_API_KEY")
FINNHUB_API_KEY   = os.getenv("FINNHUB_API_KEY")
FMP_API_KEY       = os.getenv("FMP_API_KEY")
TELEGRAM_TOKEN    = os.getenv("TELEGRAM_TOKEN")
TELEGRAM_CHAT_ID  = os.getenv("TELEGRAM_CHAT_ID")

# ── HARD FILTERS ──────────────────────────────────────────
MIN_PRICE            = 0.5        # מניות זולות
MAX_PRICE            = 20.0       # עלייה קלה - יותר אפשרויות
MIN_AVG_VOLUME       = 50_000     # הורד - מניות קטנות
MAX_FLOAT            = 100_000_000 # עלייה - יותר אפשרויות
MIN_GAP_PCT          = 0.0        # כולל 0
MAX_GAP_PCT          = 3.0        # מקסימום 3%

# ── SCORING ───────────────────────────────────────────────
MIN_SCORE            = 30          # הורד - לקבל יותר מועמדויות

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
