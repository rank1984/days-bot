"""
Premarket scanner for DAYS-BOT - Using yfinance with filtering & caching
"""
import sys
import os
from pathlib import Path
import time
import json
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional

BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))
sys.path.insert(0, str(BASE_DIR / "utils"))

import yfinance as yf
from utils.config import *
from scanner.universe import load_universe


def scan_premarket(date: str = None) -> List[Dict[str, Any]]:
    if date is None:
        date = datetime.now().strftime("%Y-%m-%d")
    
    print(f"[Premarket] Scanning for {date}...")
    
    universe = load_universe()
    if not universe:
        print("[Premarket] ❌ No universe found")
        return []
    
    # ====== סינון מקדים לפי מחיר (ממוצע) – אם יש לנו מידע ======
    # נשתמש במטמון של yfinance כדי לא להוריד שוב
    cache_file = os.path.join(BASE_DIR, "data", "yfinance_cache.json")
    cache_age = 900  # 15 דקות
    
    # טען מטמון אם קיים ועדכני
    cached_data = {}
    if os.path.exists(cache_file):
        try:
            with open(cache_file, 'r') as f:
                cache = json.load(f)
                if (datetime.now() - datetime.fromisoformat(cache.get('timestamp', '2020-01-01'))).seconds < cache_age:
                    cached_data = cache.get('data', {})
                    print(f"[Cache] Loaded {len(cached_data)} symbols from cache")
        except:
            pass
    
    # סימבולים שצריך להביא
    symbols_to_fetch = []
    for s in universe:
        if s['symbol'] not in cached_data:
            symbols_to_fetch.append(s['symbol'])
    
    # אם יש סימבולים חדשים – הבא אותם
    if symbols_to_fetch:
        print(f"[yfinance] Fetching {len(symbols_to_fetch)} symbols...")
        # נחלק לקבוצות קטנות כדי לא להעמיס
        batch_size = 20
        new_data = {}
        for i in range(0, len(symbols_to_fetch), batch_size):
            batch = symbols_to_fetch[i:i+batch_size]
            try:
                # שימוש ב-Tickers לקבוצה
                tickers = yf.Tickers(" ".join(batch))
                for symbol in batch:
                    try:
                        ticker = tickers.tickers.get(symbol)
                        if ticker:
                            info = ticker.info
                            # נשמור רק מה שנחוץ
                            new_data[symbol] = {
                                'price': info.get('preMarketPrice') or info.get('regularMarketPrice'),
                                'prev_close': info.get('previousClose'),
                                'volume': info.get('preMarketVolume') or info.get('regularMarketVolume'),
                            }
                        else:
                            new_data[symbol] = None
                    except:
                        new_data[symbol] = None
            except Exception as e:
                print(f"[yfinance] Batch error: {e}")
            # המתן בין קבוצות כדי לא להעמיס
            time.sleep(0.5)
            print(f"[yfinance] Fetched {min(i+batch_size, len(symbols_to_fetch))}/{len(symbols_to_fetch)}")
        
        # עדכן מטמון
        cached_data.update(new_data)
        cache = {'timestamp': datetime.now().isoformat(), 'data': cached_data}
        with open(cache_file, 'w') as f:
            json.dump(cache, f)
        print(f"[Cache] Updated with {len(new_data)} symbols")
    
    # ====== עכשיו סריקה ======
    candidates = []
    stats = {
        'total': len(universe),
        'no_data': 0,
        'price_passed': 0,
        'gap_passed': 0,
        'volume_passed': 0,
        'final_passed': 0,
    }
    
    for symbol_data in universe:
        symbol = symbol_data['symbol']
        data = cached_data.get(symbol)
        if not data or not data.get('price'):
            stats['no_data'] += 1
            continue
        
        price = data['price']
        prev_close = data['prev_close']
        volume = data['volume'] or 0
        
        if price <= 0 or prev_close <= 0:
            stats['no_data'] += 1
            continue
        
        # ====== Filters ======
        if price < MIN_PRICE or price > MAX_PRICE:
            continue
        stats['price_passed'] += 1
        
        gap_pct = ((price - prev_close) / prev_close) * 100
        if gap_pct < MIN_GAP_PCT or gap_pct > MAX_GAP_PCT:
            continue
        stats['gap_passed'] += 1
        
        if volume < MIN_AVG_VOLUME:
            continue
        stats['volume_passed'] += 1
        
        stats['final_passed'] += 1
        
        volume_ratio = volume / MIN_AVG_VOLUME if MIN_AVG_VOLUME > 0 else 1.0
        candidate = {
            'ticker': symbol,
            'price': price,
            'gap_pct': gap_pct,
            'prev_close': prev_close,
            'volume': volume,
            'dollar_volume': price * volume,
            'volume_ratio': volume_ratio,
            'pm_volume': volume,
            'pm_rvol': volume_ratio,
            'catalyst': '—',
        }
        candidates.append(candidate)
    
    # ====== סטטיסטיקות ======
    print("\n" + "="*50)
    print("📊 PREMARKET SCAN STATISTICS")
    print("="*50)
    print(f"Total Universe:        {stats['total']:,}")
    print(f"No Data:               {stats['no_data']:,}")
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
    if gap >= 5.0: score += 20
    elif gap >= 3.0: score += 15
    elif gap >= 2.0: score += 10
    elif gap >= 1.0: score += 5
    
    volume = candidate.get('volume', 0)
    if volume >= 1_000_000: score += 30
    elif volume >= 500_000: score += 25
    elif volume >= 200_000: score += 20
    elif volume >= 100_000: score += 15
    else: score += 5
    
    dvol = candidate.get('dollar_volume', 0)
    if dvol >= 5_000_000: score += 25
    elif dvol >= 1_000_000: score += 18
    elif dvol >= 500_000: score += 10
    elif dvol >= 250_000: score += 5
    return min(100, score)
