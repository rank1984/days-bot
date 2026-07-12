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
    Scan premarket for breakout candidates
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
    
    # Process in batches
    batch_size = 100
    for i in range(0, len(universe), batch_size):
        batch = universe[i:i+batch_size]
        symbols = [s['symbol'] for s in batch]
        
        try:
            # Get latest quotes/snapshot
            snapshots = api.get_snapshots(symbols)
            
            for symbol in symbols:
                try:
                    snapshot = snapshots.get(symbol)
                    if not snapshot:
                        continue
                    
                    # Extract data
                    latest_trade = snapshot.latest_trade
                    if not latest_trade:
                        continue
                    
                    price = latest_trade.price
                    volume = latest_trade.size
                    
                    # Get daily bar
                    daily_bar = snapshot.daily_bar
                    if not daily_bar:
                        continue
                    
                    prev_close = daily_bar.close
                    prev_volume = daily_bar.volume
                    
                    # Calculate gap
                    gap_pct = ((price - prev_close) / prev_close) * 100 if prev_close > 0 else 0
                    # אחרי השורה:
# gap_pct = ((price - prev_close) / prev_close) * 100 if prev_close > 0 else 0

# הוסף את זה:
# ====== סינון נפח מינימלי ======
# דילוג על מניות עם נפח קטן מ-50,000
if volume < 50_000:
    continue

# דילוג על מניות עם נפח ממוצע נמוך מ-100,000
if prev_volume < 100_000:
    continue
                    # Check gap filter
                    if gap_pct < MIN_GAP_PCT or gap_pct > MAX_GAP_PCT:
                        continue
                    
                    # Check price filter
                    if price < MIN_PRICE or price > MAX_PRICE:
                        continue
                    
                    # Check volume filter
                    if prev_volume < MIN_AVG_VOLUME:
                        continue
                    
                    # Get float
                    float_shares = snapshot.float_shares if hasattr(snapshot, 'float_shares') else 0
                    if float_shares > 0 and float_shares > MAX_FLOAT:
                        continue
                    
                    # Calculate RVOL
                    volume_ratio = prev_volume / MIN_AVG_VOLUME if MIN_AVG_VOLUME > 0 else 1.0
                    
                    # Calculate scores
                    freshness = 100 - (gap_pct * 2) if gap_pct > 0 else 50
                    momentum_score = 50 + (gap_pct * 0.5)
                    combined = (freshness + momentum_score) / 2
                    
                    # Build candidate
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
                    print(f"[Premarket] Error on {symbol}: {e}")
                    continue
            
            print(f"[Premarket] Processed {min(i+batch_size, len(universe))}/{len(universe)}")
            
        except Exception as e:
            print(f"[Premarket] Batch error: {e}")
            continue
    
    print(f"[Premarket] Found {len(candidates)} candidates before scoring")
    
    # Score candidates
    scored = []
    for c in candidates:
        score = calculate_breakout_score(c)
        if score >= MIN_SCORE:
            c['score'] = score
            scored.append(c)
    
    # Sort by score
    scored.sort(key=lambda x: x.get('score', 0), reverse=True)
    
    print(f"[Premarket] ✅ Found {len(scored)} qualified candidates")
    
    return scored[:10]  # Return top 10


def calculate_breakout_score(candidate: Dict[str, Any]) -> float:
    """
    Calculate breakout score for a candidate
    """
    score = 0
    
    # Gap (0-20 points) - smaller gap is better for pre-breakout
    gap = candidate.get('gap_pct', 0)
    if gap < 1.0:
        score += 20
    elif gap < 2.0:
        score += 15
    elif gap < 3.0:
        score += 10
    else:
        score += 5
    
    # Volume ratio (0-25 points)
    vol_ratio = candidate.get('volume_ratio', 1.0)
    if vol_ratio >= 2.0:
        score += 25
    elif vol_ratio >= 1.5:
        score += 18
    elif vol_ratio >= 1.2:
        score += 10
    else:
        score += 5
    
    # Float (0-20 points) - smaller is better
    float_shares = candidate.get('float', 0)
    if float_shares < 20_000_000:
        score += 20
    elif float_shares < 50_000_000:
        score += 12
    elif float_shares < 100_000_000:
        score += 5
    else:
        score += 2
    
    # Freshness (0-20 points)
    freshness = candidate.get('freshness', 0)
    if freshness >= 80:
        score += 20
    elif freshness >= 60:
        score += 14
    elif freshness >= 40:
        score += 8
    else:
        score += 4
    
    # Dollar volume (0-15 points)
    dvol = candidate.get('dollar_volume', 0)
    if dvol >= 1_000_000:
        score += 15
    elif dvol >= 500_000:
        score += 10
    elif dvol >= 250_000:
        score += 5
    else:
        score += 2
    
    return min(100, score)
