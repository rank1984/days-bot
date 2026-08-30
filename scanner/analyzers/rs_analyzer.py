"""
מנתח חוזק יחסי – משווה ביצועי המניה מול SPY
"""
import yfinance as yf

def get_relative_strength(ticker: str) -> float:
    """מחזיר RS = ביצועי מניה / ביצועי SPY ב-5 ימים"""
    try:
        spy = yf.download("SPY", period="5d", interval="1d", progress=False)
        stock = yf.download(ticker, period="5d", interval="1d", progress=False)
        if len(spy) >= 3 and len(stock) >= 3:
            spy_ret = (spy['Close'].iloc[-1] / spy['Close'].iloc[0]) - 1
            stock_ret = (stock['Close'].iloc[-1] / stock['Close'].iloc[0]) - 1
            if spy_ret != 0:
                return round(stock_ret / spy_ret, 2)
    except:
        pass
    return None
