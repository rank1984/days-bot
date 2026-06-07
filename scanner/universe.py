import os
import requests
import pandas as pd
from utils.config import FMP_API_KEY, MIN_PRICE, MAX_PRICE, MAX_MARKET_CAP

UNIVERSE_PATH = os.path.join(os.path.dirname(__file__), "..", "data", "universe.csv")
FMP_BASE = "https://financialmodelingprep.com/api/v3"


def fetch_screener() -> pd.DataFrame:
    url = (
        f"{FMP_BASE}/stock-screener"
        f"?priceMoreThan={MIN_PRICE}"
        f"&priceLowerThan={MAX_PRICE}"
        f"&marketCapLowerThan={MAX_MARKET_CAP}"
        f"&isActivelyTrading=true"
        f"&exchange=NYSE,NASDAQ,AMEX"
        f"&apikey={FMP_API_KEY}"
    )
    resp = requests.get(url, timeout=30)
    resp.raise_for_status()
    data = resp.json()

    if not data:
        print("[Universe] FMP returned empty screener.")
        return pd.DataFrame()

    df = pd.DataFrame(data)
    cols = ["symbol", "companyName", "price", "marketCap", "sector", "industry"]
    df = df[[c for c in cols if c in df.columns]].copy()
    df.rename(columns={"symbol": "ticker"}, inplace=True)

    df["price"]     = pd.to_numeric(df["price"], errors="coerce")
    df["marketCap"] = pd.to_numeric(df["marketCap"], errors="coerce")
    df.dropna(subset=["price", "marketCap"], inplace=True)
    df = df[(df["price"] >= MIN_PRICE) & (df["price"] <= MAX_PRICE)]
    df = df[df["marketCap"] < MAX_MARKET_CAP]

    print(f"[Universe] {len(df)} stocks after filtering.")
    return df


def build_universe() -> pd.DataFrame:
    os.makedirs(os.path.dirname(UNIVERSE_PATH), exist_ok=True)
    df = fetch_screener()
    if not df.empty:
        df.to_csv(UNIVERSE_PATH, index=False)
        print(f"[Universe] Saved → {UNIVERSE_PATH}")
    return df


def load_universe() -> pd.DataFrame:
    if not os.path.exists(UNIVERSE_PATH):
        print("[Universe] No universe.csv found — building now.")
        return build_universe()
    df = pd.read_csv(UNIVERSE_PATH)
    print(f"[Universe] Loaded {len(df)} tickers from cache.")
    return df
