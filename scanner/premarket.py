"""
Premarket scanner for DAYS-BOT
"""
import sys
import os
from pathlib import Path

# הוסף את ספריית הבסיס ו-utils לנתיב
BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))
sys.path.insert(0, str(BASE_DIR / "utils"))

import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import time
from typing import List, Dict, Any, Optional

# Import from utils.config
from utils.config import *
from scanner.universe import load_universe
from scanner.news import get_catalyst_label
import alpaca_trade_api as tradeapi


def scan_premarket(date: str = None) -> List[Dict[str, Any]]:
    """
    Scan premarket for breakout candidates with detailed statistics
    """
    if date is None:
        date = datetime.now().strftime("%Y-%m-%d")
    
    print(f"[Premarket] Scanning for {date}...")
    
    # Load universe
    universe = load_universe()
    if not universe:
        print("[Premarket] ❌ No universe found")
        return []
    
    print(f"[Premarket] Universe size: {len(universe)}")
    
    # Initialize Alpaca
    api = tradeapi.REST(
        ALPACA_API_KEY, 
        ALPACA_SECRET_KEY, 
        base_url='https://paper-api.alpaca.markets'
    )
    
    candidates = []
    
    # ====== סטטיסטיקות סינון ======
    stats = {
        'total': len(universe),
        'price_pass': 0,
        'gap_pass': 0,
        'volume_pass': 0,
        'float_pass': 0,
        'final_pass': 0,
        'crypto_filtered': 0,
        'no_snapshot': 0,
        'no_trade': 0,
        'no_bar': 0,
    }
    
    # ====== DEBUG: בדיקת Float ======
    debug_float_samples = []
    
    # Process in batches
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
                    volume = latest_trade.size
                    
                    daily_bar = snapshot.daily_bar
                    if not daily_bar:
                        stats['no_bar'] += 1
                        continue
                    
                    prev_close = daily_bar.close
                    prev_volume = daily_bar.volume
                    
                    # ====== DEBUG: בדיקת Float ======
                    if len(debug_float_samples) < 20:
                        float_val = snapshot.float_shares if hasattr(snapshot, 'float_shares') else 'NO_ATTR'
                        debug_float_samples.append({
                            'symbol': symbol,
                            'float': float_val,
                            'has_attr': hasattr(snapshot, 'float_shares'),
                            'price': price,
                            'volume': volume
                        })
                  # 5. סינון Float
print(f"[DEBUG] {symbol} - entering float filter")
float_shares = None
if hasattr(snapshot, 'float_shares'):
    float_shares = snapshot.float_shares
    print(f"[DEBUG] {symbol} - float_shares = {float_shares}")
else:
    print(f"[DEBUG] {symbol} - no float_shares attribute")

if float_shares is not None and float_shares > 0:
    if float_shares > MAX_FLOAT:
        stats['float_pass'] += 1
        print(f"[DEBUG] {symbol} - float too high, filtered")
        continue
# אם אין Float - אל תפסול
print(f"[DEBUG] {symbol} - passed float filter")
stats['float_pass'] += 1  
           # ====== סינון ======
# 1. דילוג על קריפטו
if '/' in symbol or 'USDC' in symbol or 'USDT' in symbol:
    stats['crypto_filtered'] += 1
    continue

# 2. סינון Price
if price < MIN_PRICE or price > MAX_PRICE:
    stats['price_pass'] += 1
    continue
stats['price_pass'] += 1

# 3. סינון Gap
gap_pct = ((price - prev_close) / prev_close) * 100 if prev_close > 0 else 0
if gap_pct < MIN_GAP_PCT or gap_pct > MAX_GAP_PCT:
    stats['gap_pass'] += 1
    continue
stats['gap_pass'] += 1

# 4. סינון נפח
if volume < 50_000 or prev_volume < 100_000:
    stats['volume_pass'] += 1
    continue
stats['volume_pass'] += 1

# 5. סינון Float - רק אם יש נתון תקף
float_shares = None
if hasattr(snapshot, 'float_shares'):
    float_shares = snapshot.float_shares

# אם יש Float - תבדוק אותו
if float_shares is not None and float_shares > 0:
    if float_shares > MAX_FLOAT:
        stats['float_pass'] += 1
        continue
# אם אין Float - אל תפסול (תעבור הלאה)

stats['float_pass'] += 1   # <--- השורה הזו אמורה להתבצע

# ====== עבר את כל הפילטרים ======
stats['final_pass'] += 1

# ... build candidate ...
candidates.append(candidate)
                    
                    # Calculate scores
                    freshness = 100 - (gap_pct * 2) if gap_pct > 0 else 50
                    momentum_score = 50 + (gap_pct * 0.5)
                    combined = (freshness + momentum_score) / 2
                    volume_ratio = prev_volume / MIN_AVG_VOLUME if MIN_AVG_VOLUME > 0 else 1.0
                    
                    candidate = {
                        'ticker': symbol,
                        'price': price,
                        'gap_pct': gap_pct,
                        'prev_close': prev_close,
                        'volume': volume,
                        'avg_volume': prev_volume,
                        'volume_ratio': volume_ratio,
                        'float': float_shares if float_shares is not None else 0,
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
                    continue
            
            print(f"[Premarket] Processed {min(i+batch_size, len(universe))}/{len(universe)}")
            
        except Exception as e:
            print(f"[Premarket] Batch error: {e}")
            continue
    
    # ====== הדפסת בדיקת Float ======
    print("\n🔍 FLOAT DEBUG SAMPLES (first 20):")
    print("-" * 60)
    for s in debug_float_samples[:20]:
        print(f"  {s['symbol']:10} | Float: {str(s['float']):15} | HasAttr: {s['has_attr']} | Price: ${s['price']:.2f}")
    print("-" * 60)
    
    # ====== הדפסת סטטיסטיקות ======
    print("\n" + "="*50)
    print("📊 PREMARKET SCAN STATISTICS")
    print("="*50)
    print(f"Total Universe:        {stats['total']:,}")
    print(f"Crypto Filtered:       {stats['crypto_filtered']:,}")
    print(f"No Snapshot:           {stats['no_snapshot']:,}")
    print(f"No Trade:              {stats['no_trade']:,}")
    print(f"No Daily Bar:          {stats['no_bar']:,}")
    print("-"*50)
    print(f"✅ Price Pass:          {stats['price_pass']:,}")
    print(f"✅ Gap Pass:            {stats['gap_pass']:,}")
    print(f"✅ Volume Pass:         {stats['volume_pass']:,}")
    print(f"✅ Float Pass:          {stats['float_pass']:,}")
    print("-"*50)
    print(f"🎯 FINAL CANDIDATES:    {stats['final_pass']:,}")
    print("="*50 + "\n")
    
    # Score candidates
    scored = []
    for c in candidates:
        score = calculate_breakout_score(c)
        if score >= MIN_SCORE:
            c['score'] = score
            scored.append(c)
    
    scored.sort(key=lambda x: x.get('score', 0), reverse=True)
    
    print(f"[Premarket] ✅ Found {len(scored)} qualified candidates")
    
    # ====== הדפס את 5 המובילים ======
    if scored:
        print("\n🏆 TOP 5 CANDIDATES:")
        for i, c in enumerate(scored[:5], 1):
            print(f"  {i}. {c['ticker']}  ${c['price']:.2f}  Gap: {c['gap_pct']:+.1f}%  Score: {c.get('score', 0):.0f}")
        print()
    
    return scored[:10]


def calculate_breakout_score(candidate: Dict[str, Any]) -> float:
    """
    Calculate breakout score for a candidate
    """
    score = 0
    
    # Gap (0-20 points)
    gap = candidate.get('gap_pct', 0)
    if gap >= 5.0:
        score += 20
    elif gap >= 3.0:
        score += 15
    elif gap >= 2.0:
        score += 10
    elif gap >= 1.0:
        score += 5
    
    # Volume (0-30 points)
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
    
    # Float (0-25 points) - only if we have data
    float_shares = candidate.get('float', 0)
    if float_shares > 0:
        if float_shares < 20_000_000:
            score += 25
        elif float_shares < 50_000_000:
            score += 18
        elif float_shares < 100_000_000:
            score += 10
        else:
            score += 3
    else:
        # No float data - give average score
        score += 10
    
    # Dollar volume (0-25 points)
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
