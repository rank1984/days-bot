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
        'volume_pass': 0,
        'gap_pass': 0,
        'float_pass': 0,
        'momentum_pass': 0,
        'final_pass': 0,
        'crypto_filtered': 0,
        'no_snapshot': 0,
        'no_trade': 0,
        'no_bar': 0,
    }
    
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
                    
                    # 5. סינון Float
                    float_shares = snapshot.float_shares if hasattr(snapshot, 'float_shares') else 0
                    if float_shares > 0 and float_shares > MAX_FLOAT:
                        stats['float_pass'] += 1
                        continue
                    stats['float_pass'] += 1
                    
                    # ====== עבר את כל הפילטרים ======
                    stats['final_pass'] += 1
                    
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
                        'float': float_shares,
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
    
    # ====== הדפס את 5 המובילים שנפסלו ======
    if scored:
        print("\n🏆 TOP 5 CANDIDATES:")
        for i, c in enumerate(scored[:5], 1):
            print(f"  {i}. {c['ticker']}  ${c['price']:.2f}  Gap: {c['gap_pct']:+.1f}%  Score: {c.get('score', 0):.0f}")
        print()
    
    return scored[:10]
