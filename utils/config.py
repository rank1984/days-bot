"""
DAYS-BOT V4.1 Configuration

Recommendation-only trading research engine.
NO automatic order execution.
"""

import os


# ============================================================
# VERSION
# ============================================================

BOT_VERSION = "V4.1"

STRATEGY_VERSION = "V4.1"

EXPERIMENT_MODE = "V4.1_LIVE_RESEARCH"

DATA_VERSION = "ALPACA_IEX_V41"


# ============================================================
# API KEYS
# ============================================================

ALPACA_API_KEY = os.getenv(
    "ALPACA_API_KEY",
    ""
)

ALPACA_SECRET_KEY = os.getenv(
    "ALPACA_SECRET_KEY",
    ""
)

# ------------------------------------------------------------
# IMPORTANT:
# This is MARKET DATA only.
# We are NOT using this URL for order execution.
# ------------------------------------------------------------

ALPACA_DATA_URL = os.getenv(
    "ALPACA_DATA_URL",
    "https://data.alpaca.markets"
)

# Keep compatibility with existing project code.
ALPACA_BASE_URL = os.getenv(
    "ALPACA_BASE_URL",
    "https://paper-api.alpaca.markets"
)


FINNHUB_API_KEY = os.getenv(
    "FINNHUB_API_KEY",
    ""
)

TELEGRAM_TOKEN = os.getenv(
    "TELEGRAM_TOKEN",
    ""
)

TELEGRAM_CHAT_ID = os.getenv(
    "TELEGRAM_CHAT_ID",
    ""
)

GEMINI_API_KEY = os.getenv(
    "GEMINI_API_KEY",
    ""
)


# ============================================================
# DISCOVERY
# ============================================================

DISCOVERY_MIN_PRICE = 1.00

DISCOVERY_MAX_PRICE = 30.00

# Lower than old hard 10% gate.
# Discovery should FIND candidates.
DISCOVERY_MIN_GAP = 3.0

DISCOVERY_MAX_GAP = 100.0

# Daily volume used only for initial liquidity.
DISCOVERY_MIN_VOLUME = 50_000


# ============================================================
# PREMARKET
# ============================================================

PM_START_HOUR = 4

PM_START_MINUTE = 0

PM_END_HOUR = 9

PM_END_MINUTE = 30

PM_CANDIDATE_LIMIT = 40


# ============================================================
# VALIDATION
# ============================================================

VALIDATION_MAX_SPREAD = 2.0

VALIDATION_MIN_PM_VOLUME_ABS = 100_000

VALIDATION_MIN_PM_BARS = 5

VALIDATION_MAX_PM_DIST = 5.0

VALIDATION_MIN_VWAP_DIST = 0.0


# ============================================================
# RVOL
# ============================================================

VALIDATION_MIN_RVOL = 0.0

VALIDATION_MIN_CATALYST_SCORE = 0


# ============================================================
# SOFT/HARD GATES
# ============================================================

EXPERIMENT_MODE_ACTIVE = True

USE_RVOL_AS_HARD_GATE = False

USE_CATALYST_AS_HARD_GATE = False

USE_PM_BARS_AS_HARD_GATE = False

USE_FLOAT_AS_HARD_GATE = False

USE_PERSONALITY_AS_HARD_GATE = False


# ============================================================
# RESEARCH
# ============================================================

LEARNING_MODE = True

TOP_RESEARCH_CANDIDATES = 5

MAX_ANALYSIS_CANDIDATES = 25


# ============================================================
# ACCOUNT
# ============================================================

ACCOUNT_SIZE = 5000.0

# 0.5%
MAX_RISK_PER_TRADE_V31 = 0.005

MAX_POSITION_VALUE_PCT = 0.20


# ============================================================
# RISK
# ============================================================

MAX_ACTIVE_TRADES = 3

MAX_TRADES_PER_DAY = 5

MAX_DAILY_LOSS = 0.03

MAX_RISK_PER_TRADE = 0.01

MIN_NET_PROFIT_PCT = 1.5


# ============================================================
# BLINK / COST MODEL
# ============================================================

# Configurable because broker pricing can change.
BLINK_FEE_PER_SHARE = 0.01

BLINK_MIN_FEE = 1.50

BLINK_MAX_FEE_PCT = 0.018


# General Israeli individual capital-gains
# assumption used only as a configurable model input.
# It is NOT applied blindly to every gross trade.
CAPITAL_GAINS_TAX_RATE = 0.25


# Estimated slippage used for research calculations.
SLIPPAGE_PCT = 0.15


# ============================================================
# MARKET REGIME
# ============================================================

REGIME_FAVORABLE = 1.00

REGIME_NEUTRAL = 0.75

REGIME_HOSTILE = 0.50


# ============================================================
# DATA QUALITY
# ============================================================

DATA_QUALITY_GOOD = 1.00

DATA_QUALITY_PARTIAL = 0.85

DATA_QUALITY_UNKNOWN = 0.70


# ============================================================
# EXECUTION POLICY
# ============================================================

# Absolutely no automatic/live order execution.
AUTO_EXECUTION = False

PAPER_TRADING_ONLY = True

MANUAL_EXECUTION_REQUIRED = True