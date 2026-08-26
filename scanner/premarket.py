"""
Premarket scanner – V2.12.2 (RVOL DISABLED, DIAGNOSTIC MODE)
"""
print("🔥 LOADED PREMARKET V2.12.2 - RVOL DISABLED")

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


def scan_premarket(date: str = None) -> List[Dict[str, Any]]:
    if date is None:
        date = datetime.now().strftime("%Y-%m-%d")

    print(f"[Premarket] V2.12.2 DIAGNOSTIC – {date}")

    universe = load_universe()
    if not universe:
        print("[Premarket] ❌ No universe.")
        return []

    print(f"[Premarket] Universe: {len(universe)}")

    api = tradeapi.REST(ALPACA_API_KEY, ALPACA_SECRET_KEY, base_url='https://paper-api.alpaca.markets')

    # ============================================================
    # STAGE 1 – DISCOVERY
    # ============================================================
    stats = {
        'total': len(universe),
        'no_snapshot': 0,
        'no_trade': 0,
        'no_bar': 0,
        'price_pass': 0,
        'gap_pass': 0,
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

                    if price < DISCOVERY_MIN_PRICE or price > DISCOVERY_MAX_PRICE:
                        continue
                    stats['price_pass'] += 1

                    gap_pct = ((price - prev_close) / prev_close) * 100 if prev_close else 0
                    if gap_pct < DISCOVERY_MIN_GAP or gap_pct > DISCOVERY_MAX_GAP:
                        continue
                    stats['gap_pass'] += 1

                    # Spread from latest_quote
                    latest_quote = getattr(snapshot, 'latest_quote', None)
                    if not latest_quote:
                        continue
                    bid = getattr(latest_quote, 'bid_price', None)
                    ask = getattr(latest_quote, 'ask_price', None)
                    if not bid or not ask or price <= 0:
                        continue
                    spread_pct = ((ask - bid) / price) * 100
                    if spread_pct > VALIDATION_MAX_SPREAD:
                        continue
                    stats['spread_pass'] += 1

                    stats['discovery_pass'] += 1
                    discovery_candidates.append({
                        'ticker': symbol,
                        'price': price,
                        'gap_pct': gap_pct,
                        'prev_close': prev_close,
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
    # STAGE 2 – PM ENGINE + DIAGNOSTICS (RVOL DISABLED)
    # ============================================================
    discovery_candidates.sort(key=lambda x: x['gap_pct'], reverse=True)
    top_200 = discovery_candidates[:200]

    pm_stats = {
        'total': len(top_200),
        'pm_vol_ok': 0,
        'rvol_ok': 0,          # will stay 0 (disabled)
        'pm_dist_ok': 0,
        'vwap_ok': 0,
        'catalyst_ok': 0,
        'final_pass': 0,
    }
    final_candidates = []

    print("\n" + "="*60)
    print("📌 PM DIAGNOSTICS (RVOL DISABLED)")
    print("="*60)

    for c in top_200:
        symbol = c['ticker']
        price = c['price']
        gap = c['gap_pct']
        spread = c['spread_pct']

        pm = get_premarket_minute_data(symbol, api)

        print(f"[PM RESULT] {symbol}")
        print(f"  price={price:.2f} | gap={gap:.1f}%")
        print(f"  pm_volume={pm.get('pm_volume', 'N/A')}")
        print(f"  pm_bars_count={pm.get('pm_bars_count', 0)}")
        print(f"  pm_high={pm.get('pm_high', 'N/A')}")
        print(f"  pm_vwap={pm.get('pm_vwap', 'N/A')}")
        print(f"  rvol=UNAVAILABLE (placeholder disabled)")
        print(f"  error={pm.get('error', 'None')}")

        if pm.get('error'):
            continue

        pm_volume = pm['pm_volume']
        if pm_volume is None or pm_volume == 0:
            continue
        pm_stats['pm_vol_ok'] += 1

        # ---- RVOL DISABLED ----
        # We do NOT check RVOL. We mark it as UNAVAILABLE.
        rvol = None
        rvol_method = "UNAVAILABLE"

        pm_high = pm['pm_high']
        pm_vwap = pm['pm_vwap']
        pm_dist = ((pm_high - price) / pm_high) * 100 if pm_high else 999
        pm_high_dist = max(0.0, pm_dist)
        if pm_high_dist > VALIDATION_MAX_PM_DIST:
            continue
        pm_stats['pm_dist_ok'] += 1

        if pm_vwap and price < pm_vwap * (1 + VALIDATION_MIN_VWAP_DIST):
            continue
        pm_stats['vwap_ok'] += 1

        # ---- Catalyst (not blocking, score only) ----
        catalyst_result = get_catalyst_from_finnhub(symbol, FINNHUB_API_KEY)
        catalyst_score = catalyst_result['score']
        catalyst_text = catalyst_result['headline'][:80] if catalyst_result['headline'] else None

        # ---- Event Score (RVOL removed) ----
        event_score = 0
        if gap > 0:
            event_score += gap / 5
        if pm_high_dist <= 2:
            event_score += 15
        if spread is not None and spread <= 1.0:
            event_score += 5
        if catalyst_score >= 5:
            event_score += catalyst_score
        event_score = round(min(100, max(0, event_score)), 1)

        pm_stats['final_pass'] += 1
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
            'rvol_method': rvol_method,
            'spread_pct': spread,
            'catalyst': catalyst_text,
            'catalyst_score': catalyst_score,
            'event_score': event_score,
            'grade': 'B' if event_score >= 60 else 'C' if event_score >= 40 else 'WATCH',
            'state': 'WATCH',
        })

    # ====== REPORT ======
    print("\n" + "="*60)
    print("📊 PREMARKET SCAN V2.12.2 – DIAGNOSTIC (RVOL DISABLED)")
    print("="*60)
    print(f"Universe:           {stats['total']:,}")
    print(f"Discovery Pass:     {stats['discovery_pass']:,}")
    print("-"*60)
    print(f"PM Volume OK:       {pm_stats['pm_vol_ok']:,}")
    print(f"RVOL FILTER:        DISABLED")
    print(f"PM Dist OK:         {pm_stats['pm_dist_ok']:,}")
    print(f"VWAP OK:            {pm_stats['vwap_ok']:,}")
    print(f"Catalyst OK:        {pm_stats['catalyst_ok']:,}")
    print(f"✅ FINAL:           {pm_stats['final_pass']:,}")
    print("="*60 + "\n")

    final_candidates.sort(key=lambda x: x['event_score'], reverse=True)
    return final_candidates[:20]