"""
universe.py — Alpaca Universe Builder (ללא Polygon)
----------------------------------------------------
משתמש ב-Alpaca Assets API + Bars API:
1. שולף רשימת מניות אקטיביות מ-Alpaca (חינמי)
2. מוריד נתוני יום קודם בקריאה אחת (batch)
3. מסנן לפי מחיר, volume
"""

import os
import requests
import pandas as pd
from datetime import datetime, timedelta
from utils.config import (
    ALPACA_API_KEY, ALPACA_SECRET_KEY,
    MIN_PRICE, MAX_PRICE, MIN_AVG_VOLUME
)

UNIVERSE_PATH = os.path.join(os.path.dirname(__file__), "..", "data", "universe.csv")
ALPACA_DATA   = "https://data.alpaca.markets/v2"

HEADERS = {
    "APCA-API-KEY-ID":     ALPACA_API_KEY,
    "APCA-API-SECRET-KEY": ALPACA_SECRET_KEY,
}


def get_prev_trading_date() -> str:
    d = datetime.utcnow() - timedelta(days=1)
    while d.weekday() >= 5:
        d -= timedelta(days=1)
    return d.strftime("%Y-%m-%d")


def fetch_active_assets() -> list:
    """רשימת מניות אקטיביות מ-Alpaca — חינמי לחלוטין."""
    url    = "https://paper-api.alpaca.markets/v2/assets"
    params = {"status": "active", "asset_class": "us_equity"}
    resp   = requests.get(url, headers=HEADERS, params=params, timeout=30)
    resp.raise_for_status()
    assets  = resp.json()
    tickers = [
        a["symbol"] for a in assets
        if a.get("tradable") and a.get("symbol", "").isalpha()
    ]
    print(f"[Universe] {len(tickers)} active assets from Alpaca.")
    return tickers


def fetch_prev_day_bars(tickers: list) -> pd.DataFrame:
    """נתוני יום קודם לכולם — batch אחד של 500."""
    date = get_prev_trading_date()
    rows = []
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

        print(f"[Universe] Batch {i//BATCH+1}: {min(i+BATCH,len(tickers))}/{len(tickers)}")

    return pd.DataFrame(rows)


def build_universe() -> pd.DataFrame:
    os.makedirs(os.path.dirname(UNIVERSE_PATH), exist_ok=True)
    tickers = fetch_active_assets()
    df      = fetch_prev_day_bars(tickers)

    if df.empty:
        print("[Universe] No data.")
        return df

    before = len(df)
    df = df[
        (df["price"] >= MIN_PRICE) &
        (df["price"] <= MAX_PRICE) &
        (df["volume"] >= MIN_AVG_VOLUME)
    ].copy()
    df["sector"]   = "Unknown"
    df["industry"] = "Unknown"
    df["float"]    = 0
    df.sort_values("volume", ascending=False, inplace=True)
    df.reset_index(drop=True, inplace=True)
    print(f"[Universe] {before} → {len(df)} after filter.")

    df.to_csv(UNIVERSE_PATH, index=False)
    print(f"[Universe] Saved {len(df)} tickers → {UNIVERSE_PATH}")
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
