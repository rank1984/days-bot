"""
Premarket scanner for DAYS-BOT - Optimized Execution
"""
import sys
import os
import json
from pathlib import Path
from datetime import datetime
from typing import List, Dict, Any
import yfinance as yf
import alpaca_trade_api as tradeapi

BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))
sys.path.insert(0, str(BASE_DIR / "utils"))

from utils.config import *
from scanner.universe import load_universe

try:
    from scanner.news_scanner import score_news_quality, get_catalyst_news_score
except ImportError:
    def score_news_quality(news): return 0.0
    def get_catalyst_news_score(symbol): return 0.0, "—"

# ====== Volume Trend Management ======
VOLUME_TREND_FILE = os.path.join(BASE_DIR, "data", "volume_trend.json")

def load_volume_trend() -> Dict[str, Any]:
    if os.path.exists(VOLUME_TREND_FILE):
        try:
            with open(VOLUME_TREND_FILE, 'r') as f:
                return json.load(f)
        except Exception:
            return {}
    return {}

def save_volume_trend(data: Dict[str, Any]) -> None:
    try:
        os.makedirs(os.path.dirname(VOLUME_TREND_FILE), exist_ok=True)
        with open(VOLUME_TREND_FILE, 'w') as f:
            json.dump(data, f, indent=2)
    except Exception as e:
        print(f"[Volume Trend] Error saving data: {e}")

# ====== Market Strength ======
_market_cache = None

def get_market_strength() -> float:
    global _market_cache
    if _market_cache is not None:
        return _market_cache
    try:
        data = yf.download(["SPY", "QQQ"], period="2d", progress=False, timeout=5)
        if not data.empty and 'Close' in data:
            spy_close = data['Close']['SPY']
            qqq_close = data['Close']['QQQ']
            
            spy_change = ((spy_close.iloc[-1] - spy_close.iloc[-2]) / spy_close.iloc[-2]) * 100
            qqq_change = ((qqq_close.iloc[-1] - qqq_close.iloc[-2]) / qqq_close.iloc[-2]) * 100
            
            _market_cache = (spy_change + qqq_change) / 2.0
            return _market_cache
    except Exception:
        pass
    _market_cache = 0.0
    return _market_cache

# ====== Alpaca Snapshot Caching ======
SNAPSHOT_CACHE = {}

def get_snapshots_cached(api, symbols: List[str]):
    key = ",".join(sorted(symbols))
    if key in SNAPSHOT_CACHE:
        return SNAPSHOT_CACHE[key]
    data = api.get_snapshots(symbols)
    SNAPSHOT_CACHE[key] = data
    return data

def get_catalyst(symbol: str) -> str:
    try:
        _, catalyst_text = get_catalyst_news_score(symbol)
        return catalyst_text if catalyst_text else "—"
    except Exception:
        return "—"

def calculate_breakout_score(candidate: Dict[str, Any]) -> float:
    score = candidate.get('score_bonus', 0) + candidate.get('float_score', 0)
    
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
    
    return min(100.0, max(0.0, float(score)))

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
    volume_trend_data = load_volume_trend()
    
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
            snapshots = get_snapshots_cached(api, symbols)
            for symbol in symbols:
                try:
                    snapshot = snapshots.get(symbol)
                    if not snapshot:
                        stats['no_snapshot'] += 1
                        continue
                    
                    latest_trade = snapshot.latest_trade
                    if not latest_trade or not getattr(latest_trade, 'price', None):
                        stats['no_trade'] += 1
                        continue
                    
                    price = float(latest_trade.price)
                    daily_bar = snapshot.daily_bar
                    prev_daily_bar = getattr(snapshot, 'prev_daily_bar', None)
                    
                    if not daily_bar:
                        stats['no_bar'] += 1
                        continue
                    
                    prev_close = prev_daily_bar.close if prev_daily_bar else daily_bar.open
                    volume = daily_bar.volume
                    prev_volume = prev_daily_bar.volume if prev_daily_bar else MIN_AVG_VOLUME

                    # 1. Price Filter
                    if price < MIN_PRICE or price > MAX_PRICE:
                        continue
                    stats['price_passed'] += 1
                    
                    # 2. Gap % Filter
                    gap_pct = ((price - prev_close) / prev_close) * 100 if prev_close and prev_close > 0 else 0
                    if gap_pct < MIN_GAP_PCT or gap_pct > MAX_GAP_PCT:
                        continue
                    stats['gap_passed'] += 1

                    # 3. Volume Filter
                    if volume < MIN_AVG_VOLUME:
                        continue
                    stats['volume_passed'] += 1

                    # ====== Spread Filter ======
                    bid = getattr(snapshot, 'bid_price', None) or getattr(getattr(snapshot, 'latest_quote', None), 'bid_price', None)
                    ask = getattr(snapshot, 'ask_price', None) or getattr(getattr(snapshot, 'latest_quote', None), 'ask_price', None)
                    if bid and ask and bid > 0 and price > 0:
                        spread_pct = ((ask - bid) / price) * 100
                        if spread_pct > 3.0:
                            print(f"[Spread] {symbol}: spread={spread_pct:.1f}%. Skipping.")
                            continue

                    # Relative Strength Filter
                    market_change = get_market_strength()
                    rs_val = gap_pct - market_change
                    if gap_pct < market_change + 2:
                        continue
                        
                    # PM High Distance Calculation
                    pm_high = price
                    if daily_bar and getattr(daily_bar, 'high', price) > price:
                        pm_high = daily_bar.high
                        
                    pm_high_dist = ((pm_high - price) / pm_high) * 100 if pm_high > price else 0
                    
                    score_bonus = 0
                    if pm_high_dist <= 1: score_bonus = 15
                    elif pm_high_dist <= 2: score_bonus = 10
                    elif pm_high_dist <= 4: score_bonus = 5
                    elif pm_high_dist <= 7: score_bonus = 0
                    else: continue

                    # Float Scoring
                    float_shares = 0
                    for item in batch:
                        if item.get('symbol') == symbol:
                            float_shares = item.get('float', 0)
                            break
                            
                    float_score = 0
                    if float_shares > 0:
                        if float_shares < 15_000_000:
                            float_score = 10
                        elif float_shares < 30_000_000:
                            float_score = 5

                    # Volume Trend Tracking (נשמר בזיכרון)
                    if symbol not in volume_trend_data:
                        volume_trend_data[symbol] = []
                    volume_trend_data[symbol].append({'time': datetime.now().isoformat(), 'volume': volume})
                    volume_trend_data[symbol] = volume_trend_data[symbol][-4:]
                    
                    trend_status = 'rising'
                    trend = volume_trend_data.get(symbol, [])
                    if len(trend) >= 3:
                        vols = [t['volume'] for t in trend[-3:]]
                        if vols[0] > vols[1] > vols[2]:
                            trend_status = 'declining'

                    rvol = volume / prev_volume if prev_volume > 0 else 1.0
                    stats['rvol_passed'] += 1
                    
                    dollar_volume = price * volume
                    stats['dvol_passed'] += 1
                    stats['final_passed'] += 1

                    volume_ratio = volume / prev_volume if prev_volume > 0 else 1.0
                    atr = price * 0.04
                    
                    catalyst_text = get_catalyst(symbol)
                    news_score = score_news_quality([catalyst_text])
                    momentum_score = min(100.0, max(0.0, gap_pct * 2 + rvol * 10))
                    
                    spread_estimate = (ask - bid) if (bid and ask) else (0.005 * price)
                    liquidity_score = min(100, (dollar_volume / 1_000_000) * 20 - (spread_estimate / price) * 100)
                    liquidity_score = max(0, liquidity_score)
                    
                    if bid and ask and price > 0:
                        spread_pct = ((ask - bid) / price) * 100
                    else:
                        spread_pct = 0.5
                    
                    candidate = {
                        'ticker': symbol,
                        'price': price,
                        'gap_pct': gap_pct,
                        'prev_close': prev_close,
                        'volume': volume,
                        'avg_volume': prev_volume,
                        'volume_ratio': volume_ratio,
                        'rvol': rvol,
                        'float': float_shares,
                        'float_score': float_score,
                        'dollar_volume': dollar_volume,
                        'freshness': "FRESH",
                        'momentum_score': momentum_score,
                        'combined': momentum_score,
                        'catalyst': catalyst_text,
                        'news_score': news_score,
                        'pm_high': pm_high,
                        'pm_high_dist': pm_high_dist,
                        'score_bonus': score_bonus,
                        'volume_trend': trend_status,
                        'relative_strength': rs_val,
                        'liquidity_score': liquidity_score,
                        'atr': atr,
                        'score': 0.0,
                        'pm_volume': volume,
                        'pm_rvol': volume_ratio,
                        'vwap_dist': 0,
                        'vol_accel': 1.0,
                        'momentum_5m': gap_pct * 0.1,
                        'bid': bid if bid else 0,
                        'ask': ask if ask else 0,
                        'spread_pct': spread_pct,
                        'spread_estimate': spread_estimate,
                    }
                    candidates.append(candidate)
                    
                except Exception:
                    continue
            
        except Exception:
            continue
            
    # שמירת נתוני מגמת הנפח בסיום הסריקה במרוכז
    save_volume_trend(volume_trend_data)
    
    print(f"\n[DEBUG] Total Universe: {stats['total']}")
    print(f"[DEBUG] Price Passed:  {stats['price_passed']}")
    print(f"[DEBUG] Gap Passed:    {stats['gap_passed']}")
    print(f"[DEBUG] Volume Passed: {stats['volume_passed']}")
    print(f"[DEBUG] Final Passed:  {stats['final_passed']}")
    
    scored = []
    for c in candidates:
        score = calculate_breakout_score(c)
        if score >= MIN_SCORE:
            c['score'] = score
            scored.append(c)
    
    scored.sort(key=lambda x: x.get('score', 0.0), reverse=True)
    return scored[:10]
