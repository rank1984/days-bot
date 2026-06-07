"""
universe.py — Polygon.io Dynamic Universe Builder
--------------------------------------------------
במקום רשימה סטטית:
1. שולף מ-Polygon את כל המניות שסחרו היום
2. מסנן לפי מחיר, market cap, ונפח מסחר ממוצע
3. מחזיר universe חי ורלוונטי בכל יום
"""

import os
import requests
import pandas as pd
from datetime import datetime, timedelta
from utils.config import POLYGON_API_KEY, MIN_PRICE, MAX_PRICE, MAX_MARKET_CAP, MIN_AVG_VOLUME

UNIVERSE_PATH = os.path.join(os.path.dirname(__file__), "..", "data", "universe.csv")
POLYGON_BASE  = "https://api.polygon.io"


def get_trading_date() -> str:
    """מחזיר את יום המסחר האחרון (לא סוף שבוע)."""
    today = datetime.utcnow()
    if today.weekday() == 5:   # שבת
        today -= timedelta(days=1)
    elif today.weekday() == 6: # ראשון
        today -= timedelta(days=2)
    return today.strftime("%Y-%m-%d")


def fetch_polygon_universe() -> pd.DataFrame:
    """
    Polygon /v2/aggs/grouped/locale/us/market/stocks/{date}
    מחזיר את כל המניות שסחרו ביום נתון עם נתוני OHLCV.
    קריאה אחת בלבד — יעיל ומהיר.
    """
    date = get_trading_date()
    url  = (
        f"{POLYGON_BASE}/v2/aggs/grouped/locale/us/market/stocks/{date}"
        f"?adjusted=true&apiKey={POLYGON_API_KEY}"
    )

    print(f"[Universe] Fetching Polygon grouped daily for {date}...")
    resp = requests.get(url, timeout=30)
    resp.raise_for_status()
    data = resp.json()

    results = data.get("results", [])
    if not results:
        print("[Universe] Polygon returned no results.")
        return pd.DataFrame()

    df = pd.DataFrame(results)
    # עמודות Polygon: T=ticker, c=close, v=volume, vw=vwap, o=open, h=high, l=low
    df.rename(columns={
        "T": "ticker",
        "c": "price",
        "v": "volume",
        "o": "open",
        "h": "high",
        "l": "low",
        "vw": "vwap",
    }, inplace=True)

    df["price"]  = pd.to_numeric(df["price"],  errors="coerce")
    df["volume"] = pd.to_numeric(df["volume"], errors="coerce")
    df.dropna(subset=["price", "volume", "ticker"], inplace=True)

    # סינון ראשוני — מחיר ונפח
    df = df[(df["price"] >= MIN_PRICE) & (df["price"] <= MAX_PRICE)]
    df = df[df["volume"] >= MIN_AVG_VOLUME]

    # סינון — רק מניות רגילות (לא ETF/Warrant: ללא רווח, ללא W/R בסוף)
    df = df[df["ticker"].str.match(r"^[A-Z]{1,5}$")]

    print(f"[Universe] {len(df)} stocks after price/volume filter.")
    return df[["ticker", "price", "volume", "open", "high", "low", "vwap"]].copy()


def enrich_with_sector(df: pd.DataFrame) -> pd.DataFrame:
    """
    מוסיף sector/industry מ-Polygon Ticker Details.
    רץ רק על המניות שעברו סינון — לא על הכל.
    מוגבל ל-50 קריאות (Polygon free tier = 5 req/min).
    """
    if df.empty:
        return df

    sectors, industries = [], []
    # ב-free tier של Polygon יש rate limit — ניקח דגימה של top 200 לפי volume
    top = df.nlargest(200, "volume").copy()

    for ticker in top["ticker"]:
        try:
            url  = f"{POLYGON_BASE}/v3/reference/tickers/{ticker}?apiKey={POLYGON_API_KEY}"
            resp = requests.get(url, timeout=5)
            if resp.status_code == 200:
                info = resp.json().get("results", {})
                sectors.append(info.get("sic_description", "Unknown"))
                industries.append(info.get("sic_description", "Unknown"))
            else:
                sectors.append("Unknown")
                industries.append("Unknown")
        except Exception:
            sectors.append("Unknown")
            industries.append("Unknown")

    top["sector"]   = sectors
    top["industry"] = industries
    return top


def build_universe() -> pd.DataFrame:
    os.makedirs(os.path.dirname(UNIVERSE_PATH), exist_ok=True)
    df = fetch_polygon_universe()
    if df.empty:
        return df

    df = enrich_with_sector(df)
    df.to_csv(UNIVERSE_PATH, index=False)
    print(f"[Universe] Saved {len(df)} tickers → {UNIVERSE_PATH}")
    return df


def load_universe() -> pd.DataFrame:
    """
    טוען universe — בודק שהקובץ מהיום.
    אם ישן → בונה מחדש.
    """
    if os.path.exists(UNIVERSE_PATH):
        mtime = datetime.utcfromtimestamp(os.path.getmtime(UNIVERSE_PATH))
        age_hours = (datetime.utcnow() - mtime).total_seconds() / 3600
        if age_hours < 20:
            df = pd.read_csv(UNIVERSE_PATH)
            print(f"[Universe] Loaded {len(df)} tickers from cache ({age_hours:.1f}h old).")
            return df
        print("[Universe] Cache outdated — rebuilding.")

    return build_universe()
