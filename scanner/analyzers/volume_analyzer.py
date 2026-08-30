"""
מנתח נפח – מחשב RVOL (נפח PM / ממוצע נפח יומי 30 יום)
"""
import yfinance as yf

def calculate_rvol(candidate: dict) -> float:
    """
    מחשב RVOL = נפח PM / נפח יומי ממוצע (30 ימים)
    """
    pm_volume = candidate.get('pm_volume', 0)
    if not pm_volume:
        return None
    try:
        data = yf.download(candidate['ticker'], period="1mo", interval="1d", progress=False)
        if len(data) >= 10:
            avg_vol = data['Volume'].iloc[-30:].mean()
            if avg_vol > 0:
                return round(pm_volume / avg_vol, 2)
    except:
        pass
    return None
