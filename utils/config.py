import os

ALPACA_API_KEY    = os.getenv("ALPACA_API_KEY")
ALPACA_SECRET_KEY = os.getenv("ALPACA_SECRET_KEY")
POLYGON_API_KEY   = os.getenv("POLYGON_API_KEY")
FINNHUB_API_KEY   = os.getenv("FINNHUB_API_KEY")
FMP_API_KEY       = os.getenv("FMP_API_KEY")
TELEGRAM_TOKEN    = os.getenv("TELEGRAM_TOKEN")
TELEGRAM_CHAT_ID  = os.getenv("TELEGRAM_CHAT_ID")

# ── DISCOVERY ──────────────────────────────────────────────
DISCOVERY_MIN_PRICE = 1.0
DISCOVERY_MAX_PRICE = 50.0
DISCOVERY_MIN_GAP = 1.0          # 1-30% (בכוונה)
DISCOVERY_MAX_GAP = 30.0

# ── VALIDATION (HARD FILTERS) ────────────────────────────
VALIDATION_MIN_RVOL = 2.0
VALIDATION_MAX_PM_DIST = 2.0      # % below PM High
VALIDATION_MIN_VWAP_DIST = 0.01   # 1% above VWAP
VALIDATION_MIN_CATALYST_SCORE = 0
VALIDATION_MAX_SPREAD = 1.5       # % – BLOCK if >1.5% or UNKNOWN

# ── RISK & POSITION ──────────────────────────────────────
MAX_RISK_PER_TRADE = 0.01
MAX_POSITION_NOTIONAL = 0.20
MAX_DAILY_LOSS = 0.03
MAX_TRADES_PER_DAY = 2
MAX_ACTIVE_TRADES = 2

# ── NET PROFIT ──────────────────────────────────────────
MIN_NET_PROFIT_PCT = 4.0
TAX_RATE = 0.25
BROKER_FEE_PCT = 0.018
BROKER_FEE_MIN = 1.50

# ── SCORING WEIGHTS ─────────────────────────────────────
WEIGHT_RVOL = 20
WEIGHT_PREMARKET_MOMENTUM = 15
WEIGHT_FLOAT = 15
WEIGHT_DOLLAR_VOLUME = 15
WEIGHT_PM_HIGH_DISTANCE = 10
WEIGHT_VWAP = 10
WEIGHT_CATALYST = 10
WEIGHT_LIQUIDITY = 5

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
