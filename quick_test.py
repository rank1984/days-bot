import os
import pytz
from datetime import datetime
import alpaca_trade_api as tradeapi

from scanner.pm_engine import get_premarket_minute_data
from utils.config import ALPACA_API_KEY, ALPACA_SECRET_KEY

ALPACA_BASE_URL = os.getenv("ALPACA_BASE_URL", "https://paper-api.alpaca.markets")
api = tradeapi.REST(ALPACA_API_KEY, ALPACA_SECRET_KEY, ALPACA_BASE_URL, api_version='v2')

ET = pytz.timezone('America/New_York')
print(f"=== QUICK IEX TEST | ET: {datetime.now(ET).strftime('%Y-%m-%d %H:%M:%S')} ===")

for ticker in ["AAPL", "SPY", "CRMG"]:
    res = get_premarket_minute_data(ticker, api)
    print(f"[{ticker}] bars_count={res.get('pm_bars_count')}, volume={res.get('pm_volume')}, error={res.get('error')}")
