"""
DAYS-BOT V4.0 – Premarket Discovery
- Returns candidates even outside PM window (using recent data)
- No hard rejection on PM volume/bars/VWAP
- Only rejects on obvious data errors
- Returns up to 40 candidates
"""
from datetime import datetime, time, timedelta
from typing import List, Tuple
import pytz
import pandas as pd
import yfinance as yf
from scanner.universe import load_universe

ET = pytz.timezone("America/New_York")
PM_START = time(4, 0)
PM_END = time(9, 30)
BATCH_SIZE = 25


def _is_in_pm_window(now_et: datetime) -> bool:
    """Check if current time is within premarket window (04:00-09:30 ET)"""
    return PM_START <= now_et.time() < PM_END


def _get_previous_closes(universe: List[str], target_date_str: str) -> dict:
    """Fetch previous close for each ticker (using 5 days of data)"""
    prev_closes = {}
    for i in range(0, len(universe), BATCH_SIZE):
        batch = universe[i:i+BATCH_SIZE]
        try:
            data = yf.download(" ".join(batch), period="5d", interval="1d", progress=False, threads=False)
            for ticker in batch:
                if len(batch) == 1:
                    if not data.empty:
                        prev_closes[ticker] = float(data['Close'].iloc[-1])
                else:
                    if ticker in data.columns.get_level_values(0):
                        series = data[ticker]['Close'].dropna()
                        if not series.empty:
                            prev_closes[ticker] = float(series.iloc[-1])
        except Exception:
            continue
    return prev_closes


def _extract_candidate(ticker: str, df: pd.DataFrame, prev_close: float, target_date_str: str, manual: bool) -> dict:
    """Extract candidate data from a DataFrame (PM or regular)"""
    if df.empty:
        return None

    # Normalize timezone
    df.index = pd.to_datetime(df.index)
    if df.index.tz is None:
        df.index = df.index.tz_localize("UTC")
    df.index = df.index.tz_convert(ET)

    # Filter to target date
    target_date = datetime.strptime(target_date_str, "%Y-%m-%d").date()
    df = df[df.index.date == target_date]
    if df.empty:
        return None

    # PM window
    df_pm = df[(df.index.time >= PM_START) & (df.index.time < PM_END)]
    if df_pm.empty:
        # No PM data – use the latest available data (last 30 min)
        now_et = datetime.now(ET)
        df_recent = df[df.index >= now_et - timedelta(minutes=30)]
        if df_recent.empty:
            return None
        price = float(df_recent['Close'].iloc[-1])
        pm_volume = int(df_recent['Volume'].sum())
        pm_bars = len(df_recent)
        pm_high = float(df_recent['High'].max())
        pm_low = float(df_recent['Low'].min())
        pm_vwap = float((df_recent['Close'] * df_recent['Volume']).sum() / df_recent['Volume'].sum()) if pm_volume > 0 else price
        pm_dist_signed = None
        pm_data_quality = "LOW_DATA" if pm_bars < 5 else "GOOD_DATA"
        mode_suffix = "POST_MARKET"
    else:
        price = float(df_pm['Close'].iloc[-1])
        pm_volume = int(df_pm['Volume'].sum())
        pm_bars = len(df_pm)
        pm_high = float(df_pm['High'].max())
        pm_low = float(df_pm['Low'].min())
        pm_vwap = float((df_pm['Close'] * df_pm['Volume']).sum() / df_pm['Volume'].sum()) if pm_volume > 0 else price
        pm_dist_signed = ((price - pm_high) / pm_high * 100) if pm_high > 0 else None
        pm_data_quality = "GOOD_DATA" if pm_bars >= 5 else "LOW_DATA"
        mode_suffix = "PM"

    gap_pct = ((price - prev_close) / prev_close) * 100.0 if prev_close > 0 else 0

    # Simple score (just for sorting)
    score = 0
    score += min(max(gap_pct, 0) * 2, 30)
    score += min(pm_volume / 100000 * 20, 30) if pm_volume > 0 else 0
    if pm_dist_signed and pm_dist_signed >= 0:
        score += 25
    elif pm_dist_signed and pm_dist_signed >= -2:
        score += 15

    candidate = {
        "ticker": ticker,
        "price": price,
        "prev_close": prev_close,
        "gap_pct": gap_pct,
        "pm_volume": pm_volume,
        "pm_bars": pm_bars,
        "pm_high": pm_high,
        "pm_low": pm_low,
        "pm_vwap": pm_vwap,
        "pm_dist_signed": pm_dist_signed,
        "spread_pct": None,
        "event_score": round(min(100, max(0, score)), 1),
        "pm_data_quality": pm_data_quality,
        "mode": "MANUAL_REPLAY" if manual else "LIVE",
        "strategy_version": "V4.0",
        "data_version": "YFINANCE_V40",
        "scan_date": target_date_str,
        "source": mode_suffix,
    }
    return candidate


def scan_premarket(target_date_str: str = None, manual: bool = False) -> List[dict]:
    now_et = datetime.now(ET)
    if not target_date_str:
        target_date_str = now_et.strftime("%Y-%m-%d")

    in_pm = _is_in_pm_window(now_et)
    print(f"[Discovery] Premarket scan for {target_date_str} | ET: {now_et.strftime('%H:%M:%S')} | PM window: {in_pm}")

    universe = load_universe()
    if not universe:
        return []

    prev_closes = _get_previous_closes(universe, target_date_str)
    candidates = []

    # Use smaller batch for speed
    for i in range(0, len(universe), BATCH_SIZE):
        batch = universe[i:i+BATCH_SIZE]
        try:
            # Fetch 1-minute data for the last 2 days (covers PM and regular)
            pm_data = yf.download(" ".join(batch), period="2d", interval="1m", prepost=True,
                                  progress=False, threads=False)
        except Exception:
            continue

        for ticker in batch:
            prev_close = prev_closes.get(ticker)
            if not prev_close:
                continue

            try:
                if len(batch) == 1:
                    df = pm_data.copy()
                else:
                    if ticker not in pm_data.columns.get_level_values(0):
                        continue
                    df = pm_data[ticker].copy()

                df = df.dropna(subset=['Close'])
                if df.empty:
                    continue

                cand = _extract_candidate(ticker, df, prev_close, target_date_str, manual)
                if cand:
                    candidates.append(cand)

            except Exception:
                continue

    candidates.sort(key=lambda x: x.get('event_score', 0), reverse=True)
    print(f"[Discovery] Candidates found: {len(candidates)}")
    return candidates[:40]
