import os

# ============================================================
# DAYS-BOT V4.1 – CENTRAL CONFIG
# ============================================================

BOT_VERSION = "V4.1"
STRATEGY_VERSION = "V4.1"
EXPERIMENT_MODE = "V4.1_LIVE_RESEARCH"
DATA_VERSION = "ALPACA_IEX_V41"

# ------------------------------------------------------------
# API KEYS
# ------------------------------------------------------------

ALPACA_API_KEY = os.getenv("ALPACA_API_KEY", "")
ALPACA_SECRET_KEY = os.getenv("ALPACA_SECRET_KEY", "")

# Trading API – NOT USED FOR AUTOMATIC ORDERS
ALPACA_BASE_URL = os.getenv(
    "ALPACA_BASE_URL",
    "https://paper-api.alpaca.markets"
)

# Market Data API
ALPACA_DATA_URL = os.getenv(
    "ALPACA_DATA_URL",
    "https://data.alpaca.markets"
)

FINNHUB_API_KEY = os.getenv("FINNHUB_API_KEY", "")
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN", "")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")

# ------------------------------------------------------------
# DISCOVERY
# ------------------------------------------------------------

DISCOVERY_MIN_PRICE = 1.00
DISCOVERY_MAX_PRICE = 30.00

# Lowered from 5% so the scanner can discover useful setups.
DISCOVERY_MIN_GAP = 3.0
DISCOVERY_MAX_GAP = 100.0

DISCOVERY_MIN_VOLUME = 50_000
DISCOVERY_MIN_PM_VOLUME = 50_000

MAX_DISCOVERY_CANDIDATES = 40
MAX_ANALYSIS_CANDIDATES = 25
TOP_RESEARCH_CANDIDATES = 5

# ------------------------------------------------------------
# VALIDATION
# ------------------------------------------------------------

VALIDATION_MAX_SPREAD = 2.0
VALIDATION_MIN_PM_VOLUME_ABS = 100_000
VALIDATION_MIN_PM_BARS = 5
VALIDATION_MAX_PM_DIST = 5.0
VALIDATION_MIN_VWAP_DIST = 0.0
VALIDATION_MIN_RVOL = 0.0
VALIDATION_MIN_CATALYST_SCORE = 0

# IMPORTANT:
# These remain soft signals during research.
USE_RVOL_AS_HARD_GATE = False
USE_CATALYST_AS_HARD_GATE = False
USE_PM_BARS_AS_HARD_GATE = False
USE_FLOAT_AS_HARD_GATE = False
USE_PERSONALITY_AS_HARD_GATE = False

# ------------------------------------------------------------
# RISK / ACCOUNT
# ------------------------------------------------------------

ACCOUNT_SIZE = 5000.0

# Preserve existing risk configuration.
MAX_RISK_PER_TRADE_V31 = 0.005
MAX_POSITION_VALUE_PCT = 0.20

MAX_ACTIVE_TRADES = 3
MAX_TRADES_PER_DAY = 5
MAX_DAILY_LOSS = 0.03

MAX_RISK_PER_TRADE = 0.005

# ------------------------------------------------------------
# TRADE ECONOMICS
# ------------------------------------------------------------

MIN_NET_PROFIT_PCT = 1.5

# Blink / Israel cost model.
# Keep configurable; do not hardcode tax assumptions in strategy logic.
BLINK_FEE_PER_SHARE = 0.01
BLINK_MIN_FEE = 1.50
BLINK_MAX_FEE_PCT = 0.018

ISRAEL_CAPITAL_GAINS_TAX_RATE = float(
    os.getenv("ISRAEL_CAPITAL_GAINS_TAX_RATE", "0.25")
)

ESTIMATED_SLIPPAGE_PCT = 0.15

# ------------------------------------------------------------
# MARKET REGIME
# ------------------------------------------------------------

REGIME_FAVORABLE_MULTIPLIER = 1.00
REGIME_NEUTRAL_MULTIPLIER = 0.75
REGIME_HOSTILE_MULTIPLIER = 0.50

# ------------------------------------------------------------
# DATA QUALITY
# ------------------------------------------------------------

MIN_DATA_QUALITY = 0.70

# ------------------------------------------------------------
# LEARNING / RESEARCH
# ------------------------------------------------------------

EXPERIMENT_MODE_ACTIVE = True
LEARNING_MODE = True

# ------------------------------------------------------------
# EXECUTION SAFETY
# ------------------------------------------------------------

# DAYS-BOT never places live orders.
AUTO_EXECUTION_ENABLED = False
