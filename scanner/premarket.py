"""
DAYS-BOT V3.2 – Premarket Scanner (Alpaca)
"""
import pandas as pd
from datetime import datetime, time
import pytz
from typing import List
from alpaca.data.historical import StockHistoricalDataClient
from alpaca.data.requests import StockBarsRequest
from alpaca.data.timeframe import TimeFrame
from utils.config import ALPACA_API_KEY, ALPACA_SECRET_KEY, DISCOVERY_MIN_PRICE, DISCOVERY_MAX_PRICE, DISCOVERY_MIN_GAP, DISCOVERY_MAX_GAP, VALIDATION_MIN_PM_VOLUME_ABS, VALIDATION_MIN_PM_BARS, VALIDATION_MAX_PM_DIST, VALIDATION_MIN_VWAP_DIST
from scanner.universe import load_universe

ET = pytz.timezone("America/New_York")

def scan_premarket(target_date_str: str = None) -> List[dict]:
    now_et = datetime.now(ET)
    if target_date_str is None:
        target_date_str = now_et.strftime("%Y-%m-%d")
    print(f"[Premarket V3.2] Scanning at {now_et.strftime('%H:%M:%S')} ET")

    universe = load_universe()
    if not universe:
        return []

    # חיבור ל-Alpaca
    client = StockHistoricalDataClient(ALPACA_API_KEY, ALPACA_SECRET_KEY)

    # PM window: 04:00 – now (or 09:30)
    pm_start = ET.localize(datetime.combine(now_et.date(), time(4, 0)))
    pm_end = min(now_et, ET.localize(datetime.combine(now_et.date(), time(9, 30))))

    # 1. שליפת סגירות קודמות (5 ימים)
    # נשתמש ב-Alpaca לשליפת יומית
    daily_req = StockBarsRequest(
        symbol_or_symbols=universe,
        timeframe=TimeFrame.Day,
        start=now_et - pd.Timedelta(days=5),
        end=now_et,
    )
    daily_bars = client.get_stock_bars(daily_req).data

    prev_closes = {}
    for symbol, bars in daily_bars.items():
        if bars:
            prev_closes[symbol] = bars[-1].close

    # 2. שליפת 1-min bars לפרה-מרקט
    pm_req = StockBarsRequest(
        symbol_or_symbols=universe,
        timeframe=TimeFrame.Minute,
        start=pm_start,
        end=pm_end,
    )
    pm_bars = client.get_stock_bars(pm_req).data

    candidates = []
    for symbol, bars in pm_bars.items():
        if not bars:
            continue
        df = pd.DataFrame([{
            'time': b.timestamp,
            'open': b.open,
            'high': b.high,
            'low': b.low,
            'close': b.close,
            'volume': b.volume
        } for b in bars])
        df.set_index('time', inplace=True)

        price = df['close'].iloc[-1]
        prev_close = prev_closes.get(symbol)
        if not prev_close:
            continue

        # Hard Filters
        if price < DISCOVERY_MIN_PRICE or price > DISCOVERY_MAX_PRICE:
            continue
        gap_pct = ((price - prev_close) / prev_close) * 100
        if gap_pct < DISCOVERY_MIN_GAP or gap_pct > DISCOVERY_MAX_GAP:
            continue

        # PM stats
        pm_volume = int(df['volume'].sum())
        if pm_volume < VALIDATION_MIN_PM_VOLUME_ABS:
            continue
        pm_high = df['high'].max()
        pm_low = df['low'].min()
        pm_vwap = (df['close'] * df['volume']).sum() / df['volume'].sum() if df['volume'].sum() > 0 else df['close'].mean()
        pm_dist_signed = ((price - pm_high) / pm_high) * 100 if pm_high > 0 else None
        if pm_dist_signed is None or pm_dist_signed < -VALIDATION_MAX_PM_DIST:
            continue
        if price < pm_vwap * (1 + VALIDATION_MIN_VWAP_DIST):
            continue

        # Score (פשוט)
        score = 0.0
        score += min(max(gap_pct, 0) * 2, 30)
        score += min((pm_volume / 100_000) * 20, 30)
        if pm_dist_signed >= 0:
            score += 25
        elif pm_dist_signed >= -2:
            score += 15
        elif pm_dist_signed >= -5:
            score += 5
        score = round(min(100, max(0, score)), 1)

        grade = "A" if score >= 70 else "B" if score >= 55 else "C" if score >= 40 else "WATCH"

        candidate = {
            "ticker": symbol,
            "price": price,
            "gap_pct": gap_pct,
            "pm_volume": pm_volume,
            "pm_high": pm_high,
            "pm_low": pm_low,
            "pm_vwap": pm_vwap,
            "pm_dist_signed": pm_dist_signed,
            "opportunity_score": score,
            "grade": grade,
            "state": "WATCH",
            "spread_pct": None,   # Alpaca לא נותן spread בפרה-מרקט
            "spread_status": "UNAVAILABLE",
            "pm_data_quality": "GOOD_DATA",
            "mode": "V3.2",
            "strategy_version": "V3.2",
            "data_version": "ALPACA"
        }
        candidates.append(candidate)

    candidates.sort(key=lambda x: x['opportunity_score'], reverse=True)
    return candidates[:20]
