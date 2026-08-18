import logging
from typing import Dict, Any, List, Optional
from datetime import datetime
import yfinance as yf

# Try importing load_universe from local universe engine if available
try:
    from scanner.universe import load_universe
except ImportError:
    try:
        from universe import load_universe
    except ImportError:
        load_universe = None

logger = logging.getLogger(__name__)


def get_previous_day_data(symbol: str) -> dict:
    """
    Fetches previous day's data (close, volume, gain, estimated rvol).
    Safe against exceptions to prevent scanner crashes.
    """
    try:
        ticker = yf.Ticker(symbol)
        hist = ticker.history(period="3d")
        if len(hist) < 2:
            return {}

        yesterday = hist.iloc[-2]
        prev_close = float(yesterday['Close'])
        prev_volume = float(yesterday['Volume'])
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
        logger.debug(f"Failed to fetch previous day data for {symbol}: {e}")
        return {}


def scan_premarket_symbol(symbol: str, raw_data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """
    Evaluates a single stock symbol against V2.3 Premarket / PRE-RUNNER criteria.
    """
    try:
        current_price = float(raw_data.get('price', 0.0))
        prev_close_today = float(raw_data.get('prev_close', 0.0))
        volume = int(raw_data.get('volume', 0))
        rvol = float(raw_data.get('rvol', 0.0))
        pm_high = float(raw_data.get('pm_high', current_price))
        float_shares = raw_data.get('float_shares', None)
        spread_pct = float(raw_data.get('spread_pct', 0.0))
        catalyst_score = int(raw_data.get('catalyst_score', 0))

        if current_price <= 0 or prev_close_today <= 0:
            return None

        gap_pct = ((current_price - prev_close_today) / prev_close_today) * 100.0
        pm_high_dist = ((pm_high - current_price) / current_price) * 100.0 if current_price > 0 else 0.0

        # Previous Day Data Integration
        prev_data = get_previous_day_data(symbol)
        prev_gain = prev_data.get('prev_gain', 0.0)
        prev_rvol = prev_data.get('prev_rvol', 0.0)
        prev_volume = prev_data.get('prev_volume', 0.0)

        volume_building = volume > (prev_volume * 1.2) if prev_volume > 0 else False

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

        # V2.3 State Determination Rules
        is_prerunner = (
            prev_gain >= 8.0 and
            prev_rvol >= 3.0 and
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
        return candidate if state != "REJECT" else None

    except Exception as e:
        logger.error(f"Error scanning symbol {symbol}: {e}")
        return None


def scan_premarket(symbols_data: Any = None) -> List[Dict[str, Any]]:
    """
    Main scanner engine wrapper. Loads universe if not provided, scans, and prints debug stats at the END.
    """
    date_str = datetime.now().strftime("%Y-%m-%d")
    print(f"[Premarket] Scanning for {date_str}...")

    # Step 1: Ensure Universe Data is loaded FIRST
    universe_dict = {}
    if symbols_data is None and load_universe is not None:
        try:
            loaded = load_universe()
            if isinstance(loaded, list):
                universe_dict = {sym: {} for sym in loaded}
            elif isinstance(loaded, dict):
                universe_dict = loaded
        except Exception as e:
            logger.error(f"Failed to load universe: {e}")

    elif isinstance(symbols_data, dict):
        universe_dict = symbols_data
    elif isinstance(symbols_data, list):
        for item in symbols_data:
            if isinstance(item, str):
                universe_dict[item] = {}
            elif isinstance(item, dict) and 'symbol' in item:
                universe_dict[item['symbol']] = item

    if not universe_dict:
        print("[Premarket] ❌ No universe loaded or empty dataset.")

    # Step 2: Initialize Statistics Counters
    stats = {
        'total': len(universe_dict),
        'no_snapshot': 0,
        'no_trade': 0,
        'no_bar': 0,
        'price_passed': 0,
        'gap_passed': 0,
        'volume_passed': 0,
        'final_passed': 0
    }

    candidates = []

    # Step 3: Run Scan Loop over the populated Universe
    for symbol, raw_data in universe_dict.items():
        if not raw_data:
            stats['no_snapshot'] += 1
            # Fallback evaluation with minimal structure if snapshot missing
            raw_data = {'price': 0.0, 'gap_pct': 0.0, 'volume': 0}

        price = float(raw_data.get('price', 0.0))
        gap_pct = float(raw_data.get('gap_pct', 0.0))
        volume = int(raw_data.get('volume', 0))

        if price > 0:
            stats['price_passed'] += 1
        else:
            stats['no_trade'] += 1

        if abs(gap_pct) >= 1.0:
            stats['gap_passed'] += 1

        if volume >= 0:
            stats['volume_passed'] += 1

        cand = scan_premarket_symbol(symbol, raw_data)
        if cand:
            candidates.append(cand)
            stats['final_passed'] += 1

    # Step 4: Print Statistics ONLY AFTER processing completes
    print("\n" + "=" * 50)
    print("📊 PREMARKET SCAN STATISTICS")
    print("=" * 50)
    print(f"Total Universe:        {stats['total']:,}")
    print(f"No Snapshot:           {stats['no_snapshot']:,}")
    print(f"No Trade/Price:        {stats['no_trade']:,}")
    print(f"No Daily Bar:          {stats['no_bar']:,}")
    print("-" * 50)
    print(f"✅ Price Passed:        {stats['price_passed']:,}")
    print(f"✅ Gap Passed:          {stats['gap_passed']:,}")
    print(f"✅ Volume Passed:       {stats['volume_passed']:,}")
    print(f"✅ Final Passed:        {stats['final_passed']:,}")
    print("=" * 50 + "\n")

    return candidates
