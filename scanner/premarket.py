"""
Premarket scanner – V2.5 (Spread BLOCK, PM High Dist, PRE-RUNNER)
"""
import sys
from pathlib import Path
from datetime import datetime
from typing import List, Dict, Any

BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))
sys.path.insert(0, str(BASE_DIR / "utils"))

import alpaca_trade_api as tradeapi
from utils.config import *
from scanner.universe import load_universe


def scan_premarket(date: str = None) -> List[Dict[str, Any]]:
    if date is None:
        date = datetime.now().strftime("%Y-%m-%d")

    print(f"[Premarket] Scanning for {date}...")

    universe = load_universe()
    if not universe:
        print("[Premarket] ❌ No universe loaded.")
        return []

    print(f"[Premarket] Universe size: {len(universe)}")

    api = tradeapi.REST(
        ALPACA_API_KEY,
        ALPACA_SECRET_KEY,
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

    batch_size = 100
    for i in range(0, len(universe), batch_size):
        batch = universe[i:i+batch_size]
        symbols = [str(s['symbol']) for s in batch]

        try:
            snapshots = api.get_snapshots(symbols)

            for symbol in symbols:
                try:
                    snapshot = snapshots.get(symbol)
                    if not snapshot:
                        stats['no_snapshot'] += 1
                        continue

                    latest_trade = snapshot.latest_trade
                    if not latest_trade:
                        stats['no_trade'] += 1
                        continue

                    daily_bar = snapshot.daily_bar
                    if not daily_bar:
                        stats['no_bar'] += 1
                        continue

                    price = float(latest_trade.price)
                    prev_close = float(daily_bar.close)

                    # ---- REAL DAILY VOLUME ----
                    today_volume = int(getattr(daily_bar, 'volume', 0) or 0)

                    # ---- Previous day ----
                    prev_daily_bar = getattr(snapshot, 'prev_daily_bar', None)
                    prev_volume = 0
                    prev_day_return = 0.0
                    prev_day_volume = 0
                    if prev_daily_bar:
                        prev_open = float(getattr(prev_daily_bar, 'open', 0) or 0)
                        prev_close_price = float(getattr(prev_daily_bar, 'close', 0) or 0)
                        prev_volume = int(getattr(prev_daily_bar, 'volume', 0) or 0)
                        prev_day_volume = prev_volume
                        if prev_open > 0:
                            prev_day_return = ((prev_close_price - prev_open) / prev_open) * 100

                    if prev_volume <= 0:
                        prev_volume = int(getattr(daily_bar, 'volume', 0) or 0)

                    if today_volume <= 0:
                        stats['no_bar'] += 1
                        continue

                    # ---- Price ----
                    if price < MIN_PRICE or price > MAX_PRICE:
                        continue
                    stats['price_passed'] += 1

                    # ---- Gap ----
                    gap_pct = ((price - prev_close) / prev_close) * 100 if prev_close else 0
                    if gap_pct < MIN_GAP_PCT or gap_pct > MAX_GAP_PCT:
                        continue
                    stats['gap_passed'] += 1

                    # ---- Volume ----
                    if prev_volume < MIN_AVG_VOLUME:
                        continue
                    stats['volume_passed'] += 1

                    # ---- RVOL ----
                    rvol = today_volume / prev_volume if prev_volume > 0 else 0.0
                    rvol_method = "DAILY_FALLBACK"

                    # ---- PRE-RUNNER ----
                    building = (
                        prev_day_return >= PRE_RUNNER_MIN_GAIN
                        and prev_day_volume >= PRE_RUNNER_MIN_VOLUME
                        and gap_pct < PRE_RUNNER_MAX_GAP
                    )
                    building_state = "PRE-RUNNER" if building else "—"

                    # ---- PM High Distance ----
                    pm_high = float(getattr(daily_bar, 'high', price))
                    pm_high_dist = ((pm_high - price) / pm_high) * 100 if pm_high > 0 else 999.0

                    # ---- Spread – BLOCK if unknown ----
                    bid = getattr(snapshot, 'bid_price', None)
                    ask = getattr(snapshot, 'ask_price', None)
                    if bid and ask and price > 0:
                        spread_pct = ((ask - bid) / price) * 100
                    else:
                        spread_pct = None  # UNKNOWN → BLOCK

                    # ---- Event Score ----
                    if rvol >= 100: rvol_score = 20
                    elif rvol >= 50: rvol_score = 18
                    elif rvol >= 20: rvol_score = 15
                    elif rvol >= 10: rvol_score = 12
                    elif rvol >= 5: rvol_score = 8
                    elif rvol >= 3: rvol_score = 5
                    else: rvol_score = 0

                    if gap_pct < 1: gap_score = 0
                    elif gap_pct < 3: gap_score = 5
                    elif gap_pct < 5: gap_score = 8
                    elif gap_pct < 10: gap_score = 12
                    elif gap_pct < 20: gap_score = 15
                    elif gap_pct < 30: gap_score = 10
                    else: gap_score = 5

                    event_score = rvol_score + gap_score
                    event_score = min(100, max(0, event_score))

                    # ---- State ----
                    if gap_pct >= 30:
                        state = "EXTENDED"
                    elif prev_day_return >= 25:
                        state = "EXTENDED"
                    elif building:
                        state = "PRE-RUNNER"
                    elif gap_pct >= 6 and rvol >= 4:
                        state = "EARLY"
                    elif event_score >= 60:
                        state = "WATCH"
                    else:
                        state = "REJECT"

                    # ---- Grade ----
                    if event_score >= 75 and rvol >= 10:
                        grade = "A"
                    elif event_score >= 60:
                        grade = "B"
                    elif event_score >= 45:
                        grade = "C"
                    elif event_score >= 30:
                        grade = "WATCH"
                    else:
                        grade = "REJECT"

                    # ---- Candidate ----
                    candidate = {
                        'ticker': symbol,
                        'price': price,
                        'gap_pct': gap_pct,
                        'prev_close': prev_close,
                        'volume': today_volume,
                        'avg_volume': prev_volume,
                        'today_volume': today_volume,
                        'rvol': rvol,
                        'rvol_method': rvol_method,
                        'prev_day_return': prev_day_return,
                        'prev_day_volume': prev_day_volume,
                        'building': building,
                        'building_state': building_state,
                        'pm_high': pm_high,
                        'pm_high_dist': pm_high_dist,
                        'spread_pct': spread_pct,
                        'float_shares': None,
                        'catalyst': '—',
                        'catalyst_type': 'UNKNOWN',
                        'dilution_risk': 'LOW',
                        'dollar_volume': price * today_volume,
                        'event_score': event_score,
                        'grade': grade,
                        'state': state,
                        'score': event_score,
                    }

                    candidates.append(candidate)
                    stats['final_passed'] += 1

                except Exception as e:
                    continue

            print(f"[Premarket] Processed {min(i+batch_size, len(universe))}/{len(universe)}")

        except Exception as e:
            print(f"[Premarket] Batch error: {e}")
            continue

    print("\n" + "="*50)
    print("📊 PREMARKET SCAN STATISTICS (V2.5)")
    print("="*50)
    print(f"Total Universe:        {stats['total']:,}")
    print(f"No Snapshot:           {stats['no_snapshot']:,}")
    print(f"No Trade:              {stats['no_trade']:,}")
    print(f"No Daily Bar:          {stats['no_bar']:,}")
    print("-"*50)
    print(f"✅ Price Passed:        {stats['price_passed']:,}")
    print(f"✅ Gap Passed:          {stats['gap_passed']:,}")
    print(f"✅ Volume Passed:       {stats['volume_passed']:,}")
    print(f"🎯 FINAL CANDIDATES:    {stats['final_passed']:,}")
    print("="*50 + "\n")

    candidates.sort(key=lambda x: x.get('event_score', 0), reverse=True)
    return candidates[:10]
