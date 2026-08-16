#!/usr/bin/env python3
"""
DAYS-BOT Trigger Monitor – checks watchlist for confirmed breakouts
"""
import yfinance as yf
from datetime import datetime
from zoneinfo import ZoneInfo
from watchlist_manager import WatchlistManager

ET = ZoneInfo("America/New_York")
MARKET_OPEN_MINUTES = 9 * 60 + 30
MARKET_CLOSE_MINUTES = 16 * 60

def now_et():
    return datetime.now(ET)

def is_market_open():
    now = now_et()
    if now.weekday() >= 5:
        return False
    minutes = now.hour * 60 + now.minute
    return MARKET_OPEN_MINUTES <= minutes < MARKET_CLOSE_MINUTES

def check_breakout(ticker, trigger_price):
    try:
        data = yf.Ticker(ticker).history(period="1d", interval="1m", prepost=False)
        if data.empty or len(data) < 6:
            return False, None
        current_price = float(data["Close"].iloc[-1])
        prev_volumes = data["Volume"].iloc[-6:-1]
        avg_volume = prev_volumes.mean()
        current_volume = float(data["Volume"].iloc[-1])
        if avg_volume <= 0:
            return False, current_price
        volume_ratio = current_volume / avg_volume
        price_ok = current_price >= float(trigger_price)
        volume_ok = volume_ratio >= 1.20
        if price_ok and volume_ok:
            print(f"[Trigger] BREAKOUT {ticker} price=${current_price:.2f} trigger=${trigger_price:.2f} vol={volume_ratio:.2f}x")
            return True, current_price
        print(f"[Trigger] {ticker} ${current_price:.2f} / Trigger ${trigger_price:.2f} / Vol {volume_ratio:.2f}x")
        return False, current_price
    except Exception as e:
        print(f"[Trigger] {ticker} ERROR: {e}")
        return False, None

def monitor_trigger():
    now = now_et()
    print(f"[TriggerMonitor] {now.strftime('%Y-%m-%d %H:%M:%S %Z')}")
    if not is_market_open():
        print("[TriggerMonitor] Market closed.")
        return
    wm = WatchlistManager()
    watchlist = wm.get_active_watchlist()
    if not watchlist:
        print("[TriggerMonitor] Watchlist empty.")
        return
    for item in watchlist:
        ticker = item["ticker"]
        trigger = item.get("trigger_price")
        status = item.get("status")
        if not trigger or status in ("EXECUTED", "CLOSED"):
            continue
        breakout, breakout_price = check_breakout(ticker, trigger)
        if breakout and breakout_price is not None:
            wm.mark_ready(ticker, breakout_price)
            print(f"[TriggerMonitor] ✅ {ticker} → READY @ ${breakout_price:.2f}")

if __name__ == "__main__":
    monitor_trigger()
