"""
Premarket scanner for DAYS-BOT - Using yfinance (free, no API key)
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

import yfinance as yf
from utils.config import *
from scanner.universe import load_universe


def scan_premarket(date: str = None) -> List[Dict[str, Any]]:
    """
    Scan for premarket candidates using yfinance.
    yfinance provides preMarketPrice, regularMarketPrice, previousClose, volume.
    """
    if date is None:
        date = datetime.now().strftime("%Y-%m-%d")
    
    print(f"[Premarket] Scanning for {date}...")
    
    universe = load_universe()
    if not universe:
        print("[Premarket] ❌ No universe found")
        return []
    
    print(f"[Premarket] Universe size: {len(universe)}")
    
    candidates = []
    stats = {
        'total': len(universe),
        'no_data': 0,
        'price_passed': 0,
        'gap_passed': 0,
        'volume_passed': 0,
        'final_passed': 0,
    }
    
    # ייתכן ש-yfinance יגביל אותנו – נעבור על המניות בסדרות קטנות
    batch_size = 50  # yfinance יכול לקחת רשימה של סימבולים בבת אחת
    all_symbols = [s['symbol'] for s in universe]
    
    for i in range(0, len(all_symbols), batch_size):
        batch_symbols = all_symbols[i:i+batch_size]
        try:
            # הורדת מידע עבור כל הקבוצה בבת אחת (יעיל יותר)
            tickers = yf.Tickers(" ".join(batch_symbols))
            
            for symbol in batch_symbols:
                try:
                    ticker = tickers.tickers.get(symbol)
                    if not ticker:
                        stats['no_data'] += 1
                        continue
                    
                    info = ticker.info
                    if not info:
                        stats['no_data'] += 1
                        continue
                    
                    # מחיר נוכחי – מעדיף preMarketPrice אם קיים, אחרת regularMarketPrice
                    price = info.get('preMarketPrice')
                    if price is None or price == 0:
                        price = info.get('regularMarketPrice')
                    if price is None or price == 0:
                        stats['no_data'] += 1
                        continue
                    
                    prev_close = info.get('previousClose')
                    if prev_close is None or prev_close == 0:
                        stats['no_data'] += 1
                        continue
                    
                    # נפח – מעדיף preMarketVolume, אחרת regularMarketVolume
                    volume = info.get('preMarketVolume')
                    if volume is None or volume == 0:
                        volume = info.get('regularMarketVolume')
                    if volume is None:
                        volume = 0
                    
                    # ====== Filters ======
                    # Price
                    if price < MIN_PRICE or price > MAX_PRICE:
                        continue
                    stats['price_passed'] += 1
                    
                    # Gap
                    gap_pct = ((price - prev_close) / prev_close) * 100 if prev_close else 0
                    if gap_pct < MIN_GAP_PCT or gap_pct > MAX_GAP_PCT:
                        continue
                    stats['gap_passed'] += 1
                    
                    # Volume (נשתמש ב-volume שהתקבל)
                    if volume < MIN_AVG_VOLUME:
                        continue
                    stats['volume_passed'] += 1
                    
                    stats['final_passed'] += 1
                    
                    # ====== Candidate ======
                    volume_ratio = volume / MIN_AVG_VOLUME if MIN_AVG_VOLUME > 0 else 1.0
                    freshness = 100 - (gap_pct * 2) if gap_pct > 0 else 50
                    momentum_score = 50 + (gap_pct * 0.5)
                    combined = (freshness + momentum_score) / 2
                    
                    candidate = {
                        'ticker': symbol,
                        'price': price,
                        'gap_pct': gap_pct,
                        'prev_close': prev_close,
                        'volume': volume,
                        'avg_volume': volume,  # אין ממוצע יומי, נשתמש באותו
                        'volume_ratio': volume_ratio,
                        'dollar_volume': price * volume,
                        'freshness': freshness,
                        'momentum_score': momentum_score,
                        'combined': combined,
                        'catalyst': '—',
                        'pm_high': price,
                        'pm_high_dist': gap_pct,
                        'pm_high_age': 0,
                        'pm_volume': volume,
                        'pm_rvol': volume_ratio,
                        'vwap_dist': 0,
                        'vol_accel': 1.0,
                        'momentum_5m': gap_pct * 0.1,
                    }
                    
                    candidates.append(candidate)
                    
                except Exception as e:
                    # אם סימבול ספציפי נכשל – נמשיך הלאה
                    continue
            
            print(f"[Premarket] Processed {min(i+batch_size, len(all_symbols))}/{len(all_symbols)}")
            
        except Exception as e:
            print(f"[Premarket] Batch error: {e}")
            continue
    
    # ====== סטטיסטיקות ======
    print("\n" + "="*50)
    print("📊 PREMARKET SCAN STATISTICS (yfinance)")
    print("="*50)
    print(f"Total Universe:        {stats['total']:,}")
    print(f"No Data (symbol):      {stats['no_data']:,}")
    print("-"*50)
    print(f"✅ Price Passed:        {stats['price_passed']:,}")
    print(f"✅ Gap Passed:          {stats['gap_passed']:,}")
    print(f"✅ Volume Passed:       {stats['volume_passed']:,}")
    print("-"*50)
    print(f"🎯 FINAL CANDIDATES:    {stats['final_passed']:,}")
    print("="*50 + "\n")
    
    # ====== Scores ======
    scored = []
    for c in candidates:
        score = calculate_breakout_score(c)
        if score >= MIN_SCORE:
            c['score'] = score
            scored.append(c)
    
    scored.sort(key=lambda x: x.get('score', 0), reverse=True)
    
    print(f"[Premarket] ✅ Found {len(scored)} qualified candidates")
    
    if scored:
        print("\n🏆 TOP 5 CANDIDATES:")
        for i, c in enumerate(scored[:5], 1):
            print(f"  {i}. {c['ticker']}  ${c['price']:.2f}  Gap: {c['gap_pct']:+.1f}%  Score: {c.get('score', 0):.0f}")
        print()
    
    return scored[:10]


def calculate_breakout_score(candidate: Dict[str, Any]) -> float:
    score = 0
    
    gap = candidate.get('gap_pct', 0)
    if gap >= 5.0:
        score += 20
    elif gap >= 3.0:
        score += 15
    elif gap >= 2.0:
        score += 10
    elif gap >= 1.0:
        score += 5
    
    volume = candidate.get('volume', 0)
    if volume >= 1_000_000:
        score += 30
    elif volume >= 500_000:
        score += 25
    elif volume >= 200_000:
        score += 20
    elif volume >= 100_000:
        score += 15
    else:
        score += 5
    
    dvol = candidate.get('dollar_volume', 0)
    if dvol >= 5_000_000:
        score += 25
    elif dvol >= 1_000_000:
        score += 18
    elif dvol >= 500_000:
        score += 10
    elif dvol >= 250_000:
        score += 5
    
    return min(100, score)
