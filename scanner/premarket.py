import logging
from typing import Dict, Any, List, Optional
import yfinance as yf

logger = logging.getLogger(__name__)


def get_previous_day_data(symbol: str) -> dict:
    """
    Fetches the previous day's metrics: close price, volume, RVOL, and gain percentage.
    """
    try:
        ticker = yf.Ticker(symbol)
        # Fetch last 3 days to correctly calculate yesterday's gain relative to day-before-yesterday
        hist = ticker.history(period="3d")
        if len(hist) < 2:
            return {}

        yesterday = hist.iloc[-2]
        prev_close = float(yesterday['Close'])
        prev_volume = float(yesterday['Volume'])

        # Rough RVOL estimation against a standard baseline volume (100k)
        prev_rvol = prev_volume / 100_000.0 if prev_volume > 0 else 0.0

        if len(hist) >= 3:
            day_before = hist.iloc[-3]
            day_before_close = float(day_before['Close'])
            prev_gain = ((prev_close - day_before_close) / day_before_close) * 100.0 if day_before_close > 0 else 0.0
        else:
            prev_gain = 0.0

        return {
            'prev_close': prev_close,
            'prev_volume': prev_volume,
            'prev_rvol': prev_rvol,
            'prev_gain': prev_gain,
        }
    except Exception as e:
        logger.warning(f"Failed to fetch previous day data for {symbol}: {e}")
        return {}


def scan_premarket_symbol(symbol: str, raw_data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """
    Evaluates a single symbol during Premarket using today's data combined with Previous Day momentum.
    """
    try:
        # Extract current premarket metrics
        current_price = raw_data.get('price', 0.0)
        prev_close_today = raw_data.get('prev_close', 0.0)
        volume = raw_data.get('volume', 0)
        rvol = raw_data.get('rvol', 0.0)
        pm_high = raw_data.get('pm_high', current_price)
        float_shares = raw_data.get('float_shares', None)
        spread_pct = raw_data.get('spread_pct', 0.0)
        catalyst_score = raw_data.get('catalyst_score', 0)

        if current_price <= 0 or prev_close_today <= 0:
            return None

        # Calculate today's gap and distance from Premarket High
        gap_pct = ((current_price - prev_close_today) / prev_close_today) * 100.0
        pm_high_dist = ((pm_high - current_price) / current_price) * 100.0 if current_price > 0 else 0.0

        # Fetch Previous Day Data for PRE-RUNNER logic
        prev_data = get_previous_day_data(symbol)
        prev_gain = prev_data.get('prev_gain', 0.0)
        prev_rvol = prev_data.get('prev_rvol', 0.0)
        prev_volume = prev_data.get('prev_volume', 0.0)

        # Check volume building pattern relative to yesterday's entire volume
        volume_building = volume > (prev_volume * 1.2) if prev_volume > 0 else False

        # Assemble unified payload for scoring and state determination
        candidate = {
            'symbol': symbol,
            'price': current_price,
            'gap_pct': gap_pct,
            'rvol': rvol,
            'volume': volume,
            'pm_high': pm_high,
            'pm_high_dist': pm_high_dist,
            'float_shares': float_shares,
            'spread_pct': spread_pct,
            'catalyst_score': catalyst_score,
            'prev_gain': prev_gain,
            'prev_rvol': prev_rvol,
            'prev_volume': prev_volume,
            'volume_building': volume_building
        }

        # Determine System State strictly following V2.3 rules
        is_prerunner = (
            prev_gain >= 8.0 and
            prev_rvol >= 3.0 and
            prev_volume >= (prev_volume * 1.5) and  # Historical volume expansion check
            gap_pct < 20.0 and
            pm_high_dist <= 5.0 and
            (float_shares is None or float_shares < 50_000_000)
        )

        if is_prerunner:
            state = "PRE-RUNNER"
        elif gap_pct >= 30.0 and pm_high_dist > 2.0:
            state = "EXTENDED"
        elif rvol >= 10.0 and pm_high_dist <= 2.0:
            state = "PREPARE"
        elif rvol >= 5.0:
            state = "WATCH"
        elif gap_pct >= 3.0:
            state = "EARLY"
        else:
            state = "REJECT"

        candidate['state'] = state
        return candidate

    except Exception as e:
        logger.error(f"Error scanning premarket for symbol {symbol}: {e}")
        return None


def scan_premarket(symbols_data: Dict[str, Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    Main scanner function imported by main.py.
    Processes a dictionary of symbols and returns a list of evaluated candidates.
    """
    results = []
    if isinstance(symbols_data, list):
        # Support for list of symbol strings or candidate dicts
        for item in symbols_data:
            if isinstance(item, str):
                res = scan_premarket_symbol(item, {})
                if res:
                    results.append(res)
            elif isinstance(item, dict) and 'symbol' in item:
                res = scan_premarket_symbol(item['symbol'], item)
                if res:
                    results.append(res)
    elif isinstance(symbols_data, dict):
        for symbol, raw_data in symbols_data.items():
            res = scan_premarket_symbol(symbol, raw_data)
            if res:
                results.append(res)

    return results
