#!/usr/bin/env python3
"""
DAYS-BOT Trade Monitor – updates open trades with MFE/MAE, closes on TP/Stop/Time
"""
import yfinance as yf
from datetime import datetime
from zoneinfo import ZoneInfo
from database.db import get_open_trades, update_trade_monitor

ET = ZoneInfo("America/New_York")
MARKET_CLOSE_MINUTES = 16 * 60

def now_et():
    return datetime.now(ET)

def is_close_time():
    now = now_et()
    minutes = now.hour * 60 + now.minute
    return minutes >= MARKET_CLOSE_MINUTES - 15

def both_tp_and_stop_hit(high, low, tp1, stop):
    return tp1 > 0 and stop > 0 and high >= tp1 and low <= stop

def update_trades():
    trades = get_open_trades()
    if not trades:
        print("[TradeMonitor] No open trades.")
        return

    for trade in trades:
        ticker = trade['ticker']
        entry = trade['entry_price']
        entry_time = datetime.fromisoformat(trade['entry_time'])
        tp1 = trade.get('tp1', 0)
        tp2 = trade.get('tp2', 0)
        stop = trade.get('stop_price', 0)

        try:
            data = yf.Ticker(ticker).history(period="1d", interval="1m")
            if data.empty:
                continue

            # Filter data after entry time
            data.index = data.index.tz_convert(None)
            entry_time_naive = entry_time.replace(tzinfo=None)
            data_after_entry = data[data.index >= entry_time_naive]
            if data_after_entry.empty:
                continue

            last_price = data_after_entry['Close'].iloc[-1]
            high = data_after_entry['High'].max()
            low = data_after_entry['Low'].min()

            mfe = ((high - entry) / entry) * 100
            mae = ((low - entry) / entry) * 100

            exit_reason = None
            exit_price = None
            pnl = None
            win = None

            # Check for both TP and Stop in same candle (conservative: Stop first)
            if both_tp_and_stop_hit(high, low, tp1, stop):
                exit_reason = "STOP"
                exit_price = stop
                pnl = ((stop - entry) / entry) * 100
                win = 0
                print(f"[TradeMonitor] ⚠️ {ticker} both TP and Stop in same candle → STOP (conservative)")

            # TP2 first (since if TP2 hit, TP1 also hit)
            elif tp2 > 0 and high >= tp2:
                exit_reason = "TP2"
                exit_price = tp2
                pnl = ((tp2 - entry) / entry) * 100
                win = 1
            elif tp1 > 0 and high >= tp1:
                exit_reason = "TP1"
                exit_price = tp1
                pnl = ((tp1 - entry) / entry) * 100
                win = 1
            elif stop > 0 and low <= stop:
                exit_reason = "STOP"
                exit_price = stop
                pnl = ((stop - entry) / entry) * 100
                win = 0
            elif is_close_time():
                exit_reason = "TIME"
                exit_price = last_price
                pnl = ((last_price - entry) / entry) * 100
                win = 1 if pnl > 0 else 0

            if exit_reason:
                update_trade_monitor(
                    ticker,
                    current_price=exit_price,
                    high=high,
                    low=low,
                    mfe=mfe,
                    mae=mae,
                    tp1_hit=(exit_reason=="TP1"),
                    tp2_hit=(exit_reason=="TP2"),
                    stop_hit=(exit_reason=="STOP"),
                    exit_price=exit_price,
                    pnl=pnl,
                    win=win
                )
                print(f"[TradeMonitor] ✅ {ticker} closed: {exit_reason} | PnL: {pnl:.2f}%")
            else:
                update_trade_monitor(ticker, current_price=last_price, high=high, low=low, mfe=mfe, mae=mae)
                print(f"[TradeMonitor] ✅ {ticker} updated: ${last_price:.2f} | MFE: {mfe:.2f}% | MAE: {mae:.2f}%")

        except Exception as e:
            print(f"[TradeMonitor] ❌ {ticker} error: {e}")

if __name__ == "__main__":
    update_trades()
