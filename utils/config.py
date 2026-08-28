import os

# ============================================================
# BOT VERSION / EXPERIMENT
# ============================================================

BOT_VERSION = "V2.14"
RUN_MODE = "EXPERIMENT"


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
# DISCOVERY
# ============================================================

DISCOVERY_MIN_PRICE = 2.0
DISCOVERY_MAX_PRICE = 20.0

DISCOVERY_MIN_GAP = 8.0
DISCOVERY_MAX_GAP = 100.0


# ============================================================
# VALIDATION
# ============================================================

VALIDATION_MAX_SPREAD = 2.0

# RVOL is INFORMATIONAL ONLY during V2.14
VALIDATION_MIN_RVOL = 0.0

# Catalyst is INFORMATIONAL ONLY during V2.14
VALIDATION_MIN_CATALYST_SCORE = 0.0

# PM data
VALIDATION_MIN_PM_VOLUME_ABS = 100_000

# Hard minimum: at least one real PM bar
VALIDATION_MIN_PM_BARS = 1

# Quality threshold only — does NOT block candidate
PM_BARS_QUALITY_THRESHOLD = 10

VALIDATION_MAX_PM_DIST = 5.0
VALIDATION_MIN_VWAP_DIST = 0.0


# ============================================================
# RISK
# ============================================================

MAX_ACTIVE_TRADES = 3
MAX_TRADES_PER_DAY = 5

MAX_DAILY_LOSS = 0.03
MAX_RISK_PER_TRADE = 0.01

MIN_NET_PROFIT_PCT = 1.5


# ============================================================
# EXPERIMENT FLAGS
# ============================================================

EXPERIMENT_MODE = True

USE_RVOL_AS_HARD_GATE = False
USE_CATALYST_AS_HARD_GATE = False

USE_PM_BARS_AS_HARD_GATE = True
