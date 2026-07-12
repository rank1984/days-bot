# breakout.py
import numpy as np
from config import *

def find_breakout_candidates(stock_data):
    """מזהה מניות לפני פריצה"""
    candidates = []
    
    for symbol, data in stock_data.items():
        # בדיקה: מחיר נוגע בקו מגמה עולה
        prices = data['close'].values
        highs = data['high'].values
        
        # 1. נפח הולך ועולה (הצטברות)
        volume_avg = np.mean(data['volume'].values[-20:])
        recent_volume = np.mean(data['volume'].values[-5:])
        volume_ratio = recent_volume / volume_avg
        
        # 2. מחיר מעל SMA 50 אבל מתחת ל-SMA 200 (פריצה מתחילה)
        sma_50 = np.mean(prices[-50:])
        sma_200 = np.mean(prices[-200:])
        above_50 = prices[-1] > sma_50
        below_200 = prices[-1] < sma_200
        
        # 3. נוגע ברמות התנגדות קודמות
        resistance = np.max(prices[-20:-5])
        price_near_resistance = (prices[-1] / resistance) > 0.95
        
        # 4. RSI עולה אבל לא מוקצן
        rsi = calculate_rsi(prices, 14)
        
        # 5. Float קטן (זיהיתי שאתה כבר משתמש בזה)
        
        if (volume_ratio > 1.5 and 
            above_50 and 
            below_200 and 
            price_near_resistance and 
            50 < rsi < 75):
            
            # חישוב ציון פריצה
            score = (
                (volume_ratio - 1) * 10 +      # נפח
                (rsi - 50) * 0.5 +             # מומנטום
                (1 - (prices[-1] / resistance)) * 100  # קרבה להתנגדות
            )
            
            candidates.append({
                'symbol': symbol,
                'score': score,
                'volume_ratio': volume_ratio,
                'rsi': rsi,
                'price': prices[-1],
                'resistance': resistance,
                'potential_gain': (resistance * 1.2) / prices[-1]  # 20% מעבר
            })
    
    return sorted(candidates, key=lambda x: x['score'], reverse=True)[:10]
