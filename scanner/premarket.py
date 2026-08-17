"""
Premarket scanner for DAYS-BOT - Optimized Execution (V2 Engine + Float Provider)
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

# imports
from scanner.risk_engine import analyze_dilution_risk
from scanner.news_scanner import classify_catalyst, get_catalyst_news_score
from scanner.float_provider import get_float_shares

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
                        continue
                    
                    latest_trade = snapshot.latest_trade
                    if not latest_trade or not getattr(latest_trade, 'price', None):
                        continue
                    
                    price = float(latest_trade.price)
                    daily_bar = getattr(snapshot, 'daily_bar', None)
                    prev_daily_bar = getattr(snapshot, 'prev_daily_bar', None)
                    
                    if not daily_bar:
                        continue
                    
                    prev_close = prev_daily_bar.close if prev_daily_bar else daily_bar.open
                    volume = daily_bar.volume
                    prev_volume = prev_daily_bar.volume if prev_daily_bar else MIN_AVG_VOLUME

                    # 1. Price Filter
                    if price < MIN_PRICE or price > MAX_PRICE:
                        continue
                    
                    # 2. Gap % Filter
                    gap_pct = ((price - prev_close) / prev_close) * 100 if prev_close and prev_close > 0 else 0
                    if gap_pct < MIN_GAP_PCT or gap_pct > MAX_GAP_PCT:
                        continue

                    # 3. Volume Filter
                    if volume < MIN_AVG_VOLUME:
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

                    # ====== Float ======
                    float_shares = get_float_shares(symbol)
                    if float_shares is None:
                        float_shares = 0

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
                    dollar_volume = price * volume
                    volume_ratio = volume / prev_volume if prev_volume > 0 else 1.0
                    atr = price * 0.04
                    catalyst_text = get_catalyst(symbol)
                    
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
                        'float_shares': float_shares,
                        'dollar_volume': dollar_volume,
                        'catalyst': catalyst_text,
                        'pm_high': pm_high,
                        'pm_high_dist': pm_high_dist,
                        'volume_trend': trend_status,
                        'relative_strength': rs_val,
                        'atr': atr
                    }

                    # ==========================================================
                    # DAYS-BOT V2 EVENT ENGINE
                    # ==========================================================
                    rvol = candidate.get("rvol", 0.0)
                    gap = candidate.get("gap_pct", 0.0)
                    volume = candidate.get("volume", 0)
                    float_shares = candidate.get("float_shares", 0)

                    # ----------------------------------------------------------
                    # Spread
                    # ----------------------------------------------------------
                    bid = 0
                    ask = 0
                    if hasattr(snapshot, 'bid_price') and snapshot.bid_price:
                        bid = snapshot.bid_price
                    if hasattr(snapshot, 'ask_price') and snapshot.ask_price:
                        ask = snapshot.ask_price
                    if bid and ask and price > 0:
                        spread_pct = ((ask - bid) / price) * 100
                    else:
                        spread_pct = 0.0
                    candidate["spread_pct"] = spread_pct

                    # ----------------------------------------------------------
                    # RVOL Score
                    # ----------------------------------------------------------
                    if rvol >= 250:
                        rvol_score = 60
                    elif rvol >= 100:
                        rvol_score = 50
                    elif rvol >= 50:
                        rvol_score = 40
                    elif rvol >= 20:
                        rvol_score = 30
                    elif rvol >= 10:
                        rvol_score = 20
                    elif rvol >= 5:
                        rvol_score = 10
                    elif rvol >= 2:
                        rvol_score = 5
                    else:
                        rvol_score = 0

                    # ----------------------------------------------------------
                    # Float Turnover
                    # ----------------------------------------------------------
                    if float_shares > 0:
                        float_turnover = volume / float_shares
                    else:
                        float_turnover = None

                    if float_turnover is None:
                        float_turnover_score = 0
                    elif float_turnover >= 20:
                        float_turnover_score = 30
                    elif float_turnover >= 10:
                        float_turnover_score = 25
                    elif float_turnover >= 5:
                        float_turnover_score = 20
                    elif float_turnover >= 3:
                        float_turnover_score = 15
                    elif float_turnover >= 1:
                        float_turnover_score = 10
                    elif float_turnover >= 0.5:
                        float_turnover_score = 5
                    else:
                        float_turnover_score = 0

                    # ----------------------------------------------------------
                    # Low Float Score
                    # ----------------------------------------------------------
                    if float_shares <= 0:
                        low_float_score = 0
                    elif float_shares < 1_000_000:
                        low_float_score = 20
                    elif float_shares < 3_000_000:
                        low_float_score = 18
                    elif float_shares < 5_000_000:
                        low_float_score = 15
                    elif float_shares < 10_000_000:
                        low_float_score = 10
                    elif float_shares < 20_000_000:
                        low_float_score = 5
                    else:
                        low_float_score = 0

                    # ----------------------------------------------------------
                    # Gap Score
                    # ----------------------------------------------------------
                    if gap >= 20:
                        gap_score = 25
                    elif gap >= 10:
                        gap_score = 20
                    elif gap >= 5:
                        gap_score = 15
                    elif gap >= 3:
                        gap_score = 10
                    elif gap >= 1:
                        gap_score = 5
                    else:
                        gap_score = 0

                    # ----------------------------------------------------------
                    # Liquidity / Spread Score
                    # ----------------------------------------------------------
                    if spread_pct <= 1:
                        liquidity_score = 10
                    elif spread_pct <= 2:
                        liquidity_score = 5
                    elif spread_pct <= 3:
                        liquidity_score = 2
                    else:
                        liquidity_score = 0

                    # ----------------------------------------------------------
                    # Catalyst
                    # ----------------------------------------------------------
                    catalyst_text = candidate.get("catalyst", "—")
                    catalyst_result = classify_catalyst([catalyst_text])
                    catalyst_score = catalyst_result["score"]

                    # ----------------------------------------------------------
                    # Risk Engine
                    # ----------------------------------------------------------
                    risk_result = analyze_dilution_risk(catalyst_text)
                    risk_score = risk_result.get("risk_score", 0)
                    dilution_risk = risk_result.get("dilution_risk", "UNKNOWN")

                    if dilution_risk == "CRITICAL":
                        risk_penalty = 30
                    elif dilution_risk == "HIGH":
                        risk_penalty = 15
                    elif dilution_risk == "MEDIUM":
                        risk_penalty = 5
                    else:
                        risk_penalty = 0

                    # ----------------------------------------------------------
                    # EVENT SCORE (max 100)
                    # ----------------------------------------------------------
                    event_score = (
                        rvol_score
                        + float_turnover_score
                        + low_float_score
                        + gap_score
                        + liquidity_score
                        + catalyst_score
                    )
                    event_score = max(0, min(100, event_score - risk_penalty))

                    # ----------------------------------------------------------
                    # SETUP GRADE
                    # ----------------------------------------------------------
                    if (
                        event_score >= 85
                        and rvol >= 20
                        and spread_pct <= 2
                        and float_turnover is not None
                        and float_turnover >= 3
                        and dilution_risk != "CRITICAL"
                    ):
                        setup_grade = "A+"
                    elif event_score >= 75 and rvol >= 10:
                        setup_grade = "A"
                    elif event_score >= 60:
                        setup_grade = "B"
                    elif event_score >= 45:
                        setup_grade = "C"
                    elif event_score >= 30:
                        setup_grade = "WATCH"
                    else:
                        setup_grade = "REJECT"

                    # ----------------------------------------------------------
                    # Store V2 metrics
                    # ----------------------------------------------------------
                    candidate.update({
                        "rvol_score": rvol_score,
                        "float_turnover": float_turnover,
                        "float_turnover_score": float_turnover_score,
                        "float_score": low_float_score,
                        "gap_score": gap_score,
                        "liquidity_score": liquidity_score,
                        "catalyst_score": catalyst_score,
                        "event_score": event_score,
                        "score": event_score,
                        "setup_grade": setup_grade,
                        "dilution_risk": dilution_risk,
                        "risk_score": risk_score,
                        "red_flags": risk_result.get("red_flags", []),
                        "float_shares": float_shares,
                        "spread_pct": spread_pct,
                        "catalyst_type": catalyst_result.get("type", "UNKNOWN"),
                    })

                    candidates.append(candidate)
                    
                except Exception:
                    continue
        except Exception:
            continue
            
    save_volume_trend(volume_trend_data)
    candidates.sort(key=lambda x: x.get('score', 0.0), reverse=True)
    return candidates[:10]
