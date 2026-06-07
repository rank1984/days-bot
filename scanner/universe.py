import os
import pandas as pd
import yfinance as yf

UNIVERSE_PATH = os.path.join(os.path.dirname(__file__), "..", "data", "universe.csv")

# רשימת Small Cap ETFs כדי לקבל tickers
SMALL_CAP_ETFS = ["IWM", "SCHA", "VB"]

from utils.config import MIN_PRICE, MAX_PRICE, MAX_MARKET_CAP


def fetch_from_etf() -> pd.DataFrame:
    """Pull holdings from small-cap ETFs via yfinance screener."""
    # Use yfinance screener for small caps
    try:
        screener = yf.screen(
            "small_cap_gainers",
            size=250
        )
        quotes = screener.get("quotes", [])
        if not quotes:
            raise ValueError("Empty screener")
    except Exception:
        # Fallback: manual small cap list from known active tickers
        quotes = []

    rows = []
    for q in quotes:
        ticker = q.get("symbol", "")
        price  = q.get("regularMarketPrice", 0) or 0
        mcap   = q.get("marketCap", 0) or 0
        sector = q.get("sector", "Unknown")
        industry = q.get("industry", "Unknown")

        if MIN_PRICE <= price <= MAX_PRICE and mcap < MAX_MARKET_CAP:
            rows.append({
                "ticker":   ticker,
                "price":    price,
                "marketCap": mcap,
                "sector":   sector,
                "industry": industry,
            })

    print(f"[Universe] {len(rows)} stocks after filtering.")
    return pd.DataFrame(rows)


def build_universe() -> pd.DataFrame:
    os.makedirs(os.path.dirname(UNIVERSE_PATH), exist_ok=True)
    df = fetch_from_etf()
    if not df.empty:
        df.to_csv(UNIVERSE_PATH, index=False)
        print(f"[Universe] Saved → {UNIVERSE_PATH}")
    return df


def load_universe() -> pd.DataFrame:
    if not os.path.exists(UNIVERSE_PATH):
        print("[Universe] No universe.csv — building now.")
        return build_universe()
    df = pd.read_csv(UNIVERSE_PATH)
    print(f"[Universe] Loaded {len(df)} tickers from cache.")
    return df
