import os

ALPACA_API_KEY    = os.getenv("ALPACA_API_KEY")
ALPACA_SECRET_KEY = os.getenv("ALPACA_SECRET_KEY")

POLYGON_API_KEY   = os.getenv("POLYGON_API_KEY")
FMP_API_KEY       = os.getenv("FMP_API_KEY")
FINNHUB_API_KEY   = os.getenv("FINNHUB_API_KEY")

TELEGRAM_TOKEN    = os.getenv("TELEGRAM_TOKEN")
TELEGRAM_CHAT_ID  = os.getenv("TELEGRAM_CHAT_ID")

# סינון universe
MIN_PRICE         = 1.0
MAX_PRICE         = 20.0
MAX_MARKET_CAP    = 2_000_000_000   # 2B
MIN_AVG_VOLUME    = 500_000         # חובה — מונע slippage

# סינון premarket
MIN_GAP_PCT       = 5.0
MIN_PREMARKET_VOL = 50_000
MIN_RVOL          = 1.5             # נפח יחסי מינימום

# ציון מינימום לשליחה
MIN_SCORE         = 60
