"""
Premarket scanner – V2.8 (Fixed)
Stages:
1. Fast Filter (Alpaca snapshot)
2. PM Quant (minute bars)
3. Catalyst & Risk (top 50 only)
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
from scanner.pm_engine import get_premarket_minute_data
from scanner.catalyst_engine import get_catalyst_from_finnhub


# ── Fallback thresholds if not defined in config ──────────
if not hasattr(sys.modules['__main__'], 'DISCOVERY_MIN_PRICE'):
    DISCOVERY_MIN_PRICE = 1.0
    DISCOVERY_MAX_PRICE = 50.0
    DISCOVERY_MIN_GAP = 3.0
    DISCOVERY_MAX_GAP = 25.0
    MIN_AVG_VOLUME = 50_000
    MAX_READY_SPREAD = 1.5

if not hasattr(sys.modules['__main__'], 'VALIDATION_MIN_RVOL'):
    VALIDATION_MIN_RVOL = 2.0
    VALIDATION_MAX_PM_DIST = 2.0
    VALIDATION_MIN_VWAP_DIST = 0.01
    VALIDATION_MIN_CATALYST_SCORE = 0   # 0 = pass, negative = reject


def scan_premarket(date: str = None) -> List[Dict[str, Any]]:
    if date is None:
        date = datetime.now().strftime("%Y-%m-%d")

    print(f"[Premarket] V2.8 Scan for {date}...")

    universe = load_universe()
    if not universe:
        print("[Premarket] ❌ No universe.")
        return []

    print(f"[Premarket] Universe: {len(universe)}")

    api = tradeapi.REST(ALPACA_API_KEY, ALPACA_SECRET_KEY, base_url='https://paper-api.alpaca.markets')

    # ============================================================
    # STAGE 1 – FAST FILTER (Alpaca Snapshot)
    # ============================================================
    filters = {
        'total': len(universe),
        'no_snapshot': 0,
        'no_trade': 0,
        'no_bar': 0,
        'price_pass': 0,
        'gap_pass': 0,
        'vol_pass': 0,
        'spread_pass': 0,
        'fast_pass': 0,
    }
    fast_candidates = []

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
                        filters['no_snapshot'] += 1
                        continue
                    latest_trade = snapshot.latest_trade
                    if not latest_trade:
                        filters['no_trade'] += 1
                        continue
                    daily_bar = snapshot.daily_bar
                    if not daily_bar:
                        filters['no_bar'] += 1
                        continue

                    price = float(latest_trade.price)
                    prev_close = float(daily_bar.close)

                    # Price
                    if price < DISCOVERY_MIN_PRICE or price > DISCOVERY_MAX_PRICE:
                        continue
                    filters['price_pass'] += 1

                    # Gap
                    gap_pct = ((price - prev_close) / prev_close) * 100 if prev_close else 0
                    if gap_pct < DISCOVERY_MIN_GAP or gap_pct > DISCOVERY_MAX_GAP:
                        continue
                    filters['gap_pass'] += 1

                    # Volume
                    avg_vol = int(getattr(daily_bar, 'volume', 0) or 0)
                    if avg_vol < MIN_AVG_VOLUME:
                        continue
                    filters['vol_pass'] += 1

                    # Spread – if known, check; if unknown, pass
                    bid = getattr(snapshot, 'bid_price', None)
                    ask = getattr(snapshot, 'ask_price', None)
                    spread_pct = None
                    if bid and ask and price > 0:
                        spread_pct = ((ask - bid) / price) * 100
                        if spread_pct <= MAX_READY_SPREAD:
                            filters['spread_pass'] += 1
                        # else: we still keep it but mark as too wide
                    else:
                        spread_pct = None  # unknown

                    filters['fast_pass'] += 1
                    fast_candidates.append({
                        'ticker': symbol,
                        'price': price,
                        'gap_pct': gap_pct,
                        'prev_close': prev_close,
                        'avg_volume': avg_vol,
                        'spread_pct': spread_pct,
                    })

                except Exception:
                    continue
            print(f"[FastFilter] Processed {min(i+batch_size, len(universe))}/{len(universe)}")
        except Exception as e:
            print(f"[FastFilter] Batch error: {e}")
            continue

    print(f"[FastFilter] Passed: {filters['fast_pass']} candidates.")

    if filters['fast_pass'] == 0:
        print("[FastFilter] No candidates.")
        return []

    # ============================================================
    # STAGE 2 – PM QUANT (minute bars) – only top 200
    # ============================================================
    # Sort by gap descending, take top 200
    fast_candidates.sort(key=lambda x: x['gap_pct'], reverse=True)
    top_200 = fast_candidates[:200]

    pm_quant_stats = {
        'total': len(top_200),
        'pm_vol_pass': 0,
        'rvol_pass': 0,
        'pm_dist_pass': 0,
        'vwap_pass': 0,
        'pm_quant_pass': 0,
    }
    pm_candidates = []

    for c in top_200:
        symbol = c['ticker']
        price = c['price']
        gap = c['gap_pct']
        spread = c['spread_pct']

        pm = get_premarket_minute_data(symbol)
        if pm['pm_volume'] == 0 or pm['data_quality'] == 'LOW':
            continue
        pm_quant_stats['pm_vol_pass'] += 1

        rvol = pm['rvol_time_adjusted']
        if rvol < VALIDATION_MIN_RVOL:
            continue
        pm_quant_stats['rvol_pass'] += 1

        pm_high = pm['pm_high']
        pm_dist = ((pm_high - price) / pm_high) * 100 if pm_high > 0 else 999
        if pm_dist > VALIDATION_MAX_PM_DIST:
            continue
        pm_quant_stats['pm_dist_pass'] += 1

        vwap = pm['pm_vwap']
        if price < vwap * (1 + VALIDATION_MIN_VWAP_DIST):
            continue
        pm_quant_stats['vwap_pass'] += 1

        pm_quant_stats['pm_quant_pass'] += 1
        pm_candidates.append({
            'ticker': symbol,
            'price': price,
            'gap_pct': gap,
            'spread_pct': spread,
            'pm_high': pm_high,
            'pm_vwap': vwap,
            'pm_volume': pm['pm_volume'],
            'rvol_time_adj': rvol,
            'pm_high_dist': pm_dist,
            'median_pm_volume': pm.get('median_pm_volume', 0),
        })

    print(f"[PMQuant] Passed: {pm_quant_stats['pm_quant_pass']} candidates.")

    if pm_quant_stats['pm_quant_pass'] == 0:
        print("[PMQuant] No candidates passed.")
        return []

    # ============================================================
    # STAGE 3 – CATALYST & RISK – only top 50
    # ============================================================
    pm_candidates.sort(key=lambda x: x['rvol_time_adj'] + x['gap_pct']/10, reverse=True)
    top_50 = pm_candidates[:50]

    catalyst_stats = {
        'total': len(top_50),
        'catalyst_pass': 0,
        'final_pass': 0,
    }
    final_candidates = []

    for c in top_50:
        symbol = c['ticker']
        catalyst = get_catalyst_from_finnhub(symbol, FINNHUB_API_KEY)

        # Only reject if catalyst score is clearly negative (dilution/offering)
        if catalyst['score'] < VALIDATION_MIN_CATALYST_SCORE:
            continue

        catalyst_stats['catalyst_pass'] += 1
        catalyst_stats['final_pass'] += 1

        final_candidates.append({
            'ticker': symbol,
            'price': c['price'],
            'gap_pct': c['gap_pct'],
            'spread_pct': c['spread_pct'],
            'pm_high': c['pm_high'],
            'pm_vwap': c['pm_vwap'],
            'pm_volume': c['pm_volume'],
            'rvol_time_adj': c['rvol_time_adj'],
            'pm_high_dist': c['pm_high_dist'],
            'catalyst': catalyst['headline'][:80] if catalyst['headline'] else '—',
            'catalyst_score': catalyst['score'],
        })

    print(f"[Catalyst] Passed: {catalyst_stats['final_pass']} candidates.")

    # ============================================================
    # REPORT
    # ============================================================
    print("\n" + "="*60)
    print("📊 PREMARKET SCAN V2.8 – BREAKDOWN")
    print("="*60)
    print(f"Universe:              {filters['total']:,}")
    print(f"Price Pass:            {filters['price_pass']:,}")
    print(f"Gap Pass:              {filters['gap_pass']:,}")
    print(f"Volume Pass:           {filters['vol_pass']:,}")
    print(f"Spread Pass:           {filters['spread_pass']:,}")
    print(f"Fast Filter Pass:      {filters['fast_pass']:,}")
    print("-"*60)
    print(f"PM Volume Pass:        {pm_quant_stats['pm_vol_pass']:,}")
    print(f"RVOL Pass:             {pm_quant_stats['rvol_pass']:,}")
    print(f"PM Dist Pass:          {pm_quant_stats['pm_dist_pass']:,}")
    print(f"VWAP Pass:             {pm_quant_stats['vwap_pass']:,}")
    print(f"PM Quant Pass:         {pm_quant_stats['pm_quant_pass']:,}")
    print("-"*60)
    print(f"Catalyst Pass:         {catalyst_stats['catalyst_pass']:,}")
    print(f"✅ FINAL CANDIDATES:   {catalyst_stats['final_pass']:,}")
    print("="*60 + "\n")

    # Sort by final score (rvol + gap)
    final_candidates.sort(key=lambda x: x['rvol_time_adj'] + x['gap_pct']/10, reverse=True)
    return final_candidates[:10]
