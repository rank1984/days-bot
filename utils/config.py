import os

# API KEYS & ENVIRONMENT VARIABLES
ALPACA_API_KEY = os.getenv("ALPACA_API_KEY", "")
ALPACA_SECRET_KEY = os.getenv("ALPACA_SECRET_KEY", "")
ALPACA_BASE_URL = os.getenv("ALPACA_BASE_URL", "https://api.alpaca.markets")

FINNHUB_API_KEY = os.getenv("FINNHUB_API_KEY", "")
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN", "")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "")

# DISCOVERY PARAMETERS
DISCOVERY_MIN_PRICE = 1.0
DISCOVERY_MAX_PRICE = 20.0
DISCOVERY_MIN_GAP = 8.0
DISCOVERY_MAX_GAP = 100.0

# VALIDATION PARAMETERS
VALIDATION_MAX_SPREAD = 1.5
VALIDATION_MIN_PM_VOLUME_ABS = 100_000
VALIDATION_MIN_PM_BARS = 10
VALIDATION_MAX_PM_DIST = 5.0
VALIDATION_MIN_VWAP_DIST = 0.0

# RVOL & CATALYST
VALIDATION_MIN_RVOL = 0.0
VALIDATION_MIN_CATALYST_SCORE = 3.0

# RISK & TRADING LIMITS
MAX_DAILY_LOSS = 0.05       # 5% max daily drawdown
MAX_ACTIVE_TRADES = 3
MAX_TRADES_PER_DAY = 5
MAX_RISK_PER_TRADE = 0.01   # 1% equity risk
MIN_NET_PROFIT_PCT = 0.01   # 1% minimum net target

# EXECUTION, FEE & BROKERAGE QUOTAS
FEE_PER_SHARE = 0.005       # Execution fee per share ($0.005)
FEE_PER_ORDER = 0.0         # Flat fee per order
FEE_MIN = 1.0               # Minimum total fee per order ($1.00)
FEE_MAX_PCT = 0.01          # Maximum fee cap (1.0% of trade value)
SLIPPAGE_PCT = 0.001        # Estimated slippage allowance (0.1%)

FREE_OPS_QUOTA = 0          # Monthly free operations quota
FREE_SHARES_QUOTA = 0       # Monthly free shares volume quota
