import os

# ============================================================
# BOT VERSION / EXPERIMENT METADATA
# ============================================================

BOT_VERSION = "V2.14"
STRATEGY_VERSION = "V2.14"
EXPERIMENT_MODE = "EXPERIMENT_V2.14"
DATA_VERSION = "ALPACA_IEX_PM"


# ============================================================
# API KEYS
# ============================================================

ALPACA_API_KEY = os.getenv("ALPACA_API_KEY", "")
ALPACA_SECRET_KEY = os.getenv("ALPACA_SECRET_KEY", "")
ALPACA_BASE_URL = os.getenv(
    "ALPACA_BASE_URL",
    "https://api.alpaca.markets"
)

FINNHUB_API_KEY = os.getenv("FINNHUB_API_KEY", "")

TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN", "")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "")


# ============================================================
# DISCOVERY (FROZEN FOR EXPERIMENT)
# ============================================================

DISCOVERY_MIN_PRICE = 2.0
DISCOVERY_MAX_PRICE = 20.0

DISCOVERY_MIN_GAP = 8.0
DISCOVERY_MAX_GAP = 100.0


# ============================================================
# VALIDATION (FROZEN FOR EXPERIMENT)
# ============================================================

VALIDATION_MAX_SPREAD = 2.0

# PM Bar Data Classification Thresholds (Soft Quality Tagging Only)
VALIDATION_MIN_PM_VOLUME_ABS = 100_000
VALIDATION_MIN_PM_BARS = 10

VALIDATION_MAX_PM_DIST = 5.0
VALIDATION_MIN_VWAP_DIST = 0.0

# RVOL & Catalyst are INFORMATIONAL ONLY during V2.14 (Soft Gates)
VALIDATION_MIN_RVOL = 0.0
VALIDATION_MIN_CATALYST_SCORE = 0


# ============================================================
# RISK & MONTE CARLO CONSTRAINTS
# ============================================================

MAX_ACTIVE_TRADES = 3
MAX_TRADES_PER_DAY = 5

MAX_DAILY_LOSS = 0.03
MAX_RISK_PER_TRADE = 0.01

MIN_NET_PROFIT_PCT = 1.5


# ============================================================
# EXPERIMENT FLAGS (SOFT GATES)
# ============================================================

EXPERIMENT_MODE_ACTIVE = True

USE_RVOL_AS_HARD_GATE = False
USE_CATALYST_AS_HARD_GATE = False
USE_PM_BARS_AS_HARD_GATE = False
