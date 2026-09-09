"""
DAYS-BOT V5.0.4 – Premarket Engine (Alpaca IEX + yfinance Fallback)
Fetches real 1-minute premarket bars.
If Alpaca IEX fails / returns empty → falls back to yfinance (prepost=True).
"""
import pytz
import requests
from datetime import datetime, timedelta, time
from typing import Optional, Dict, Any
import pandas as pd
import yfinance as yf
from utils.config import ALPACA_API_KEY, ALPACA_SECRET_KEY, ALPACA_DATA_URL

ET = pytz.timezone("America/New_York")
BARS_URL = f"{ALPACA_DATA_URL.rstrip('/')}/v2/stocks/bars"

PM_START = time(4, 0)
PM_END = time(9, 30)


def _headers() -> dict:
    return {
        "APCA-API-KEY-ID": ALPACA_API_KEY,
        "APCA-API-SECRET-KEY": ALPACA_SECRET_KEY,
        "Accept": "application/json",
    }


def _calculate_pm_metrics(df: pd.DataFrame) -> Optional[Dict[str, Any]]:
    """Calculate PM metrics from DataFrame. Returns None if empty."""
    if df is None or df.empty:
        return None

    # Normalize column names (yfinance / Alpaca)
    col_map = {
        "Open": "open", "High": "high", "Low": "low", "Close": "close", "Volume": "volume",
        "open": "open", "high": "high", "low": "low", "close": "close", "volume": "volume",
    }
    df = df.rename(columns={k: v for k, v in col_map.items() if k in df.columns})

    required = ["high", "low", "close", "volume"]
    if not all(c in df.columns for c in required):
        return None

    pm_high = float(df["high"].max())
    pm_low = float(df["low"].min())
    pm_volume = int(df["volume"].sum())
    pm_bars_count = len(df)

    # VWAP (typical price weighted)
    typical = (df["high"] + df["low"] + df["close"]) / 3.0
    total_value = (typical * df["volume"]).sum()
    total_volume = df["volume"].sum()
    pm_vwap = float(total_value / total_volume) if total_volume > 0 else float(df["close"].iloc[-1])

    return {
        "pm_high": round(pm_high, 4),
        "pm_low": round(pm_low, 4),
        "pm_vwap": round(pm_vwap, 4),
        "pm_volume": pm_volume,
        "pm_bars_count": pm_bars_count,
        "pm_data_quality": "GOOD_DATA" if pm_bars_count >= 10 else "LOW_DATA",
        "pm_last": round(float(df["close"].iloc[-1]), 4),
    }


def _fetch_yfinance_pm(ticker: str, target_date: datetime) -> Optional[Dict[str, Any]]:
    """Fallback to yfinance for premarket data."""
    try:
        data = yf.download(
            ticker,
            period="2d",
            interval="1m",
            prepost=True,
            progress=False,
            auto_adjust=False,
            threads=False,
        )

        if data is None or data.empty:
            return None

        # Flatten MultiIndex columns if present (newer yfinance)
        if isinstance(data.columns, pd.MultiIndex):
            data.columns = data.columns.get_level_values(0)

        data.index = pd.to_datetime(data.index)
        if data.index.tz is None:
            data.index = data.index.tz_localize("UTC")
        data = data.tz_convert(ET)

        # Filter to the target calendar day
        target_date_only = target_date.date() if hasattr(target_date, "date") else target_date
        mask = data.index.date == target_date_only
        df = data.loc[mask]

        if df.empty:
            return None

        # PM window only (04:00 inclusive → 09:30 exclusive)
        df = df.between_time("04:00", "09:29")

        if df.empty:
            return None

        print(f"[PM] {ticker} - yfinance fallback: {len(df)} bars")
        metrics = _calculate_pm_metrics(df)
        if metrics:
            metrics["source"] = "yfinance"
            metrics["error"] = None
        return metrics

    except Exception as e:
        print(f"[PM] {ticker} - yfinance error: {e}")
        return None


def get_premarket_minute_data(ticker: str, target_date_str: str = None) -> Dict[str, Any]:
    """
    Fetch 1-minute premarket bars.
    Priority: Alpaca IEX → yfinance fallback.
    """
    now_et = datetime.now(ET)

    if target_date_str:
        try:
            target_date = datetime.strptime(target_date_str, "%Y-%m-%d")
            target_date = ET.localize(target_date) if target_date.tzinfo is None else target_date
        except Exception:
            target_date = now_et
    else:
        target_date = now_et
        target_date_str = now_et.strftime("%Y-%m-%d")

    # ---------- 1. Try Alpaca ----------
    if ALPACA_API_KEY and ALPACA_SECRET_KEY:
        try:
            start = now_et - timedelta(days=3)  # מספיק 3 ימים

            response = requests.get(
                BARS_URL,
                headers=_headers(),
                params={
                    "symbols": ticker,
                    "timeframe": "1Min",
                    "start": start.isoformat(),
                    "end": now_et.isoformat(),
                    "adjustment": "raw",
                    "feed": "iex",
                    "limit": 10000,
                },
                timeout=12,
            )

            if response.status_code == 200:
                data = response.json()
                bars = data.get("bars", {}).get(ticker, [])
                print(f"[PM] {ticker} - Alpaca total bars received: {len(bars)}")

                if bars:
                    pm_bars = []
                    target_d = target_date.date()
                    current_t = now_et.time()

                    for bar in bars:
                        ts = datetime.fromisoformat(bar["t"].replace("Z", "+00:00"))
                        ts_et = ts.astimezone(ET)

                        if ts_et.date() != target_d:
                            continue
                        if not (PM_START <= ts_et.time() < PM_END):
                            continue
                        if ts_et.time() > current_t:
                            continue

                        pm_bars.append(bar)

                    print(f"[PM] {ticker} - PM bars (04:00-09:30, today): {len(pm_bars)}")

                    if pm_bars:
                        # Convert to DataFrame for unified calculation
                        df = pd.DataFrame([{
                            "high": float(b["h"]),
                            "low": float(b["l"]),
                            "close": float(b["c"]),
                            "volume": int(b["v"]),
                        } for b in pm_bars])

                        metrics = _calculate_pm_metrics(df)
                        if metrics:
                            metrics["source"] = "alpaca_iex"
                            metrics["error"] = None
                            return metrics
            else:
                print(f"[PM] {ticker} - Alpaca HTTP {response.status_code}")

        except Exception as e:
            print(f"[PM] {ticker} - Alpaca exception: {e}")

    # ---------- 2. Fallback to yfinance ----------
    print(f"[PM] {ticker} - Falling back to yfinance")
    yf_result = _fetch_yfinance_pm(ticker, target_date)
    if yf_result:
        return yf_result

    # ---------- 3. Complete failure ----------
    return {
        "pm_high": None,
        "pm_low": None,
        "pm_vwap": None,
        "pm_volume": 0,
        "pm_bars_count": 0,
        "pm_data_quality": "NO_DATA",
        "pm_last": None,
        "source": "none",
        "error": "No PM data from Alpaca or yfinance",
    }
