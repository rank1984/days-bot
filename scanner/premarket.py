"""
Premarket scanner – V2.10 REAL PM DATA
Stage 1: Discovery (fast filters)
Stage 2: PM Engine (minute bars) – only for top candidates
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


# ── Discovery thresholds ──────────────────────────────────
DISCOVERY_MIN_PRICE = 1.0
DISCOVERY_MAX_PRICE = 50.0
DISCOVERY_MIN_GAP = 1.0
DISCOVERY_MAX_GAP = 30.0
DISCOVERY_MIN_PM_VOL = 50_000  # placeholder – will be replaced by real PM volume after Stage 2
MAX_SPREAD_DISCOVERY = 1.5


def scan_premarket(date: str = None) -> List[Dict[str, Any]]:
    if date is None:
        date = datetime.now().strftime("%Y-%m-%d")

    print(f"[Premarket] V2.10 REAL PM – {date}")

    universe = load_universe()
    if not universe:
        print("[Premarket] ❌ No universe.")
        return []

    print(f"[Premarket] Universe: {len(universe)}")

    api = tradeapi.REST(ALPACA_API_KEY, ALPACA_SECRET_KEY, base_url='https://paper-api.alpaca.markets')

    # ============================================================
    # STAGE 1 – DISCOVERY (Fast filters, no PM data)
    # ============================================================
    stats = {
        'total': len(universe),
        'no_snapshot': 0,
        'no_trade': 0,
        'no_bar': 0,
        'price_pass': 0,
        'gap_pass': 0,
        'vol_pass': 0,
        'spread_pass': 0,
        'discovery_pass': 0,
    }
    discovery_candidates = []

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

                    # 1. Price
                    if price < DISCOVERY_MIN_PRICE or price > DISCOVERY_MAX_PRICE:
                        continue
                    stats['price_pass'] += 1

                    # 2. Gap
                    gap_pct = ((price - prev_close) / prev_close) * 100 if prev_close else 0
                    if gap_pct < DISCOVERY_MIN_GAP or gap_pct > DISCOVERY_MAX_GAP:
                        continue
                    stats['gap_pass'] += 1

                    # 3. Volume (placeholder – daily_bar.volume, but we'll use it only for initial filtering)
                    avg_vol = int(getattr(daily_bar, 'volume', 0) or 0)
                    if avg_vol < MIN_AVG_VOLUME:
                        continue
                    stats['vol_pass'] += 1

                    # 4. Spread – only if known and too wide; unknown = pass
                    bid = getattr(snapshot, 'bid_price', None)
                    ask = getattr(snapshot, 'ask_price', None)
                    spread_pct = None
                    if bid and ask and price > 0:
                        spread_pct = ((ask - bid) / price) * 100
                        if spread_pct > MAX_SPREAD_DISCOVERY:
                            continue
                        stats['spread_pass'] += 1
                    else:
                        stats['spread_pass'] += 1

                    # ====== Discovery Pass ======
                    stats['discovery_pass'] += 1
                    discovery_candidates.append({
                        'ticker': symbol,
                        'price': price,
                        'gap_pct': gap_pct,
                        'prev_close': prev_close,
                        'avg_volume': avg_vol,
                        'spread_pct': spread_pct,
                    })

                except Exception:
                    continue
            print(f"[Discovery] Processed {min(i+batch_size, len(universe))}/{len(universe)}")
        except Exception as e:
            print(f"[Discovery] Batch error: {e}")
            continue

    print(f"[Discovery] Passed: {stats['discovery_pass']} candidates.")

    if stats['discovery_pass'] == 0:
        return []

    # ============================================================
    # STAGE 2 – PM ENGINE (Minute Bars) – only top 100
    # ============================================================
    discovery_candidates.sort(key=lambda x: x['gap_pct'], reverse=True)
    top_100 = discovery_candidates[:100]

    pm_stats = {
        'total': len(top_100),
        'pm_vol_ok': 0,
        'rvol_ok': 0,
        'pm_dist_ok': 0,
        'vwap_ok': 0,
        'catalyst_ok': 0,
        'final_pass': 0,
    }
    final_candidates = []

    for c in top_100:
        symbol = c['ticker']
        price = c['price']
        gap = c['gap_pct']
        spread = c['spread_pct']

        # ---- Fetch real PM data ----
        pm = get_premarket_minute_data(symbol, api)
        if pm.get('error'):
            continue  # no PM data, skip

        pm_volume = pm['pm_volume']
        if pm_volume is None or pm_volume == 0:
            continue
        pm_stats['pm_vol_ok'] += 1

        rvol = pm.get('rvol_time_adjusted')
        if rvol is None:
            continue
        pm_stats['rvol_ok'] += 1

        pm_high = pm['pm_high']
        pm_vwap = pm['pm_vwap']
        pm_dist = ((pm_high - price) / pm_high) * 100 if pm_high else 999
        pm_high_dist = max(0.0, pm_dist)  # no negative

        # ---- Filters with real PM data ----
        if pm_high_dist > 5:  # too far from PMH
            continue
        pm_stats['pm_dist_ok'] += 1

        if pm_vwap and price < pm_vwap * 1.01:  # must be above VWAP
            continue
        pm_stats['vwap_ok'] += 1

        # ---- Catalyst ----
        catalyst_result = get_catalyst_from_finnhub(symbol, FINNHUB_API_KEY)
        catalyst_text = catalyst_result['headline'][:80] if catalyst_result['headline'] else None
        catalyst_score = catalyst_result['score']
        # Catalyst is optional – not a blocker

        # ---- Event Score ----
        event_score = 0
        if gap > 0:
            event_score += gap / 5
        if rvol is not None and rvol > 0:
            event_score += min(rvol * 10, 40)
        if pm_high_dist <= 2:
            event_score += 15
        if spread is not None and spread <= 1.0:
            event_score += 5
        event_score = round(min(100, max(0, event_score)), 1)

        # ---- Candidate ----
        final_candidates.append({
            'ticker': symbol,
            'price': price,
            'gap_pct': gap,
            'pm_high': pm_high,
            'pm_low': pm['pm_low'],
            'pm_volume': pm_volume,
            'pm_vwap': pm_vwap,
            'pm_high_dist': pm_high_dist,
            'rvol': rvol,
            'rvol_method': 'TIME_ADJUSTED' if rvol is not None else 'N/A',
            'spread_pct': spread,
            'catalyst': catalyst_text,
            'catalyst_score': catalyst_score,
            'event_score': event_score,
            'grade': 'B' if event_score >= 60 else 'C' if event_score >= 40 else 'WATCH',
            'state': 'WATCH',
        })
        pm_stats['final_pass'] += 1

    # ====== סיכום ======
    print("\n" + "="*60)
    print("📊 PREMARKET SCAN V2.10 – REAL PM DATA")
    print("="*60)
    print(f"Universe:           {stats['total']:,}")
    print(f"Discovery Pass:     {stats['discovery_pass']:,}")
    print("-"*60)
    print(f"PM Volume OK:       {pm_stats['pm_vol_ok']:,}")
    print(f"RVOL OK:            {pm_stats['rvol_ok']:,}")
    print(f"PM Dist OK:         {pm_stats['pm_dist_ok']:,}")
    print(f"VWAP OK:            {pm_stats['vwap_ok']:,}")
    print(f"Catalyst OK:        {pm_stats['catalyst_ok']:,}")
    print(f"✅ FINAL:           {pm_stats['final_pass']:,}")
    print("="*60 + "\n")

    final_candidates.sort(key=lambda x: x['event_score'], reverse=True)
    return final_candidates[:20]
