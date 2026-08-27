from datetime import datetime
import pytz
from scanner.pm_engine import get_premarket_minute_data
from utils.config import get_alpaca_api

ET = pytz.timezone('America/New_York')
now_et = datetime.now(ET)

print(f"Current ET Time: {now_et.strftime('%Y-%m-%d %H:%M:%S %Z')}")

api = get_alpaca_api()

# בדיקה 1: מניה נזילה ביותר
aapl_data = get_premarket_minute_data("AAPL", api)
print(f"[AAPL Test] bars_count={aapl_data['pm_bars_count']}, volume={aapl_data['pm_volume']}")

# בדיקה 2: מניית Micro-Cap
crmg_data = get_premarket_minute_data("CRMG", api)
print(f"[CRMG Test] bars_count={crmg_data['pm_bars_count']}, volume={crmg_data['pm_volume']}")
