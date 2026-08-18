import os
import logging
from typing import Dict, Any, List, Optional
from datetime import datetime
import yfinance as yf
import alpaca_trade_api as tradeapi

# Import load_universe from local module
try:
    from scanner.universe import load_universe
except ImportError:
    try:
        from universe import load_universe
    except ImportError:
        load_universe = None

logger = logging.getLogger(__name__)

# Config Defaults / Fallbacks (Relaxed for small-cap & off-hours trading)
ALPACA_API_KEY = os.getenv('ALPACA_API_KEY', '')
ALPACA_SECRET_KEY = os.getenv('ALPACA_SECRET_KEY', '')
MIN_PRICE = float(os.getenv('MIN_PRICE', 0.1))
MAX_PRICE = float(os.getenv('MAX_PRICE', 50.0))
MIN_GAP_PCT = float(os.getenv('MIN_GAP_PCT', -5.0))
MAX_GAP_PCT = float(os.getenv('MAX_GAP_PCT', 100.0))
MIN_AVG_VOLUME = int(os.getenv('MIN_AVG_VOLUME', 5_000))


def get_previous_day_data(symbol: str) -> dict:
    """
    Fetches previous day's metrics using yfinance.
    Provides robust fallbacks when Alpaca daily bars lack volume data.
    """
    try:
        ticker = yf.Ticker(symbol)
        hist = ticker.history(period="5d")
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


def scan_premarket(date: str = None) -> List[Dict[str, Any]]:
    """
    Main Premarket Engine V2.3 (Robust Volume & Gap Handling)
    """
    if date is None:
        date = datetime.now().strftime("%Y-%m-%d")

    print(f"[Premarket] Scanning for {date}...")

    # ====== 1. Load Universe ======
    if load_universe is None:
        print("[Premarket] ❌ load_universe function not available.")
        return []

    universe = load_universe()
    if not universe:
        print("[Premarket] ❌ No universe loaded or empty dataset.")
        return []

    print(f"[Premarket] Universe size: {len(universe)}")

    # ====== 2. Initialize Alpaca API & Statistics ======
    api = tradeapi.REST(
        key_id=ALPACA_API_KEY,
        secret_key=ALPACA_SECRET_KEY,
        base_url='https://paper-api.alpaca.markets'
    )

    candidates = []
    stats = {
        'total': len(universe),
        'no_snapshot': 0,
        'no_trade': 0,
        'no_bar': 0,
        'price_passed': 0,
        'gap_passed': 0,
        'volume_passed': 0,
        'final_passed': 0,
    }

    # Extract ticker strings
    if isinstance(universe, list):
        if len(universe) > 0 and isinstance(universe[0], dict):
            symbol_list = [str(item.get('symbol', '')) for item in universe if item.get('symbol')]
        else:
            symbol_list = [str(item) for item in universe]
    else:
        symbol_list = list(universe.keys())

    batch_size = 100

    # ====== 3. Process Batches ======
    for i in range(0, len(symbol_list), batch_size):
        batch_symbols = symbol_list[i:i + batch_size]

        try:
            snapshots = api.get_snapshots(batch_symbols)
        except Exception as e:
            print(f"[Premarket] Batch snapshot error for index {i}: {e}")
            continue

        for symbol in batch_symbols:
            try:
                snapshot = snapshots.get(symbol)
                if not snapshot:
                    stats['no_snapshot'] += 1
                    continue

                latest_trade = getattr(snapshot, 'latest_trade', None)
                if not latest_trade:
                    stats['no_trade'] += 1
                    continue

                price = float(latest_trade.price)
                volume = int(getattr(latest_trade, 'size', 0))

                daily_bar = getattr(snapshot, 'daily_bar', None)
                if not daily_bar:
                    stats['no_bar'] += 1
                    continue

                prev_close = float(daily_bar.close)
                alpaca_prev_volume = float(getattr(daily_bar, 'volume', 0))

                # ---- Price Filter ----
                if price < MIN_PRICE or price > MAX_PRICE:
                    continue
                stats['price_passed'] += 1

                # ---- Gap Filter ----
                gap_pct = ((price - prev_close) / prev_close) * 100.0 if prev_close > 0 else 0.0
                if gap_pct < MIN_GAP_PCT or gap_pct > MAX_GAP_PCT:
                    continue
                stats['gap_passed'] += 1

                # ---- Get Fallback Data from yfinance if needed ----
                prev_data = get_previous_day_data(symbol)
                yf_prev_volume = prev_data.get('prev_volume', 0.0)

                # Use Alpaca volume if available, otherwise fall back to yfinance volume
                eval_volume = alpaca_prev_volume if alpaca_prev_volume > 0 else yf_prev_volume

                # ---- Volume Filter ----
                if eval_volume < MIN_AVG_VOLUME:
                    continue
                stats['volume_passed'] += 1

                # ---- Momentum & PRE-RUNNER Logic ----
                prev_gain = prev_data.get('prev_gain', 0.0)
                prev_rvol = prev_data.get('prev_rvol', 0.0)

                pm_high = float(getattr(daily_bar, 'high', price))
                pm_high_dist = ((pm_high - price) / price) * 100.0 if price > 0 else 0.0
                rvol = volume / eval_volume if eval_volume > 0 else 0.0
                volume_building = volume > (eval_volume * 1.2) if eval_volume > 0 else False

                # V2.3 State Determination
                is_prerunner = (
                    prev_gain >= 8.0 and
                    prev_rvol >= 3.0 and
                    gap_pct < 20.0 and
                    pm_high_dist <= 5.0
                )

                if is_prerunner:
                    state = "PRE-RUNNER"
                elif gap_pct >= 30.0 and pm_high_dist > 2.0:
                    state = "EXTENDED"
                elif rvol >= 10.0 and pm_high_dist <= 2.0:
                    state = "PREPARE"
                elif rvol >= 5.0:
                    state = "WATCH"
                elif gap_pct >= -5.0:
                    state = "EARLY"
                else:
                    state = "REJECT"

                if state == "REJECT":
                    continue

                candidate = {
                    'symbol': symbol,
                    'ticker': symbol,
                    'price': price,
                    'gap_pct': gap_pct,
                    'prev_close': prev_close,
                    'volume': volume,
                    'avg_volume': eval_volume,
                    'rvol': rvol,
                    'rvol_method': 'HYBRID_ALPACA_YFINANCE',
                    'float_shares': None,
                    'spread_pct': 0.0,
                    'pm_high': pm_high,
                    'pm_high_dist': pm_high_dist,
                    'catalyst': '—',
                    'catalyst_score': 0,
                    'prev_gain': prev_gain,
                    'prev_rvol': prev_rvol,
                    'prev_volume': eval_volume,
                    'volume_building': volume_building,
                    'event_score': 50,
                    'grade': state,
                    'state': state,
                    'dollar_volume': price * volume,
                }

                candidates.append(candidate)
                stats['final_passed'] += 1

            except Exception as e:
                logger.debug(f"Error processing symbol {symbol}: {e}")
                continue

        processed_count = min(i + batch_size, len(symbol_list))
        print(f"[Premarket] Processed {processed_count}/{len(symbol_list)}")

    # ====== 4. Statistics Output ======
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

    candidates.sort(key=lambda x: x.get('event_score', 0), reverse=True)
    return candidates[:10]
