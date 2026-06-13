import pandas as pd
from alpaca.data.historical import StockHistoricalDataClient
from alpaca.data.requests import StockSnapshotRequest, StockBarsRequest
from alpaca.data.timeframe import TimeFrame
from datetime import datetime, timedelta
import pytz

from utils.config import (
    ALPACA_API_KEY, ALPACA_SECRET_KEY,
    MIN_PREMARKET_VOL, MAX_FLOAT
)

client = StockHistoricalDataClient(ALPACA_API_KEY, ALPACA_SECRET_KEY)
NY_TZ  = pytz.timezone("America/New_York")

# Hard Filters — מינימום בלבד
MIN_GAP_HARD      = 15.0
MIN_DOLLAR_VOLUME = 2_000_000
MIN_PM_VOLUME     = 500_000


def get_premarket_bars(ticker: str) -> list:
    try:
        now_ny          = datetime.now(NY_TZ)
        premarket_start = now_ny.replace(hour=4, minute=0, second=0, microsecond=0)
        if now_ny < premarket_start:
            premarket_start -= timedelta(days=1)
            now_ny = premarket_start.replace(hour=9, minute=30)
        if premarket_start >= now_ny:
            return []
        req = StockBarsRequest(
            symbol_or_symbols=ticker,
            timeframe=TimeFrame.Minute,
            start=premarket_start,
            end=now_ny,
            feed="iex",
        )
        bars_resp = client.get_stock_bars(req)
        df        = bars_resp.df
        if df is None or df.empty:
            return []
        if hasattr(df.index, "levels"):
            if ticker in df.index.get_level_values(0):
                return df.loc[ticker].reset_index().to_dict("records")
            return []
        return df.reset_index().to_dict("records")
    except Exception as e:
        print(f"[Premarket] bars error {ticker}: {e}")
        return []


def _get_vol(b: dict) -> int:
    return int(b.get("volume", b.get("v", 0)) or 0)


def _get_close(b: dict, fallback: float) -> float:
    return float(b.get("close", b.get("c", fallback)) or fallback)


def analyze_bars(bars: list, latest: float, now_ny: datetime) -> dict:
    """מחשב את כל מדדי Freshness מה-bars."""
    if not bars:
        return {
            "pm_volume": 0, "pm_high": latest,
            "pm_high_dist": 0, "pm_high_age": 999,
            "pullback_pct": 0, "momentum_5m": 0,
            "vwap": latest, "vwap_dist": 0, "vol_accel": 1.0,
        }

    pm_volume    = 0
    pm_high      = 0.0
    pm_high_time = None
    vwap_num     = 0.0
    total_vol    = 0

    for b in bars:
        vol = _get_vol(b)
        h   = float(b.get("high", b.get("h", 0)) or 0)
        c   = _get_close(b, latest)
        pm_volume += vol
        vwap_num  += c * vol
        total_vol += vol
        if h > pm_high:
            pm_high = h
            t = b.get("timestamp") or b.get("t")
            if t:
                try:
                    if isinstance(t, str):
                        from dateutil import parser as dtp
                        parsed = dtp.parse(t)
                        pm_high_time = NY_TZ.localize(parsed) \
                            if parsed.tzinfo is None else parsed
                    else:
                        pm_high_time = t
                except Exception:
                    pass

    if pm_high == 0:
        pm_high = latest

    vwap         = round(vwap_num / total_vol, 4) if total_vol > 0 else latest
    vwap_dist    = round(((latest - vwap) / vwap) * 100, 2) if vwap > 0 else 0
    pm_high_dist = round(((pm_high - latest) / latest) * 100, 2) if latest > 0 else 0
    pullback_pct = round(((pm_high - latest) / pm_high) * 100, 2) if pm_high > 0 else 0

    pm_high_age = 999
    if pm_high_time:
        try:
            if hasattr(pm_high_time, "tzinfo") and pm_high_time.tzinfo:
                pm_high_age = max(0, int((now_ny - pm_high_time).total_seconds() / 60))
        except Exception:
            pass

    # Momentum 5m
    momentum_5m = 0.0
    if len(bars) >= 5:
        try:
            p5 = _get_close(bars[-5], latest)
            if p5 > 0:
                momentum_5m = round(((latest - p5) / p5) * 100, 2)
        except Exception:
            pass

    # Volume Acceleration — 5 bars אחרונים vs 5 לפניהם
    vol_accel = 1.0
    if len(bars) >= 10:
        try:
            v5  = sum(_get_vol(b) for b in bars[-5:])
            v5p = sum(_get_vol(b) for b in bars[-10:-5])
            if v5p > 0:
                vol_accel = round(v5 / v5p, 2)
        except Exception:
            pass

    return {
        "pm_volume":    pm_volume,
        "pm_high":      round(pm_high, 2),
        "pm_high_dist": pm_high_dist,
        "pm_high_age":  pm_high_age,
        "pullback_pct": pullback_pct,
        "momentum_5m":  momentum_5m,
        "vwap":         round(vwap, 4),
        "vwap_dist":    vwap_dist,
        "vol_accel":    vol_accel,
    }


def calc_freshness(a: dict) -> float:
    """
    Freshness Score 0-100:
    PM High Age     25  — חדש = טוב
    Pullback        20  — קטן = טוב
    Momentum 5m     20  — חיובי = טוב
    Vol Acceleration 20  — עולה = טוב
    VWAP            15  — מעל = טוב
    """
    # Age: 0 דק' = 25, 60 דק'+ = 0
    age_score  = max(0.0, 25 - (a["pm_high_age"] / 2.4))

    # Pullback: 0% = 20, 20%+ = 0
    pull_score = max(0.0, 20 - (a["pullback_pct"] * 1.0))

    # Momentum 5m: -5% = 0, +5% = 20
    mom_score  = min(20.0, max(0.0, (a["momentum_5m"] + 5) * 2))

    # Volume Acceleration: 0.5x = 0, 2x+ = 20
    accel      = a.get("vol_accel", 1.0)
    accel_score = min(20.0, max(0.0, (accel - 0.5) * 13.33))

    # VWAP: -3% = 0, +3% = 15
    vwap_score = min(15.0, max(0.0, (a["vwap_dist"] + 3) * 2.5))

    return round(age_score + pull_score + mom_score + accel_score + vwap_score, 1)


def calc_momentum_score(gap_pct: float, pm_rvol: float, momentum_5m: float) -> float:
    """
    Momentum Score 0-100:
    Gap     40
    RVOL    30
    5m Mom  30
    """
    gap_s  = min(40.0, gap_pct * 0.6)
    rvol_s = min(30.0, pm_rvol * 6)
    mom_s  = min(30.0, max(0.0, (momentum_5m + 5) * 3))
    return round(gap_s + rvol_s + mom_s, 1)


def calc_pm_rvol(pm_volume: int, avg_daily_volume: int) -> float:
    if avg_daily_volume <= 0 or pm_volume <= 0:
        return 0.0
    return round(pm_volume / (avg_daily_volume * (330 / 390)), 2)


def scan_premarket(universe: pd.DataFrame) -> pd.DataFrame:
    tickers   = universe["ticker"].tolist()
    results   = []
    snapshots = {}
    now_ny    = datetime.now(NY_TZ)

    BATCH = 500
    for i in range(0, len(tickers), BATCH):
        batch = tickers[i:i + BATCH]
        try:
            req  = StockSnapshotRequest(symbol_or_symbols=batch)
            snap = client.get_stock_snapshot(req)
            snapshots.update(snap)
            print(f"[Premarket] Snapshot {i//BATCH+1}: {len(snap)} results")
        except Exception as e:
            print(f"[Premarket] Alpaca error: {e}")

    avg_vol_map = universe.set_index("ticker")["volume"].to_dict()
    float_map   = universe.set_index("ticker")["float"].to_dict() \
                  if "float" in universe.columns else {}

    for _, row in universe.iterrows():
        ticker = row["ticker"]
        snap   = snapshots.get(ticker)
        if snap is None:
            continue

        try:
            prev_close = snap.previous_daily_bar.close if snap.previous_daily_bar else None
            latest     = snap.latest_trade.price        if snap.latest_trade     else None
            if not prev_close or not latest or prev_close == 0:
                continue

            # HARD FILTER 1: Gap
            gap_pct = ((latest - prev_close) / prev_close) * 100
            if gap_pct < MIN_GAP_HARD:
                continue

            # Bars
            pm_bars  = get_premarket_bars(ticker)
            analysis = analyze_bars(pm_bars, latest, now_ny)
            pm_volume = analysis["pm_volume"]

            if pm_volume == 0 and snap.daily_bar:
                pm_volume = int(snap.daily_bar.volume)
                analysis["pm_volume"] = pm_volume

            # HARD FILTER 2: PM Volume
            if pm_volume < MIN_PM_VOLUME:
                continue

            float_shares  = int(float_map.get(ticker, 0))
            dollar_volume = latest * pm_volume
            avg_vol       = avg_vol_map.get(ticker, 0)
            pm_rvol       = calc_pm_rvol(pm_volume, avg_vol)
            daily_rvol    = round(pm_volume / avg_vol, 2) if avg_vol > 0 else 0.0

            # HARD FILTER 3: Float
            if float_shares <= 0 or float_shares > MAX_FLOAT:
                continue

            # HARD FILTER 4: Dollar Volume
            if dollar_volume < MIN_DOLLAR_VOLUME:
                continue

            # ציונים — לא פוסלים, רק מדרגים
            freshness      = calc_freshness(analysis)
            momentum_score = calc_momentum_score(gap_pct, pm_rvol, analysis["momentum_5m"])
            combined       = round(0.6 * freshness + 0.4 * momentum_score, 1)

            results.append({
                "ticker":          ticker,
                "price":           round(latest, 2),
                "prev_close":      round(prev_close, 2),
                "gap_pct":         round(gap_pct, 2),
                "pm_volume":       int(pm_volume),
                "pm_high":         analysis["pm_high"],
                "pm_high_dist":    analysis["pm_high_dist"],
                "pm_high_age":     analysis["pm_high_age"],
                "pullback_pct":    analysis["pullback_pct"],
                "momentum_5m":     analysis["momentum_5m"],
                "vwap":            analysis["vwap"],
                "vwap_dist":       analysis["vwap_dist"],
                "vol_accel":       analysis["vol_accel"],
                "dollar_volume":   int(dollar_volume),
                "daily_rvol":      daily_rvol,
                "pm_rvol":         pm_rvol,
                "vol_ratio":       pm_rvol,
                "float":           float_shares,
                "freshness":       freshness,
                "momentum_score":  momentum_score,
                "combined":        combined,
                "sector":          row.get("sector", "Unknown"),
                "industry":        row.get("industry", "Unknown"),
            })

            print(f"[✅] {ticker} gap={gap_pct:.1f}% "
                  f"fresh={freshness} mom={momentum_score} "
                  f"combined={combined}")

        except Exception as e:
            print(f"[Premarket] Error {ticker}: {e}")

    df = pd.DataFrame(results)
    if not df.empty:
        df.sort_values("combined", ascending=False, inplace=True)
        df.reset_index(drop=True, inplace=True)

    print(f"[Premarket] {len(df)} candidates passed filters.")
    return df
