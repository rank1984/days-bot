import os

ALPACA_API_KEY    = os.getenv("ALPACA_API_KEY")
ALPACA_SECRET_KEY = os.getenv("ALPACA_SECRET_KEY")
POLYGON_API_KEY   = os.getenv("POLYGON_API_KEY")
FINNHUB_API_KEY   = os.getenv("FINNHUB_API_KEY")
FMP_API_KEY       = os.getenv("FMP_API_KEY")
TELEGRAM_TOKEN    = os.getenv("TELEGRAM_TOKEN")
TELEGRAM_CHAT_ID  = os.getenv("TELEGRAM_CHAT_ID")

# ── FILTERS ──────────────────────────────────────────────
MIN_PRICE            = 1.0          # $1 minimum – avoid pennies
MAX_PRICE            = 50.0
MIN_AVG_VOLUME       = 50_000       # minimum daily volume
MIN_GAP_PCT          = 3.0          # need some gap
MAX_GAP_PCT          = 25.0         # avoid already extended

# ── READY CRITERIA (HARD) ──────────────────────────────
MIN_READY_RVOL = 2.0
MIN_READY_EVENT_SCORE = 70
MAX_READY_SPREAD = 1.5              # % – REJECT if unknown or >1.5%
MIN_READY_VWAP_DIST = 0.0           # price must be above VWAP
MAX_PM_HIGH_DIST_READY = 2.0        # must be within 2% of PM High

# ── PRE-RUNNER ────────────────────────────────────────────
PRE_RUNNER_MIN_GAIN = 8.0
PRE_RUNNER_MIN_VOLUME = 200_000
PRE_RUNNER_MAX_GAP = 25.0

# ── RISK ──────────────────────────────────────────────────
MAX_RISK_PER_TRADE = 0.02           # 2% of equity
MAX_POSITION_NOTIONAL = 0.20        # 20% of equity
MAX_DAILY_LOSS = 0.05               # 5% of equity

# ── POSITION & TRADE LIMITS ─────────────────────────────
MAX_ACTIVE_TRADES = 2
MAX_TRADES_PER_DAY = 2              # only 2 per day

# ── SCORING WEIGHTS ──────────────────────────────────────
WEIGHT_RVOL = 20
WEIGHT_PREMARKET_MOMENTUM = 15
WEIGHT_FLOAT = 15
WEIGHT_DOLLAR_VOLUME = 15
WEIGHT_PM_HIGH_DISTANCE = 10
WEIGHT_VWAP = 10
WEIGHT_CATALYST = 10
WEIGHT_LIQUIDITY = 5

# ── DISABLE SLOW FEATURES ──────────────────────────────
ENABLE_FLOAT_LOOKUP = False         # keep off until we have reliable data
ENABLE_PRE_RUNNER = True

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
