"""
Breakout detection - finds stocks about to break out
"""
import numpy as np
from typing import Dict, List, Any

def detect_breakout(stock_data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Detect if a stock is about to break out
    Returns: dict with breakout signals
    """
    if 'close' not in stock_data or len(stock_data['close']) < 50:
        return {'is_breakout': False, 'score': 0}
    
    prices = np.array(stock_data['close'])
    volumes = np.array(stock_data.get('volume', []))
    
    # 1. SMA 50 and SMA 200
    sma_50 = np.mean(prices[-50:])
    sma_200 = np.mean(prices[-200:]) if len(prices) >= 200 else sma_50
    
    # 2. Volume ratio (last 5 days vs last 20 days)
    vol_5 = np.mean(volumes[-5:]) if len(volumes) >= 5 else 0
    vol_20 = np.mean(volumes[-20:]) if len(volumes) >= 20 else vol_5
    vol_ratio = vol_5 / vol_20 if vol_20 > 0 else 1.0
    
    # 3. Price above SMA 50
    price_above_sma = (prices[-1] / sma_50) - 1 if sma_50 > 0 else 0
    
    # 4. RSI
    rsi = calculate_rsi(prices, 14)
    
    # 5. Resistance level (20-day high)
    resistance = np.max(prices[-20:-5]) if len(prices) >= 20 else prices[-1]
    near_resistance = prices[-1] / resistance if resistance > 0 else 1.0
    
    # 6. Volume trend (increasing volume over last 10 days)
    if len(volumes) >= 10:
        vol_trend = np.corrcoef(range(10), volumes[-10:])[0, 1] if len(volumes[-10:]) > 1 else 0
    else:
        vol_trend = 0
    
    # Score: 0-100
    score = 0
    
    # Price above SMA 50 (0-20 points)
    if 0.01 < price_above_sma < 0.15:
        score += 20
    elif 0.005 < price_above_sma < 0.20:
        score += 10
    
    # Volume ratio (0-25 points)
    if vol_ratio > 2.0:
        score += 25
    elif vol_ratio > 1.5:
        score += 18
    elif vol_ratio > 1.2:
        score += 10
    
    # RSI (0-20 points)
    if 55 < rsi < 70:
        score += 20
    elif 50 < rsi < 75:
        score += 10
    
    # Near resistance (0-15 points)
    if near_resistance > 0.95:
        score += 15
    elif near_resistance > 0.90:
        score += 10
    
    # Volume trend (0-20 points)
    if vol_trend > 0.5:
        score += 20
    elif vol_trend > 0.3:
        score += 12
    elif vol_trend > 0.1:
        score += 5
    
    # Normalize to 0-100
    score = min(100, score)
    
    return {
        'is_breakout': score > 50,
        'score': score,
        'volume_ratio': vol_ratio,
        'rsi': rsi,
        'price_above_sma': price_above_sma * 100,  # as percentage
        'near_resistance': near_resistance,
        'vol_trend': vol_trend,
        'sma_50': sma_50,
        'sma_200': sma_200,
        'resistance': resistance,
    }

def calculate_rsi(prices: np.ndarray, period: int = 14) -> float:
    """Calculate RSI for a price series"""
    if len(prices) < period + 1:
        return 50
    
    deltas = np.diff(prices)
    seed = deltas[:period]
    up = seed[seed >= 0].sum() / period
    down = -seed[seed < 0].sum() / period
    
    if down == 0:
        return 100
    
    rs = up / down
    rsi = 100 - (100 / (1 + rs))
    
    # Smooth RSI
    for i in range(period, len(deltas)):
        delta = deltas[i]
        if delta > 0:
            up = (up * (period - 1) + delta) / period
            down = (down * (period - 1)) / period
        else:
            up = (up * (period - 1)) / period
            down = (down * (period - 1) - delta) / period
        rs = up / down if down != 0 else 999
        rsi = 100 - (100 / (1 + rs))
    
    return rsi
