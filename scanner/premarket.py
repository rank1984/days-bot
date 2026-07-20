"""
Premarket scanner for DAYS-BOT - Using Alpaca (fast)
Integrated with RVOL, Dollar Volume, and Enhanced Scoring.
"""
import sys
import os
from pathlib import Path
import time
from datetime import datetime
from typing import List, Dict, Any, Optional

BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))
sys.path.insert(0, str(BASE_DIR / "utils"))

# טעינת הגדרות קבועות (נניח שקיימים שם המשתנים הנדרשים)
from utils.config import *
from scanner.universe import load_universe
import alpaca_trade_api as tradeapi


def get_catalyst(symbol: str) -> str:
    """
    פונקציית עזר להבאת חדשות/זרזים (למשל מ-Finnhub או מקור אחר).
    כרגע מחזירה ערך ברירת מחדל כדי לא לחסום את הריצה הריבועית המהירה.
    """
    # כאן תוכל להטמיע בעתיד: קריאה ל- Finnhub API
    return "—"


def calculate_breakout_score(candidate: Dict[str, Any]) -> float:
    """
    מערכת דירוג (Scoring) משופרת המבוססת על משקולות מומנטום, נזילות ועניין בשוק.
    מחזירה ציון מ-0 עד 100.
    """
    score = 0
    
    # 1. מומנטום התחלתי (Gap %) - עד 25 נקודות
    gap = candidate.get('gap_pct', 0)
    if gap >= 5.0: score += 25
    elif gap >= 3.0: score += 18
    elif gap >= 1.0: score += 10
        
    # 2. עניין בשוק (RVOL) - עד 25 נקודות
    rvol = candidate.get('rvol', 1.0)
    if rvol >= 5.0: score += 25
    elif rvol >= 3.0: score += 18
    elif rvol >= 2.0: score += 10
        
    # 3. נזילות אמיתית (Dollar Volume) - עד 20 נקודות
    dvol = candidate.get('dollar_volume', 0)
    if dvol >= 5_000_000: score += 20
    elif dvol >= 1_000_000: score += 15
    elif dvol >= 500_000: score += 10
        
    # הערה: ניתן להוסיף בעתיד עוד 30 נקודות על Catalyst, Float ומרחק מ-PM High
    
    return min(100.0, float(score))


def scan_premarket(date: str = None) -> List[Dict[str, Any]]:
    if date is None:
        date = datetime.now().strftime("%Y-%m-%d")
    
    print(f"[Premarket] Scanning for {date}...")
    
    universe = load_universe()
    if not universe:
        print("[Premarket] ❌ No universe found")
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
        'rvol_passed': 0,
        'dvol_passed': 0,
        'final_passed': 0,
    }
    
    batch_size = 100
    for i in range(0, len(universe), batch_size):
        batch = universe[i:i+batch_size]
        symbols = [s['symbol'] for s in batch]
        
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
                    
                    daily_bar = snapshot.daily_bar
                    if not daily_bar:
                        stats['no_bar'] += 1
                        continue
                    
                    prev_close = daily_bar.close
                    volume = daily_bar.volume
                    
                    # נפח ממוצע היסטורי לטובת חישוב RVOL 
                    # נשתמש ב-prev_daily_bar מה-Snapshot במידה וקיים, כחלופה מהירה
                    prev_bar = getattr(snapshot, 'prev_daily_bar', None)
                    avg_volume_10d = prev_bar.volume if (prev_bar and prev_bar.volume > 0) else MIN_AVG_VOLUME
                    
                    # ====== פילטר 1: מחיר ======
                    if price < MIN_PRICE or price > MAX_PRICE:
                        continue
                    stats['price_passed'] += 1
                    
                    # ====== פילטר 2: אחוז הגאפ ======
                    gap_pct = ((price - prev_close) / prev_close) * 100 if prev_close else 0
                    if gap_pct < MIN_GAP_PCT or gap_pct > MAX_GAP_PCT:
                        continue
                    stats['gap_passed'] += 1
                    
                    # ====== פילטר 3: נפח בסיסי וממוצע ======
                    if volume < MIN_AVG_VOLUME:
                        continue
                    stats['volume_passed'] += 1
                    
                    # ====== פילטר 4: Relative Volume (RVOL) ======
                    rvol = volume / avg_volume_10d if avg_volume_10d > 0 else 1.0
                    if rvol < 2.0:  # סינון מניות ללא מומנטום ווליום
                        continue
                    stats['rvol_passed'] += 1
                    
                    # ====== פילטר 5: Dollar Volume (נזילות אמיתית) ======
                    dollar_volume = price * volume
                    if dollar_volume < 1_000_000:  # מינימום 1 מיליון דולר נזילות
                        continue
                    stats['dvol_passed'] += 1
                    
                    stats['final_passed'] += 1
                    
                    candidate = {
                        'ticker': symbol,
                        'price': price,
                        'gap_pct': gap_pct,
                        'prev_close': prev_close,
                        'volume': volume,
                        'dollar_volume': dollar_volume,
                        'rvol': rvol,
                        'volume_ratio': volume / MIN_AVG_VOLUME if MIN_AVG_VOLUME > 0 else 1.0,
                        'pm_volume': volume,
                        'pm_rvol': rvol,
                        'catalyst': get_catalyst(symbol),
                        'score': 0.0  # יחושב בשלב הבא
                    }
                    candidates.append(candidate)
                    
                except Exception:
                    continue
            
            print(f"[Premarket] Processed {min(i+batch_size, len(universe))}/{len(universe)}")
            
        except Exception as e:
            print(f"[Premarket] Batch error: {e}")
            continue
    
    # ====== הדפסת סטטיסטיקות סריקה ======
    print("\n" + "="*50)
    print("📊 PREMARKET SCAN STATISTICS (Alpaca Enhanced)")
    print("="*50)
    print(f"Total Universe:        {stats['total']:,}")
    print(f"No Snapshot:           {stats['no_snapshot']:,}")
    print(f"No Trade:              {stats['no_trade']:,}")
    print(f"No Daily Bar:          {stats['no_bar']:,}")
    print("-"*50)
    print(f"✅ Price Passed:        {stats['price_passed']:,}")
    print(f"✅ Gap Passed:          {stats['gap_passed']:,}")
    print(f"✅ Volume Passed:       {stats['volume_passed']:,}")
    print(f"✅ RVOL Passed:         {stats['rvol_passed']:,}")
    print(f"✅ Dollar Volume Passed:{stats['dvol_passed']:,}")
    print("-"*50)
    print(f"🎯 FINAL CANDIDATES:    {stats['final_passed']:,}")
    print("="*50 + "\n")
    
    # ====== חישוב ציון וסינון סופי ======
    scored = []
    for c in candidates:
        score = calculate_breakout_score(c)
        if score >= MIN_SCORE:
            c['score'] = score
            scored.append(c)
    
    # מיון לפי הציון הגבוה ביותר
    scored.sort(key=lambda x: x.get('score', 0.0), reverse=True)
    
    print(f"[Premarket] ✅ Found {len(scored)} qualified candidates (Score >= {MIN_SCORE})")
    if scored:
        print("\n🏆 TOP 5 ENHANCED CANDIDATES:")
        for i, c in enumerate(scored[:5], 1):
            print(f"  {i}. {c['ticker']}  ${c['price']:.2f}  Gap: {c['gap_pct']:+.1f}%  RVOL: {c['rvol']:.2f}  DVol: ${c['dollar_volume']/1e6:.1f}M  Score: {c['score']:.0f}")
        print()
    
    return scored[:10]
