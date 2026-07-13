"""
Premarket scanner for DAYS-BOT - Using Alpaca
"""
import sys
import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))
sys.path.insert(0, str(BASE_DIR / "utils"))

import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import time
from typing import List, Dict, Any, Optional

from utils.config import *
from scanner.universe import load_universe
import alpaca_trade_api as tradeapi


def scan_premarket(date: str = None) -> List[Dict[str, Any]]:
    if date is None:
        date = datetime.now().strftime("%Y-%m-%d")
    
    print(f"[Premarket] Scanning for {date}...")
    
    universe = load_universe()
    if not universe:
        print("[Premarket] ❌ No universe found")
        return []
    
    print(f"[Premarket] Universe size: {len(universe)}")
    
    # ====== Alpaca API ======
    api = tradeapi.REST(
        ALPACA_API_KEY, 
        ALPACA_SECRET_KEY, 
        base_url='https://paper-api.alpaca.markets'
    )
    
    candidates = []
    
    # ====== סטטיסטיקות ======
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
        symbols = [s['symbol'] for s in batch]
        
        try:
            # ====== Alpaca Snapshot ======
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
                    prev_volume = daily_bar.volume
                    
                    # ====== Filters ======
                    # Price
                    if price < MIN_PRICE or price > MAX_PRICE:
                        continue
                    stats['price_passed'] += 1
                    
                    # Gap
                    gap_pct = ((price - prev_close) / prev_close) * 100 if prev_close > 0 else 0
                    if gap_pct < MIN_GAP_PCT or gap_pct > MAX_GAP_PCT:
                        continue
                    stats['gap_passed'] += 1
                    
                    # Volume
                    if prev_volume < MIN_AVG_VOLUME:
                        continue
                    stats['volume_passed'] += 1
                    
                    stats['final_passed'] += 1
                    
                    # ====== Candidate ======
                    volume_ratio = prev_volume / MIN_AVG_VOLUME if MIN_AVG_VOLUME > 0 else 1.0
                    freshness = 100 - (gap_pct * 2) if gap_pct > 0 else 50
                    momentum_score = 50 + (gap_pct * 0.5)
                    combined = (freshness + momentum_score) / 2
                    
                    candidate = {
                        'ticker': symbol,
                        'price': price,
                        'gap_pct': gap_pct,
                        'prev_close': prev_close,
                        'volume': prev_volume,
                        'avg_volume': prev_volume,
                        'volume_ratio': volume_ratio,
                        'dollar_volume': price * prev_volume,
                        'freshness': freshness,
                        'momentum_score': momentum_score,
                        'combined': combined,
                        'catalyst': '—',
                        'pm_high': price,
                        'pm_high_dist': gap_pct,
                        'pm_high_age': 0,
                        'pm_volume': prev_volume,
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
    # ====== DEBUG: הצג את 20 המניות הראשונות ======
debug_count = 0
for symbol in symbols[:20]:
    try:
        snapshot = snapshots.get(symbol)
        if snapshot and snapshot.latest_trade and snapshot.daily_bar:
            price = snapshot.latest_trade.price
            volume = snapshot.latest_trade.size
            prev_close = snapshot.daily_bar.close
            prev_volume = snapshot.daily_bar.volume
            gap = ((price - prev_close) / prev_close) * 100 if prev_close > 0 else 0
            print(f"[DEBUG] {symbol}: Price=${price:.2f}, Volume={volume:,}, PrevVol={prev_volume:,}, Gap={gap:.2f}%")
    except:
        pass
    # ====== סטטיסטיקות ======
    print("\n" + "="*50)
    print("📊 PREMARKET SCAN STATISTICS")
    print("="*50)
    print(f"Total Universe:        {stats['total']:,}")
    print(f"No Snapshot:           {stats['no_snapshot']:,}")
    print(f"No Trade:              {stats['no_trade']:,}")
    print(f"No Daily Bar:          {stats['no_bar']:,}")
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
