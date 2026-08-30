"""
מנתח נפח – מחשב RVOL לעומת ממוצע 30 ימי
"""
import yfinance as yf
import pandas as pd

def get_rvol(ticker: str) -> float:
    """מחזיר RVOL (נפח PM / ממוצע נפח יומי 30 יום)"""
    try:
        # נפח PM – ניקח מה-candidate (אבל נוכל לחשב גם כאן)
        # לצורך RVOL נשתמש בנפח היומי הממוצע
        data = yf.download(ticker, period="1mo", interval="1d", progress=False)
        if len(data) >= 10:
            avg_volume = data['Volume'].iloc[-30:].mean()
            # נפח PM נשלח מה-candidate – נעביר כפרמטר
            return avg_volume
        return None
    except:
        return None

def calculate_rvol(candidate: dict) -> float:
    """
    מחשב RVOL = נפח PM / נפח יומי ממוצע (30 ימים)
    """
    pm_volume = candidate.get('pm_volume', 0)
    try:
        data = yf.download(candidate['ticker'], period="1mo", interval="1d", progress=False)
        if len(data) >= 10:
            avg_vol = data['Volume'].iloc[-30:].mean()
            if avg_vol > 0:
                return round(pm_volume / avg_vol, 2)
    except:
        pass
    return None
