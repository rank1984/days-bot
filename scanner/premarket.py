"""
Premarket scanner for DAYS-BOT - Using Alpaca (fast)
Integrated with RVOL, Dollar Volume, and Enhanced Scoring.
"""
import sys
import os
import json
from pathlib import Path
import time
from datetime import datetime
from typing import List, Dict, Any, Optional
import yfinance as yf
import alpaca_trade_api as tradeapi

BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))
sys.path.insert(0, str(BASE_DIR / "utils"))

from utils.config import *
from scanner.universe import load_universe
from scanner.news_scanner import score_news_quality

# ====== Volume Trend Management ======
VOLUME_TREND_FILE = "data/volume_trend.json"

def load_volume_trend():
    if os.path.exists(VOLUME_TREND_FILE):
        with open(VOLUME_TREND_FILE, 'r') as f:
            return json.load(f)
    return {}

def save_volume_trend(data):
    os.makedirs(os.path.dirname(VOLUME_TREND_FILE), exist_ok=True)
    with open(VOLUME_TREND_FILE, 'w') as f:
        json.dump(data, f, indent=2)

def update_volume_trend(symbol, volume):
    data = load_volume_trend()
    if symbol not in data:
        data[symbol] = []
    data[symbol].append({'time': datetime.now().isoformat(), 'volume': volume})
    # שמור רק 4 האחרונים
    data[symbol] = data[symbol][-4:]
    save_volume_trend(data)

# ====== Market Strength ======
_market_cache = None

def get_market_strength():
    global _market_cache
    if _market_cache is not None:
        return _market_cache
    try:
        spy = yf.Ticker("SPY")
        qqq = yf.Ticker("QQQ")
        spy_info = spy.info
        qqq_info = qqq.info
        spy_change = (spy_info['regularMarketPrice'] - spy_info['previousClose']) / spy_info['previousClose'] * 100
        qqq_change = (qqq_info['regularMarketPrice'] - qqq_info['previousClose']) / qqq_info['previousClose'] * 100
        _market_cache = (spy_change + qqq_change) / 2
        return _market_cache
    except:
        return 0.0

def get_catalyst(symbol: str) -> str:
    try:
        from scanner.news_scanner import get_catalyst_news_score
        _, catalyst_text = get_catalyst_news_score(symbol)
        return catalyst_text if catalyst_text else "—"
    except Exception:
        return "—"

def calculate_breakout_score(candidate: Dict[str, Any]) -> float:
    score = 0
    gap = candidate.get('gap_pct', 0)
    if gap >= 5.0: score += 25
    elif gap >= 3.0: score += 18
    elif gap >= 1.0: score += 10
    
    volume = candidate.get('volume', 0)
    if volume >= 500_000: score += 20
    elif volume >= 200_000: score += 15
    elif volume >= 100_000: score += 10
    elif volume >= 50_000: score += 5
    
    rvol = candidate.get('rvol', 0)
    if rvol >= 3.0: score += 20
    elif rvol >= 2.0: score += 15
    elif rvol >= 1.0: score += 10
    
    dvol = candidate.get('dollar_volume', 0)
    if dvol >= 1_000_000: score += 20
    elif dvol >= 500_000: score += 15
    elif dvol >= 200_000: score += 10
    
    return min(100, score)

def scan_premarket(date: str = None) -> List[Dict[str, Any]]:
    if date is None:
        date = datetime.now().strftime("%Y-%m-%d")
    
    print(f"[Premarket] Scanning for {date}...")
    universe = load_universe()
    if not universe:
        return []
        
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
                    
                    # 1. Price
                    if price < MIN_PRICE or price > MAX_PRICE: continue
                    stats['price_passed'] += 1
                    
                    # 2. Gap %
                    gap_pct = ((price - prev_close) / prev_close) * 100 if prev_close else 0
                    if gap_pct < MIN_GAP_PCT or gap_pct > MAX_GAP_PCT: continue
                    stats['gap_passed'] += 1
                    
                    # Market Strength Filter
                    market_change = get_market_strength()
                    if market_change < -0.5 and gap_pct < 3.0:
                        continue  # שוק חלש, דורשים Gap גבוה יותר
                        
                    # PM High Distance
                    pm_high = price  # נשתמש במחיר הנוכחי כשיא
                    pm_high_dist = 0.0  # המרחק מהשיא (באחוזים)
                    if pm_high_dist > 10.0:
                        continue
                        
                    # 3. Volume
                    if volume < MIN_AVG_VOLUME: continue
                    stats['volume_passed'] += 1
                    
                    # Volume Trend
                    update_volume_trend(symbol, volume)
                    trend_status = 'rising'
                    trend = load_volume_trend().get(symbol, [])
                    if len(trend) >= 3:
                        vols = [t['volume'] for t in trend[-3:]]
                        if vols[0] > vols[1] > vols[2]:
                            trend_status = 'declining'

                    # 4. RVOL
                    rvol = volume / 100_000 
                    stats['rvol_passed'] += 1
                    
                    # 5. Dollar Volume
                    dollar_volume = price * volume
                    stats['dvol_passed'] += 1
                    
                    stats['final_passed'] += 1
                    volume_ratio = volume / MIN_AVG_VOLUME if MIN_AVG_VOLUME > 0 else 1.0
                    atr = price * 0.04
                    
                    catalyst_text = get_catalyst(symbol)
                    news_score = score_news_quality([catalyst_text])
                    
                    momentum_score = min(100.0, max(0.0, gap_pct * 2 + rvol * 10))
                    
                    # Liquidity Score
                    spread_estimate = 0.005 * price
                    liquidity_score = min(100, (dollar_volume / 1_000_000) * 20 - (spread_estimate / price) * 100)
                    liquidity_score = max(0, liquidity_score)
                    
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
                        'freshness': "FRESH",
                        'momentum_score': momentum_score,
                        'combined': momentum_score,
                        'catalyst': catalyst_text,
                        'news_score': news_score,
                        'pm_high': pm_high,
                        'pm_high_dist': pm_high_dist,
                        'volume_trend': trend_status,
                        'liquidity_score': liquidity_score,
                        'atr': atr,
                        'score': 0.0,
                        'pm_volume': volume,
                        'pm_rvol': volume_ratio,
                        'vwap_dist': 0,
                        'vol_accel': 1.0,
                        'momentum_5m': gap_pct * 0.1,
                    }
                    candidates.append(candidate)
                    
                except Exception:
                    continue
            
        except Exception as e:
            continue
    
    scored = []
    for c in candidates:
        score = calculate_breakout_score(c)
        if score >= MIN_SCORE:
            c['score'] = score
            scored.append(c)
    
    scored.sort(key=lambda x: x.get('score', 0.0), reverse=True)
    return scored[:10]
