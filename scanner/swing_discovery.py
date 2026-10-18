"""
DAYS-BOT V5.0.6 — Swing Discovery (Daily Data)
סורק מניות על בסיס נתונים יומיים (Daily Bars) ללא תלות בנתוני Pre-Market תוך-דקתיים.
"""
import yfinance as yf
import pandas as pd
import pytz
from datetime import datetime, timedelta
from typing import List, Dict, Tuple
import math

ET = pytz.timezone("America/New_York")

def _safe_float(val, default=0.0):
    try:
        if val is None or (isinstance(val, float) and math.isnan(val)):
            return default
        return float(val)
    except:
        return default

def run_swing_discovery(universe_tickers: List[str]) -> Tuple[List[dict], dict]:
    """
    מקבל רשימת טיקרים (למשל 500), מוריד נתונים יומיים, ומחזיר את אלה שעוברים את פילטרי ה-Swing.
    """
    print(f"[SwingDiscovery] Starting daily scan on {len(universe_tickers)} symbols...")
    
    # מורידים נתונים יומיים ל-5 ימים אחורה (כדי לחשב נפח ממוצע ו-SMA)
    # yfinance מאפשר הורדה מרוכזת של מספר טיקרים בבת אחת
    print("[SwingDiscovery] Fetching daily bars via yfinance...")
    data = yf.download(
        tickers=" ".join(universe_tickers), 
        period="1mo", 
        interval="1d", 
        group_by='ticker', 
        progress=False, 
        threads=True,
        auto_adjust=False
    )
    
    candidates = []
    diagnostics = {
        "universe": len(universe_tickers),
        "passed_filters": 0,
        "reject_price": 0,
        "reject_volume": 0,
        "reject_trend": 0,
        "reject_gap": 0
    }
    
    for ticker in universe_tickers:
        try:
            # חילוץ הנתונים של הטיקר הספציפי
            if isinstance(data.columns, pd.MultiIndex):
                if ticker not in data.columns.levels[0]:
                    continue
                df = data[ticker]
            else:
                df = data # אם הורד רק טיקר אחד
                
            df = df.dropna()
            if len(df) < 20: # צריך לפחות 20 יום לממוצע
                continue
                
            latest = df.iloc[-1]
            prev = df.iloc[-2]
            
            price = _safe_float(latest['Close'])
            prev_close = _safe_float(prev['Close'])
            volume = _safe_float(latest['Volume'])
            avg_volume_5d = _safe_float(df['Volume'].tail(5).mean())
            
            # 1. פילטר מחיר
            if price < 1.0 or price > 100.0: # Swing trading מתאים גם למניות בינוניות
                diagnostics["reject_price"] += 1
                continue
                
            # 2. פילטר נפח
            if avg_volume_5d < 500_000:
                diagnostics["reject_volume"] += 1
                continue
                
            # 3. פילטר מגמה (SMA20)
            sma20 = _safe_float(df['Close'].tail(20).mean())
            if price < sma20:
                diagnostics["reject_trend"] += 1
                continue
                
            # 4. פילטר Gap (לא רוצים מניות שזינקו יותר מדי ביום אחד)
            gap_pct = ((price - prev_close) / prev_close) * 100 if prev_close > 0 else 0
            if gap_pct > 10.0: # Gap יומי מעל 10% נחשב מסוכן ל-Swing (פסגה)
                diagnostics["reject_gap"] += 1
                continue
                
            # עבר את כל הפילטרים!
            diagnostics["passed_filters"] += 1
            candidates.append({
                "ticker": ticker,
                "price": price,
                "prev_close": prev_close,
                "gap_pct": gap_pct,
                "volume": volume,
                "avg_volume": avg_volume_5d,
                "sma20": sma20,
                "float": None, # נמשוך בהמשך ב-FullScan
                "spread_pct": 0.5, # הנחה ראשונית למניות יומיות (ימדד בפועל ב-RTH)
                "data_status": "ACTIONABLE",
                "trade_type": "SWING_1_3D"
            })
            
        except Exception as e:
            continue
            
    print(f"[SwingDiscovery] Found {len(candidates)} candidates passing daily filters.")
    print(f"[SwingDiscovery] Diagnostics: {diagnostics}")
    
    return candidates, diagnostics
