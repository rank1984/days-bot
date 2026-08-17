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
    from scanner.news_scanner import score_news_quality, get_catalyst_news_score, classify_catalyst
except ImportError:
    def score_news_quality(news): return 0.0
    def get_catalyst_news_score(symbol): return 0.0, "—"
    def classify_catalyst(headlines): return {"type": "UNKNOWN", "score": 0, "headline": "", "quality": "LOW"}

try:
    from scanner.risk_analyzer import analyze_dilution_risk
except ImportError:
    def analyze_dilution_risk(catalyst):
        return {'dilution_risk': 'LOW', 'risk_score': 0, 'red_flags': []}

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

                    # Float Shares Retrieval
                    float_shares = 0
                    for item in batch:
                        if item.get('symbol') == symbol:
                            float_shares = item.get('float', 0)
                            break

                    # Volume Trend Tracking
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
                    
                    if bid and ask and price > 0:
                        spread_pct = ((ask - bid) / price) * 100
                    else:
                        spread_pct = 0.5
                    
                    spread_estimate = (ask - bid) if (bid and ask) else (0.005 * price)

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
                        'dollar_volume': dollar_volume,
                        'catalyst': catalyst_text,
                        'news_score': news_score,
                        'pm_high': pm_high,
                        'pm_high_dist': pm_high_dist,
                        'volume_trend': trend_status,
                        'relative_strength': rs_val,
                        'atr': atr,
                        'bid': bid if bid else 0,
                        'ask': ask if ask else 0,
                        'spread_pct': spread_pct,
                        'spread_estimate': spread_estimate,
                    }

                    # ====== EVENT SCORE CALCULATION ======
                    # 1. RVOL Score
                    rvol_score = 0
                    if rvol >= 250: rvol_score = 60
                    elif rvol >= 100: rvol_score = 50
                    elif rvol >= 50: rvol_score = 40
                    elif rvol >= 20: rvol_score = 30
                    elif rvol >= 10: rvol_score = 20
                    elif rvol >= 5: rvol_score = 10
                    elif rvol >= 2: rvol_score = 5

                    # 2. Float Turnover
                    float_turnover = (volume / float_shares) if float_shares > 0 else None
                    float_turnover_score = 0
                    if float_turnover is not None:
                        if float_turnover >= 20: float_turnover_score = 30
                        elif float_turnover >= 10: float_turnover_score = 25
                        elif float_turnover >= 5: float_turnover_score = 20
                        elif float_turnover >= 3: float_turnover_score = 15
                        elif float_turnover >= 1: float_turnover_score = 10
                        elif float_turnover >= 0.5: float_turnover_score = 5

                    # 3. Low Float Score
                    float_score = 0
                    if float_shares > 0:
                        if float_shares < 1_000_000: float_score = 20
                        elif float_shares < 3_000_000: float_score = 18
                        elif float_shares < 5_000_000: float_score = 15
                        elif float_shares < 10_000_000: float_score = 10
                        elif float_shares < 20_000_000: float_score = 5

                    # 4. Gap Score
                    gap_score = 0
                    if gap_pct >= 20: gap_score = 25
                    elif gap_pct >= 10: gap_score = 20
                    elif gap_pct >= 5: gap_score = 15
                    elif gap_pct >= 3: gap_score = 10
                    elif gap_pct >= 1: gap_score = 5

                    # 5. Liquidity Score
                    liquidity_score = 0
                    if spread_pct <= 1: liquidity_score = 10
                    elif spread_pct <= 2: liquidity_score = 5
                    elif spread_pct <= 3: liquidity_score = 2

                    # 6. Catalyst Score
                    catalyst_score = 0
                    if 'fda' in catalyst_text.lower() or 'approval' in catalyst_text.lower():
                        catalyst_score = 5
                    elif 'contract' in catalyst_text.lower() or 'acquisition' in catalyst_text.lower():
                        catalyst_score = 4
                    elif 'earnings' in catalyst_text.lower():
                        catalyst_score = 3
                    else:
                        catalyst_score = 1 if catalyst_text != '—' else 0

                    # Total Event Score computation
                    event_score = 0
                    event_score += rvol_score
                    if float_turnover_score > 0:
                        event_score += float_turnover_score
                    else:
                        event_score += 10  # compensation for unknown float
                    event_score += float_score
                    event_score += gap_score
                    event_score += liquidity_score
                    event_score += catalyst_score
                    event_score = min(100, max(0, event_score))

                    # ====== Risk ======
                    risk_result = analyze_dilution_risk(catalyst_text)
                    risk_penalty = 0
                    if risk_result['dilution_risk'] == 'LOW': risk_penalty = 0
                    elif risk_result['dilution_risk'] == 'MEDIUM': risk_penalty = 5
                    elif risk_result['dilution_risk'] == 'HIGH': risk_penalty = 15
                    elif risk_result['dilution_risk'] == 'CRITICAL': risk_penalty = 30

                    final_event_score = max(0, event_score - risk_penalty)

                    # ====== Setup Grade ======
                    if final_event_score >= 85 and rvol >= 20 and spread_pct <= 2 and float_shares > 0 and float_turnover is not None and float_turnover >= 3 and risk_result['dilution_risk'] != 'CRITICAL':
                        grade = "A+"
                    elif final_event_score >= 75 and rvol >= 10:
                        grade = "A"
                    elif final_event_score >= 60:
                        grade = "B"
                    elif final_event_score >= 45:
                        grade = "C"
                    elif final_event_score >= 30:
                        grade = "WATCH"
                    else:
                        grade = "REJECT"

                    candidate.update({
                        'rvol_score': rvol_score,
                        'float_turnover': float_turnover,
                        'float_turnover_score': float_turnover_score,
                        'float_score': float_score,
                        'gap_score': gap_score,
                        'liquidity_score': liquidity_score,
                        'catalyst_score': catalyst_score,
                        'event_score': final_event_score,
                        'setup_grade': grade,
                        'dilution_risk': risk_result['dilution_risk'],
                        'risk_score': risk_result['risk_score'],
                        'red_flags': json.dumps(risk_result['red_flags']) if isinstance(risk_result['red_flags'], list) else str(risk_result['red_flags']),
                        'float_shares': float_shares,
                        'spread_pct': spread_pct,
                        'score': final_event_score
                    })

                    candidates.append(candidate)
                    
                except Exception:
                    continue
        except Exception:
            continue
            
    save_volume_trend(volume_trend_data)
    
    candidates.sort(key=lambda x: x.get('score', 0.0), reverse=True)
    return candidates[:10]
