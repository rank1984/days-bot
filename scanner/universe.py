"""
universe.py — שדרוג #6: Top Gainers Universe + שדרוג #1: Float Filter
----------------------------------------------------------------------
במקום לסרוק אלפי מניות:
1. שולפים Top 100 Gainers מ-Polygon
2. מסננים לפי מחיר, volume, float
3. מחזירים universe ממוקד ורלוונטי
"""

import os
import time
import requests
import pandas as pd
from datetime import datetime, timedelta
from utils.config import (
    POLYGON_API_KEY, MIN_PRICE, MAX_PRICE,
    MIN_AVG_VOLUME, MAX_FLOAT
)

UNIVERSE_PATH = os.path.join(os.path.dirname(__file__), "..", "data", "universe.csv")
POLYGON_BASE  = "https://api.polygon.io"


def get_trading_date() -> str:
    today = datetime.utcnow()
    if today.weekday() == 5:
        today -= timedelta(days=1)
    elif today.weekday() == 6:
        today -= timedelta(days=2)
    return today.strftime("%Y-%m-%d")


def fetch_top_gainers() -> pd.DataFrame:
    """
    שדרוג #6: Top 100 Gainers מ-Polygon במקום לסרוק הכל.
    מהיר, ממוקד, רלוונטי.
    """
    url = (
        f"{POLYGON_BASE}/v2/snapshot/locale/us/markets/stocks/gainers"
        f"?include_otc=false&apiKey={POLYGON_API_KEY}"
    )
    print("[Universe] Fetching Top Gainers from Polygon...")
    resp = requests.get(url, timeout=15)
    resp.raise_for_status()
    data = resp.json()

    tickers_data = data.get("tickers", [])
    if not tickers_data:
        print("[Universe] No gainers returned.")
        return pd.DataFrame()

    rows = []
    for item in tickers_data:
        ticker = item.get("ticker", "")
        day    = item.get("day", {})
        prev   = item.get("prevDay", {})

        price  = day.get("c", 0) or prev.get("c", 0)
        volume = day.get("v", 0)
        open_  = day.get("o", 0)
        high   = day.get("h", 0)
        change = item.get("todaysChangePerc", 0)

        # סינון בסיסי
        if not ticker or not ticker.isalpha():
            continue
        if not (MIN_PRICE <= price <= MAX_PRICE):
            continue
        if volume < MIN_AVG_VOLUME:
            continue

        rows.append({
            "ticker":     ticker,
            "price":      round(price, 2),
            "volume":     int(volume),
            "open":       round(open_, 2),
            "high":       round(high, 2),
            "change_pct": round(change, 2),
            "sector":     "Unknown",
            "industry":   "Unknown",
            "float":      0,
            "news_score": 0,
        })

    df = pd.DataFrame(rows)
    print(f"[Universe] {len(df)} gainers after basic filter.")
    return df


def enrich_ticker(ticker: str) -> dict:
    """
    שולף float ו-sector עבור מניה אחת מ-Polygon.
    מחזיר dict עם float, sector, industry.
    """
    result = {"float": 0, "sector": "Unknown", "industry": "Unknown"}
    try:
        url  = f"{POLYGON_BASE}/v3/reference/tickers/{ticker}?apiKey={POLYGON_API_KEY}"
        resp = requests.get(url, timeout=5)
        if resp.status_code == 200:
            info = resp.json().get("results", {})
            result["float"]    = info.get("share_class_shares_outstanding", 0) or 0
            result["sector"]   = info.get("sic_description", "Unknown")
            result["industry"] = info.get("sic_description", "Unknown")
    except Exception:
        pass
    return result


def enrich_universe(df: pd.DataFrame) -> pd.DataFrame:
    """
    שדרוג #1: מוסיף float לכל מניה + מסנן לפי MAX_FLOAT.
    """
    if df.empty:
        return df

    print(f"[Universe] Enriching {len(df)} tickers with float data...")
    enriched = []

    for i, (_, row) in enumerate(df.iterrows()):
        info = enrich_ticker(row["ticker"])
        row  = row.copy()
        row["float"]    = info["float"]
        row["sector"]   = info["sector"]
        row["industry"] = info["industry"]
        enriched.append(row)

        # Rate limit — Polygon free = 5 req/min
        if i > 0 and i % 5 == 0:
            time.sleep(12)

    result = pd.DataFrame(enriched)

    # סינון float
    before = len(result)
    result = result[(result["float"] == 0) | (result["float"] <= MAX_FLOAT)]
    print(f"[Universe] Float filter: {before} → {len(result)} (max {MAX_FLOAT:,})")

    return result


def build_universe() -> pd.DataFrame:
    os.makedirs(os.path.dirname(UNIVERSE_PATH), exist_ok=True)
    df = fetch_top_gainers()
    if df.empty:
        return df
    df = enrich_universe(df)
    df.to_csv(UNIVERSE_PATH, index=False)
    print(f"[Universe] Saved {len(df)} tickers → {UNIVERSE_PATH}")
    return df


def load_universe() -> pd.DataFrame:
    if os.path.exists(UNIVERSE_PATH):
        mtime     = datetime.utcfromtimestamp(os.path.getmtime(UNIVERSE_PATH))
        age_hours = (datetime.utcnow() - mtime).total_seconds() / 3600
        if age_hours < 8:
            df = pd.read_csv(UNIVERSE_PATH)
            print(f"[Universe] Loaded {len(df)} tickers from cache ({age_hours:.1f}h old).")
            return df
        print("[Universe] Cache outdated — rebuilding.")
    return build_universe()
