"""
Premarket scanner – V2.9 DATA INTEGRITY FIX
"""
import sys
from pathlib import Path
from datetime import datetime
from typing import List, Dict, Any, Optional

BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))
sys.path.insert(0, str(BASE_DIR / "utils"))

import alpaca_trade_api as tradeapi
from utils.config import *
from scanner.universe import load_universe
from scanner.catalyst_engine import get_catalyst_from_finnhub


# ── קריטריוני גילוי ──────────────────────────────────────
DISCOVERY_MIN_PRICE = 1.0
DISCOVERY_MAX_PRICE = 50.0
DISCOVERY_MIN_GAP = 1.0
DISCOVERY_MAX_GAP = 30.0
DISCOVERY_MIN_PM_VOL = 50_000
VALIDATION_MAX_SPREAD = 1.5


def scan_premarket(date: str = None) -> List[Dict[str, Any]]:
    if date is None:
        date = datetime.now().strftime("%Y-%m-%d")

    print(f"[Premarket] V2.9 DATA FIX – {date}")

    universe = load_universe()
    if not universe:
        print("[Premarket] ❌ No universe.")
        return []

    print(f"[Premarket] Universe: {len(universe)}")

    api = tradeapi.REST(ALPACA_API_KEY, ALPACA_SECRET_KEY, base_url='https://paper-api.alpaca.markets')

    candidates = []
    stats = {
        'total': len(universe),
        'no_snapshot': 0,
        'no_trade': 0,
        'no_bar': 0,
        'price_pass': 0,
        'gap_pass': 0,
        'pm_vol_pass': 0,
        'spread_pass': 0,
        'final_candidates': 0,
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

                    # 1. Price
                    if price < DISCOVERY_MIN_PRICE or price > DISCOVERY_MAX_PRICE:
                        continue
                    stats['price_pass'] += 1

                    # 2. Gap
                    gap_pct = ((price - prev_close) / prev_close) * 100 if prev_close else 0
                    if gap_pct < DISCOVERY_MIN_GAP or gap_pct > DISCOVERY_MAX_GAP:
                        continue
                    stats['gap_pass'] += 1

                    # 3. Premarket Volume (אומדן מ-daily_bar.volume)
                    pm_volume = int(getattr(daily_bar, 'volume', 0) or 0)
                    if pm_volume < DISCOVERY_MIN_PM_VOL:
                        continue
                    stats['pm_vol_pass'] += 1

                    # 4. Spread – אם UNKNOWN → REJECT
                    bid = getattr(snapshot, 'bid_price', None)
                    ask = getattr(snapshot, 'ask_price', None)
                    if bid and ask and price > 0:
                        spread_pct = ((ask - bid) / price) * 100
                        if spread_pct > VALIDATION_MAX_SPREAD:
                            continue  # spread רחב מדי
                        stats['spread_pass'] += 1
                    else:
                        # Spread UNKNOWN – לא נכנס לרשימה
                        continue

                    # ====== עבר את כל הפילטרים ======
                    stats['final_candidates'] += 1

                    # ====== נתוני PM ======
                    pm_high = float(getattr(daily_bar, 'high', price))
                    pm_low = float(getattr(daily_bar, 'low', price))
                    pm_vwap = (pm_high + pm_low + price) / 3
                    # PM Dist – לא יכול להיות שלילי (מעל PMH = 0)
                    pm_high_dist = max(0.0, ((pm_high - price) / pm_high) * 100 if pm_high > 0 else 999.0)

                    # ====== RVOL – אמיתי או N/A ======
                    avg_volume = int(getattr(daily_bar, 'volume', 0) or 1)
                    if avg_volume > 0:
                        rvol = round(pm_volume / avg_volume, 2)
                        rvol_method = 'ESTIMATED'
                    else:
                        rvol = None  # N/A
                        rvol_method = 'N/A'

                    # ====== Catalyst – עם טיפול בשגיאות ======
                    try:
                        catalyst_result = get_catalyst_from_finnhub(symbol, FINNHUB_API_KEY)
                        catalyst_text = catalyst_result['headline'][:80] if catalyst_result['headline'] else None
                        catalyst_score = catalyst_result['score']
                        if catalyst_text is None or catalyst_text == '':
                            catalyst_text = None
                            catalyst_score = 0
                    except Exception as e:
                        catalyst_text = None
                        catalyst_score = 0
                        print(f"[Catalyst] Error for {symbol}: {e}")

                    # ====== Event Score (רק עם נתונים אמיתיים) ======
                    event_score = 0
                    if gap_pct > 0:
                        event_score += gap_pct / 5
                    if rvol is not None and rvol > 0:
                        event_score += rvol * 10
                    if pm_high_dist <= 2:
                        event_score += 10
                    if spread_pct <= 1.0:
                        event_score += 5

                    event_score = round(min(100, max(0, event_score)), 1)

                    # ====== Candidate Contract ======
                    candidate = {
                        "ticker": symbol,
                        "price": price,

                        "gap_pct": gap_pct,

                        "pm_high": pm_high,
                        "pm_low": pm_low,
                        "pm_volume": pm_volume,
                        "pm_vwap": pm_vwap,
                        "pm_high_dist": pm_high_dist,   # 0 = at or above PMH

                        "rvol": rvol,                     # None = N/A
                        "rvol_method": rvol_method,

                        "spread_pct": spread_pct,

                        "catalyst": catalyst_text,        # None = N/A
                        "catalyst_score": catalyst_score,

                        "event_score": event_score,

                        "grade": "B" if event_score >= 60 else "C" if event_score >= 40 else "WATCH",
                        "state": "WATCH",  # עדיין לא breakout
                    }

                    candidates.append(candidate)

                except Exception:
                    continue
            print(f"[Discovery] Processed {min(i+batch_size, len(universe))}/{len(universe)}")
        except Exception as e:
            print(f"[Discovery] Batch error: {e}")
            continue

    # ====== סיכום ======
    print("\n" + "="*60)
    print("📊 PREMARKET DISCOVERY – V2.9 DATA FIX")
    print("="*60)
    print(f"Universe:           {stats['total']:,}")
    print(f"Price Pass:         {stats['price_pass']:,}")
    print(f"Gap Pass:           {stats['gap_pass']:,}")
    print(f"PM Vol Pass:        {stats['pm_vol_pass']:,}")
    print(f"Spread Pass:        {stats['spread_pass']:,}")
    print(f"✅ CANDIDATES:      {stats['final_candidates']:,}")
    print("="*60 + "\n")

    candidates.sort(key=lambda x: x['event_score'], reverse=True)
    return candidates[:20]