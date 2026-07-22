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

# טעינת הגדרות קבועות
from utils.config import *
from scanner.universe import load_universe
import alpaca_trade_api as tradeapi


def get_catalyst(symbol: str) -> str:
    """
    פונקציית עזר להבאת חדשות/זרזים (מנסה לטעון מ-news_scanner במידה וקיים)
    """
    try:
        from scanner.news_scanner import get_catalyst_news_score
        _, catalyst_text = get_catalyst_news_score(symbol)
        return catalyst_text if catalyst_text else "—"
    except Exception:
        return "—"


def calculate_breakout_score(candidate: Dict[str, Any]) -> float:
    score = 0
    
    gap = candidate.get('gap_pct', 0)
    if gap >= 5.0:
        score += 25
    elif gap >= 3.0:
        score += 18
    elif gap >= 1.0:
        score += 10
    
    volume = candidate.get('volume', 0)
    if volume >= 500_000:
        score += 20
    elif volume >= 200_000:
        score += 15
    elif volume >= 100_000:
        score += 10
    elif volume >= 50_000:
        score += 5
    
    rvol = candidate.get('rvol', 0)
    if rvol >= 3.0:
        score += 20
    elif rvol >= 2.0:
        score += 15
    elif rvol >= 1.0:
        score += 10
    
    dvol = candidate.get('dollar_volume', 0)
    if dvol >= 1_000_000:
        score += 20
    elif dvol >= 500_000:
        score += 15
    elif dvol >= 200_000:
        score += 10
    
    return min(100, score)


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
                    
                    daily_bar = snapshot.daily_bar
                    if not daily_bar:
                        stats['no_bar'] += 1
                        continue
                    
                    prev_close = daily_bar.close
                    volume = daily_bar.volume
                    prev_volume = daily_bar.volume
                    
                    # נפח ממוצע היסטורי לטובת חישוב RVOL 
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
                    
                    # ====== חישוב פרמטרים מורחבים ======
                    volume_ratio = volume / MIN_AVG_VOLUME if MIN_AVG_VOLUME > 0 else 1.0
                    pm_high = price
                    pm_high_dist = 0.0
                    atr = price * 0.04
                    catalyst_text = get_catalyst(symbol)
                    momentum_score = min(100.0, max(0.0, gap_pct * 2 + rvol * 10))
                    freshness = "FRESH"
                    combined = momentum_score
                    
                    candidate = {
                        'ticker': symbol,
                        'price': price,
                        'gap_pct': gap_pct,
                        'prev_close': prev_close,
                        'volume': volume,
                        'avg_volume': prev_volume,
                        'volume_ratio': volume_ratio,
                        'rvol': rvol,
                        'float': 0,
                        'dollar_volume': dollar_volume,
                        'freshness': freshness,
                        'momentum_score': momentum_score,
                        'combined': combined,
                        'catalyst': catalyst_text,
                        'pm_high': pm_high,
                        'pm_high_dist': pm_high_dist,
                        'atr': atr,
                        'score': 0.0,  # יחושב בשלב הבא
                        # שדות תואמים לאחור
                        'pm_volume': volume,
                        'pm_rvol': volume_ratio,
                        'vwap_dist': 0,
                        'vol_accel': 1.0,
                        'momentum_5m': gap_pct * 0.1,
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
    print(f"Total Universe:         {stats['total']:,}")
    print(f"No Snapshot:            {stats['no_snapshot']:,}")
    print(f"No Trade:               {stats['no_trade']:,}")
    print(f"No Daily Bar:           {stats['no_bar']:,}")
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
