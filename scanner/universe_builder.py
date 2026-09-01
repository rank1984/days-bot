"""
DAYS-BOT V4.0 – Dynamic Universe Builder
Builds 300-500 symbols from:
1. Nasdaq FTP (base universe)
2. Finnhub News (mentions in last 24h)
3. Premarket movers (gap > 3%)
4. Static fallback
"""
import requests
import pandas as pd
import yfinance as yf
import re
from datetime import datetime, timedelta
from typing import List, Set
import pytz
from pathlib import Path

from utils.config import FINNHUB_API_KEY

ET = pytz.timezone("America/New_York")

# ============================================================
# SOURCE 1: Nasdaq FTP (base universe)
# ============================================================

def get_nasdaq_universe() -> List[str]:
    """Fetch active US equities from Nasdaq public FTP"""
    try:
        url = "ftp://ftp.nasdaqtrader.com/SymbolDirectory/nasdaqtraded.txt"
        df = pd.read_csv(url, sep='|')
        df = df[df['Test Issue'] == 'N']
        df = df[df['ETF'] == 'N']
        # Filter out preferred, warrants, etc.
        symbols = []
        for s in df['Symbol'].dropna():
            s = s.strip().upper()
            if not any(c in s for c in ['$', '.', '-', '/', '^']) and len(s) <= 5:
                symbols.append(s)
        print(f"[Universe] Nasdaq base: {len(symbols)} symbols")
        return symbols[:2000]  # Limit to 2000 for performance
    except Exception as e:
        print(f"[Universe] Nasdaq FTP error: {e}")
        return []


# ============================================================
# SOURCE 2: Finnhub News
# ============================================================

def get_news_symbols() -> List[str]:
    """Extract tickers from news headlines"""
    if not FINNHUB_API_KEY:
        return []

    try:
        url = f"https://finnhub.io/api/v1/news?category=general&token={FINNHUB_API_KEY}"
        resp = requests.get(url, timeout=10)
        if resp.status_code != 200:
            return []

        data = resp.json()
        symbols = set()
        common = {'THE', 'FOR', 'AND', 'WITH', 'THIS', 'THAT', 'FROM', 'WILL', 'HAVE', 'MORE', 'NEW', 'YORK', 'MARKET', 'STOCK', 'NASDAQ', 'NYSE'}
        for item in data[:30]:
            text = item.get('headline', '') + ' ' + item.get('summary', '')
            found = re.findall(r'\b[A-Z]{2,5}\b', text)
            for s in found:
                if s not in common and len(s) >= 2:
                    symbols.add(s)
        print(f"[Universe] News symbols: {len(symbols)}")
        return list(symbols)
    except Exception as e:
        print(f"[Universe] News error: {e}")
        return []


# ============================================================
# SOURCE 3: Premarket movers
# ============================================================

def get_premarket_movers(base_universe: List[str]) -> List[str]:
    """Check top 100 from base for gaps > 3%"""
    movers = []
    test_set = base_universe[:100]
    for ticker in test_set:
        try:
            data = yf.download(ticker, period="2d", interval="1m", prepost=True, progress=False)
            if data.empty:
                continue
            data.index = pd.to_datetime(data.index)
            if data.index.tz is None:
                data.index = data.index.tz_localize("UTC")
            data.index = data.index.tz_convert(ET)
            # Get PM data (04:00-09:30)
            df_pm = data[(data.index.time >= datetime.strptime("04:00", "%H:%M").time()) &
                         (data.index.time < datetime.strptime("09:30", "%H:%M").time())]
            if df_pm.empty:
                continue
            price = float(df_pm['Close'].iloc[-1])
            # Previous close
            prev = yf.download(ticker, period="2d", interval="1d", progress=False)
            if prev.empty:
                continue
            prev_close = float(prev['Close'].iloc[-1])
            gap = ((price - prev_close) / prev_close) * 100
            if abs(gap) > 3:
                movers.append(ticker)
        except:
            continue
    print(f"[Universe] Premarket movers: {len(movers)}")
    return movers


# ============================================================
# MAIN BUILDER
# ============================================================

def build_universe() -> List[str]:
    """Build dynamic universe"""
    print("[Universe] Building dynamic universe...")

    all_symbols: Set[str] = set()

    # 1. Nasdaq base
    base = get_nasdaq_universe()
    all_symbols.update(base[:1500])

    # 2. News
    news = get_news_symbols()
    all_symbols.update(news[:100])

    # 3. Premarket movers (only if in base)
    movers = get_premarket_movers(base[:100])
    all_symbols.update(movers[:30])

    # 4. Static fallback if too small
    fallback = [
        "AAPL", "MSFT", "NVDA", "AMZN", "META", "GOOGL", "TSLA", "AMD",
        "NFLX", "ORCL", "CRM", "ADBE", "QCOM", "INTC", "MU", "AMAT",
        "JPM", "BAC", "WFC", "GS", "MS", "V", "MA", "PYPL", "COF",
        "WMT", "COST", "TGT", "HD", "LOW", "NKE", "MCD", "SBUX", "KO", "PEP",
        "DIS", "ABNB", "BKNG", "UBER", "LYFT", "DASH", "XOM", "CVX", "COP",
        "LLY", "JNJ", "PFE", "MRK", "ABBV", "UNH", "CVS", "ISRG", "CAT", "DE",
        "BA", "GE", "HON", "UPS", "FDX", "SMCI", "MRVL", "ON", "PLTR", "SNOW",
        "CRWD", "PANW", "NET", "DDOG", "MDB", "SHOP", "RIVN", "LCID",
        "COIN", "HOOD", "MSTR", "SOFI", "RBLX", "ROKU", "SNAP", "SPOT",
        "DKNG", "CELH", "BABA", "JD", "PDD", "BIDU", "SE", "GRAB"
    ]
    if len(all_symbols) < 100:
        all_symbols.update(fallback)

    # Clean
    cleaned = []
    for s in all_symbols:
        s = s.strip().upper()
        if not s or len(s) < 2 or len(s) > 5:
            continue
        if any(c in s for c in ["$", ".", "-", "/", "^"]):
            continue
        if s in {"SPY", "QQQ", "IWM", "VTI", "VOO", "DIA", "ARKK"}:
            continue
        if s not in cleaned:
            cleaned.append(s)

    # Limit to 500
    result = cleaned[:500]
    print(f"[Universe] Final dynamic universe: {len(result)} symbols")

    # Cache
    try:
        cache_path = Path(__file__).resolve().parent.parent / "data" / "universe_cache.csv"
        cache_path.parent.mkdir(parents=True, exist_ok=True)
        pd.DataFrame({"symbol": result}).to_csv(cache_path, index=False)
    except:
        pass

    return result


def load_universe() -> List[str]:
    """Main entry point"""
    try:
        return build_universe()
    except Exception as e:
        print(f"[Universe] Build failed: {e}")
        # Try cache
        try:
            cache_path = Path(__file__).resolve().parent.parent / "data" / "universe_cache.csv"
            if cache_path.exists():
                df = pd.read_csv(cache_path)
                symbols = df['symbol'].dropna().tolist()
                print(f"[Universe] Loaded {len(symbols)} from cache")
                return symbols
        except:
            pass
        # Fallback
        fallback = ["AAPL", "MSFT", "NVDA", "AMZN", "META", "GOOGL", "TSLA", "AMD", "NFLX", "ORCL"]
        print(f"[Universe] Using fallback: {len(fallback)} symbols")
        return fallback
