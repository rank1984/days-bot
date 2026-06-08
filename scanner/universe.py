import os
import time
import requests
import pandas as pd
from datetime import datetime, timedelta
from utils.config import (
    ALPACA_API_KEY, ALPACA_SECRET_KEY,
    MIN_PRICE, MAX_PRICE, MIN_AVG_VOLUME,
    FINNHUB_API_KEY
)

UNIVERSE_PATH = os.path.join(os.path.dirname(__file__), "..", "data", "universe.csv")
ALPACA_DATA   = "https://data.alpaca.markets/v2"
HEADERS = {
    "APCA-API-KEY-ID":     ALPACA_API_KEY,
    "APCA-API-SECRET-KEY": ALPACA_SECRET_KEY,
}

BLOCK_TICKERS = {
    "MSTU","TSLL","TSDD","BITO","ETHA","ETHU","SOXS","TZA","UVIX",
    "DRIP","NVD","QID","SQQQ","TQQQ","SPXS","SPXL","FAS","FAZ",
    "LABD","LABU","PURR","BMNU","MSOS",
}
BLOCK_NAME_KEYWORDS = [
    "etf","etn","fund","trust","index","proshares","direxion",
    "ultrashort","leveraged","inverse","bitcoin","ethereum","crypto",
    "2x","3x","-2x","-3x",
]


def get_prev_trading_date() -> str:
    d = datetime.utcnow() - timedelta(days=1)
    while d.weekday() >= 5:
        d -= timedelta(days=1)
    return d.strftime("%Y-%m-%d")


def is_real_stock(asset: dict) -> bool:
    ticker = asset.get("symbol", "").upper()
    name   = asset.get("name", "").lower()
    if ticker in BLOCK_TICKERS:
        return False
    if len(ticker) > 5 or not ticker.isalpha():
        return False
    for kw in BLOCK_NAME_KEYWORDS:
        if kw in name:
            return False
    return asset.get("tradable", False)


def fetch_active_assets() -> list:
    url    = "https://paper-api.alpaca.markets/v2/assets"
    params = {"status": "active", "asset_class": "us_equity"}
    resp   = requests.get(url, headers=HEADERS, params=params, timeout=30)
    resp.raise_for_status()
    assets  = resp.json()
    tickers = [a["symbol"] for a in assets if is_real_stock(a)]
    print(f"[Universe] {len(tickers)} real stocks (ETFs filtered).")
    return tickers


def fetch_prev_day_bars(tickers: list) -> pd.DataFrame:
    date  = get_prev_trading_date()
    rows  = []
    BATCH = 500
    for i in range(0, len(tickers), BATCH):
        batch  = tickers[i:i + BATCH]
        params = {
            "symbols":   ",".join(batch),
            "timeframe": "1Day",
            "start":     date + "T00:00:00Z",
            "end":       date + "T23:59:59Z",
            "limit":     10000,
            "feed":      "iex",
        }
        try:
            resp = requests.get(
                f"{ALPACA_DATA}/stocks/bars",
                headers=HEADERS, params=params, timeout=30
            )
            resp.raise_for_status()
            bars_data = resp.json().get("bars", {})
            for ticker, bars in bars_data.items():
                if not bars:
                    continue
                bar = bars[-1]
                rows.append({
                    "ticker": ticker,
                    "price":  round(bar.get("c", 0), 2),
                    "open":   round(bar.get("o", 0), 2),
                    "high":   round(bar.get("h", 0), 2),
                    "volume": int(bar.get("v", 0)),
                    "vwap":   round(bar.get("vw", 0), 2),
                })
        except Exception as e:
            print(f"[Universe] Batch {i} error: {e}")
        print(f"[Universe] Bars {i//BATCH+1}: {min(i+BATCH,len(tickers))}/{len(tickers)}")
    return pd.DataFrame(rows)


def fetch_floats(tickers: list) -> dict:
    float_map = {}
    for i, ticker in enumerate(tickers):
        try:
            resp = requests.get(
                "https://finnhub.io/api/v1/stock/profile2",
                params={"symbol": ticker, "token": FINNHUB_API_KEY},
                timeout=5
            )
            if resp.status_code == 200:
                fl = resp.json().get("shareOutstanding")
                if fl and fl > 0:
                    float_map[ticker] = int(fl * 1_000_000)
        except Exception:
            pass
        if (i + 1) % 55 == 0:
            print(f"[Universe] Float {i+1}/{len(tickers)} — waiting 65s...")
            time.sleep(65)
    print(f"[Universe] Got float for {len(float_map)}/{len(tickers)} tickers.")
    return float_map


def build_universe() -> pd.DataFrame:
    os.makedirs(os.path.dirname(UNIVERSE_PATH), exist_ok=True)
    tickers = fetch_active_assets()
    df      = fetch_prev_day_bars(tickers)
    if df.empty:
        return df

    df = df[
        (df["price"] >= MIN_PRICE) &
        (df["price"] <= MAX_PRICE) &
        (df["volume"] >= MIN_AVG_VOLUME) &
        (df["ticker"].str.match(r"^[A-Z]{1,5}$")) &
        (~df["ticker"].isin(BLOCK_TICKERS))
    ].copy()

    float_map    = fetch_floats(df["ticker"].tolist())
    df["float"]  = df["ticker"].map(float_map).fillna(0).astype(int)
    df["sector"] = "Unknown"
    df["industry"] = "Unknown"

    df.sort_values("volume", ascending=False, inplace=True)
    df.reset_index(drop=True, inplace=True)
    df.to_csv(UNIVERSE_PATH, index=False)
    print(f"[Universe] Saved {len(df)} real stocks → {UNIVERSE_PATH}")
    return df


def load_universe() -> pd.DataFrame:
    if os.path.exists(UNIVERSE_PATH):
        mtime     = datetime.utcfromtimestamp(os.path.getmtime(UNIVERSE_PATH))
        age_hours = (datetime.utcnow() - mtime).total_seconds() / 3600
        if age_hours < 8:
            df = pd.read_csv(UNIVERSE_PATH)
            print(f"[Universe] Loaded {len(df)} tickers ({age_hours:.1f}h old).")
            return df
    return build_universe()
