"""
Premarket scanner - updated with new data source and scoring
"""
import sys
import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))
sys.path.insert(0, str(BASE_DIR / "utils"))

from datetime import datetime
from typing import List, Dict, Any

from utils.config import *
from scanner.universe import load_universe
from scanner.scorer import calculate_score, get_news_score
from scanner.news_scanner import NewsScanner
from utils.data_fetcher import PolygonDataFetcher


def scan_premarket(date: str = None) -> List[Dict[str, Any]]:
    if date is None:
        date = datetime.now().strftime("%Y-%m-%d")
    
    print(f"[Premarket] Scanning for {date}...")
    
    universe = load_universe()
    if not universe:
        print("[Premarket] ❌ No universe found")
        return []
    
    print(f"[Premarket] Universe size: {len(universe)}")
    
    # Use Polygon for premarket data
    fetcher = PolygonDataFetcher()
    news_scanner = NewsScanner()
    
    candidates = []
    
    batch_size = 100
    for i in range(0, len(universe), batch_size):
        batch = universe[i:i+batch_size]
        symbols = [s['symbol'] for s in batch]
        
        # Get premarket data from Polygon
        pre_data = fetcher.get_premarket_snapshot(symbols)
        
        for symbol in symbols:
            data = pre_data.get(symbol)
            if not data:
                continue
            
            price = data.get('price', 0)
            volume = data.get('volume', 0)
            gap = data.get('change_pct', 0)
            prev_close = data.get('prev_close', 0)
            high = data.get('high', 0)
            vwap = data.get('vwap', 0)
            
            # ====== FILTERS ======
            if price < MIN_PRICE or price > MAX_PRICE:
                continue
            
            if gap < MIN_GAP_PCT or gap > MAX_GAP_PCT:
                continue
            
            if volume < MIN_PREMARKET_VOL:
                continue
            
            dollar_vol = price * volume
            if dollar_vol < MIN_DOLLAR_VOLUME:
                continue
            
            # Relative Volume (simplified - need historical avg)
            # For now, use a placeholder
            rvol = volume / 100_000  # rough estimate
            
            # ====== NEWS ======
            catalyst = news_scanner.get_catalyst(symbol)
            news_score = get_news_score([catalyst])
            
            # ====== SCORE ======
            candidate = {
                'ticker': symbol,
                'price': price,
                'gap_pct': gap,
                'prev_close': prev_close,
                'volume': volume,
                'pm_volume': volume,
                'dollar_volume': dollar_vol,
                'relative_volume': rvol,
                'pm_high': high,
                'pm_high_dist': ((high - price) / price * 100) if price > 0 else 0,
                'vwap': vwap,
                'vwap_dist': ((price - vwap) / vwap * 100) if vwap > 0 else 0,
                'catalyst': catalyst,
            }
            
            score_result = calculate_score(candidate, news_score=news_score)
            candidate['score'] = score_result['total']
            candidate['grade'] = score_result['grade']
            candidate['breakdown'] = score_result['breakdown']
            
            if candidate['score'] >= MIN_SCORE:
                candidates.append(candidate)
        
        print(f"[Premarket] Processed {min(i+batch_size, len(universe))}/{len(universe)}")
    
    # Sort by score
    candidates.sort(key=lambda x: x.get('score', 0), reverse=True)
    
    print(f"[Premarket] ✅ Found {len(candidates)} qualified candidates")
    
    if candidates:
        print("\n🏆 TOP 5 CANDIDATES:")
        for i, c in enumerate(candidates[:5], 1):
            print(f"  {i}. {c['ticker']}  ${c['price']:.2f}  Gap: {c['gap_pct']:+.1f}%  Score: {c['score']:.0f}  {c['grade']}")
        print()
    
    return candidates[:10]
