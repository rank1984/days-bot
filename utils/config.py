import os

# ── API ──────────────────────────────────────────────────
ALPACA_API_KEY    = os.getenv("ALPACA_API_KEY")
ALPACA_SECRET_KEY = os.getenv("ALPACA_SECRET_KEY")
POLYGON_API_KEY   = os.getenv("POLYGON_API_KEY")
FINNHUB_API_KEY   = os.getenv("FINNHUB_API_KEY")
FMP_API_KEY       = os.getenv("FMP_API_KEY")
TELEGRAM_TOKEN    = os.getenv("TELEGRAM_TOKEN")
TELEGRAM_CHAT_ID  = os.getenv("TELEGRAM_CHAT_ID")

# ── HARD FILTERS ──────────────────────────────────────────
MIN_PRICE            = 1.0          # $1 minimum – avoid pennies
MAX_PRICE            = 50.0
MIN_AVG_VOLUME       = 50_000       # minimum daily volume (fallback)
MIN_PREMARKET_VOL    = 200_000      # minimum premarket volume
MIN_GAP_PCT          = 3.0          # need some gap
MAX_GAP_PCT          = 20.0         # avoid already extended (READY limit)

# ── PREMARKET DATA (needs minute bars) ──────────────────
MIN_PREMARKET_VOL    = 200_000
MIN_READY_RVOL       = 2.0          # time-adjusted RVOL minimum
MAX_READY_SPREAD     = 1.5          # % – REJECT if unknown or >1.5%
MAX_PM_HIGH_DIST     = 2.0          # % below PM High to be READY
MIN_VWAP_DIST        = 0.01         # price must be at least 1% above VWAP

# ── PRE-RUNNER ────────────────────────────────────────────
PRE_RUNNER_MIN_GAIN = 8.0
PRE_RUNNER_MIN_VOLUME = 200_000
PRE_RUNNER_MAX_GAP = 20.0

# ── RISK & POSITION ──────────────────────────────────────
MAX_RISK_PER_TRADE = 0.01           # 1% of equity (conservative)
MAX_POSITION_NOTIONAL = 0.20        # 20% of equity
MAX_DAILY_LOSS = 0.03               # 3% daily loss – stops new signals
MAX_TRADES_PER_DAY = 2              # max 2 trades per day
MAX_ACTIVE_TRADES = 2               # max 2 open positions

# ── NET PROFIT GATE ──────────────────────────────────────
MIN_NET_PROFIT_PCT = 4.0            # minimum net expected profit after costs
TAX_RATE = 0.25                     # 25% capital gains tax (Israel)
BROKER_FEE_PCT = 0.018              # max 1.8% of trade value (Blink)
BROKER_FEE_MIN = 1.50               # min $1.50 per trade (Blink)

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
