import os

# API Keys & Credentials
ALPACA_API_KEY = os.getenv("ALPACA_API_KEY", "")
ALPACA_SECRET_KEY = os.getenv("ALPACA_SECRET_KEY", "")
FINNHUB_API_KEY = os.getenv("FINNHUB_API_KEY", "")
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN", "")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "")

# Discovery & Validation Thresholds
DISCOVERY_MIN_PRICE = 1.0
DISCOVERY_MAX_PRICE = 20.0
DISCOVERY_MIN_GAP = 8.0
DISCOVERY_MAX_GAP = 100.0

VALIDATION_MAX_SPREAD = 1.5
VALIDATION_MIN_PM_VOLUME_ABS = 100_000
VALIDATION_MIN_PM_BARS = 10
VALIDATION_MAX_PM_DIST = 5.0
VALIDATION_MIN_VWAP_DIST = 0.0
VALIDATION_MIN_CATALYST_SCORE = 3.0

# Account Risk & Trade Limits
MAX_RISK_PER_TRADE = 0.01       # 1% risk per trade
MAX_DAILY_LOSS = 0.03           # 3% max daily account drawdown
MAX_TRADES_PER_DAY = 2
MAX_ACTIVE_TRADES = 2
MIN_NET_PROFIT_PCT = 0.04       # 4% minimum net return requirement

# BLINK Broker Fee Model & Conservative Buffers
FEE_PER_SHARE = 0.01            # $0.01 per share
FEE_MIN = 1.50                  # $1.50 minimum execution floor
FEE_MAX_PCT = 0.01              # 1% maximum cap of total trade value

FREE_OPS_QUOTA = 10             # 10 free operations per month
FREE_SHARES_QUOTA = 1000        # 1,000 free shares per month

FREE_OPS_BUFFER = 2             # Bot applies fee at 8 ops
FREE_SHARES_BUFFER = 200        # Bot applies fee at 800 shares

MANUAL_OPS_OFFSET = 0
MANUAL_SHARES_OFFSET = 0
