"""
Premarket scanner – FAST version (no yfinance, no float, no PRE-RUNNER)
"""
import sys
import os
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

                    price = latest_trade.price
                    volume = latest_trade.size

                    daily_bar = snapshot.daily_bar
                    if not daily_bar:
                        stats['no_bar'] += 1
                        continue

                    prev_close = daily_bar.close
                    prev_volume = daily_bar.volume

                    # ---- Price filter ----
                    if price < MIN_PRICE or price > MAX_PRICE:
                        continue
                    stats['price_passed'] += 1

                    # ---- Gap ----
                    gap_pct = ((price - prev_close) / prev_close) * 100 if prev_close else 0
                    if gap_pct < MIN_GAP_PCT or gap_pct > MAX_GAP_PCT:
                        continue
                    stats['gap_passed'] += 1

                    # ---- Volume filter (lowered) ----
                    if prev_volume < MIN_AVG_VOLUME:
                        continue
                    stats['volume_passed'] += 1

                    # ---- Simple RVOL (fallback) ----
                    rvol = volume / prev_volume if prev_volume > 0 else 1.0

                    # ---- Basic candidate (no float, no PRE-RUNNER) ----
                    candidate = {
                        'ticker': symbol,
                        'price': price,
                        'gap_pct': gap_pct,
                        'prev_close': prev_close,
                        'volume': volume,
                        'avg_volume': prev_volume,
                        'rvol': rvol,
                        'rvol_method': 'DAILY_FALLBACK',
                        'float_shares': None,
                        'float_turnover': None,
                        'spread_pct': 0,
                        'pm_high': daily_bar.high if hasattr(daily_bar, 'high') else price,
                        'pm_high_dist': 0,
                        'catalyst': '—',
                        'catalyst_type': 'UNKNOWN',
                        'catalyst_score': 0,
                        'dilution_risk': 'LOW',
                        'dollar_volume': price * volume,
                    }

                    # ---- Event Score (simple, based only on gap and rvol) ----
                    # RVOL score
                    if rvol >= 20: rvol_score = 30
                    elif rvol >= 10: rvol_score = 20
                    elif rvol >= 5: rvol_score = 10
                    elif rvol >= 2: rvol_score = 5
                    else: rvol_score = 0

                    # Gap score (diminishing after 20%)
                    if gap_pct < 1: gap_score = 0
                    elif gap_pct < 3: gap_score = 5
                    elif gap_pct < 5: gap_score = 8
                    elif gap_pct < 10: gap_score = 12
                    elif gap_pct < 20: gap_score = 15
                    elif gap_pct < 30: gap_score = 10
                    else: gap_score = 5

                    event_score = rvol_score + gap_score
                    event_score = min(100, max(0, event_score))

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

                    # ---- State ----
                    if gap_pct >= 30:
                        state = "EXTENDED"
                    elif event_score >= 70 and rvol >= 10:
                        state = "PREPARE"
                    elif event_score >= 50:
                        state = "WATCH"
                    elif event_score >= 30:
                        state = "EARLY"
                    else:
                        state = "REJECT"

                    candidate.update({
                        'event_score': event_score,
                        'grade': grade,
                        'state': state,
                        'score': event_score,  # for compatibility
                    })

                    candidates.append(candidate)
                    stats['final_passed'] += 1

                except Exception as e:
                    continue

            print(f"[Premarket] Processed {min(i+batch_size, len(universe))}/{len(universe)}")

        except Exception as e:
            print(f"[Premarket] Batch error: {e}")
            continue

    # ---- Stats ----
    print("\n" + "="*50)
    print("📊 PREMARKET SCAN STATISTICS (FAST)")
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
