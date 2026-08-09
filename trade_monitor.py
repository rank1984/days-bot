#!/usr/bin/env python3
"""
Trade Monitor – tracks open trades and executes exits
"""
import yfinance as yf
import time
from datetime import datetime
from database.db import get_open_trades, update_trade_monitor

MARKET_OPEN = 9.5   # 09:30 ET
MARKET_CLOSE = 16.0 # 16:00 ET

def is_market_open() -> bool:
    now = datetime.now()
    if now.weekday() >= 5:
        return False
    hour = now.hour + now.minute / 60.0
    return MARKET_OPEN <= hour <= MARKET_CLOSE

def update_all_trades():
    trades = get_open_trades()
    if not trades:
        print("[TradeMonitor] No open trades.")
        return
    
    print(f"[TradeMonitor] Found {len(trades)} open trades")
    updated = 0
    
    for trade in trades:
        ticker = trade['ticker']
        entry = trade['entry_price']
        tp1 = trade.get('tp1', 0)
        tp2 = trade.get('tp2', 0)
        stop = trade.get('stop_price', 0)
        entry_time = datetime.fromisoformat(trade['entry_time'])
        
        try:
            data = yf.Ticker(ticker).history(period="1d", interval="1m")
            if data.empty:
                continue
            
            last_price = data['Close'].iloc[-1]
            high = data['High'].max()
            low = data['Low'].min()
            
            mfe = ((high - entry) / entry) * 100 if entry else 0
            mae = ((low - entry) / entry) * 100 if entry else 0
            
            # ====== בדיקת יציאה ======
            exit_reason = None
            exit_price = None
            pnl = None
            win = None
            
            # 1. Stop Loss
            if stop > 0 and low <= stop:
                exit_reason = "STOP"
                exit_price = stop
                pnl = ((stop - entry) / entry) * 100
                win = 0
                print(f"[TradeMonitor] 🔴 {ticker} STOP HIT @ {stop:.2f}")
            
            # 2. TP1
            elif tp1 > 0 and high >= tp1:
                exit_reason = "TP1"
                exit_price = tp1
                pnl = ((tp1 - entry) / entry) * 100
                win = 1
                print(f"[TradeMonitor] 🟢 {ticker} TP1 HIT @ {tp1:.2f}")
            
            # 3. TP2 (Runner)
            elif tp2 > 0 and high >= tp2:
                exit_reason = "TP2"
                exit_price = tp2
                pnl = ((tp2 - entry) / entry) * 100
                win = 1
                print(f"[TradeMonitor] 🟢 {ticker} TP2 HIT @ {tp2:.2f}")
            
            # 4. Time Exit (15 min before close)
            else:
                now = datetime.now()
                hour = now.hour + now.minute / 60.0
                if hour >= MARKET_CLOSE - 0.25:  # 15 דקות לפני סגירה
                    exit_reason = "TIME"
                    exit_price = last_price
                    pnl = ((last_price - entry) / entry) * 100
                    win = 1 if pnl > 0 else 0
                    print(f"[TradeMonitor] ⏰ {ticker} TIME EXIT @ {last_price:.2f}")
            
            # ====== ביצוע עדכון ======
            if exit_reason:
                update_trade_monitor(
                    ticker,
                    current_price=exit_price,
                    high=high,
                    low=low,
                    mfe=mfe,
                    mae=mae,
                    tp1_hit=(exit_reason == "TP1"),
                    tp2_hit=(exit_reason == "TP2"),
                    stop_hit=(exit_reason == "STOP"),
                    exit_price=exit_price,
                    pnl=pnl,
                    win=win
                )
                print(f"[TradeMonitor] ✅ {ticker} closed: {exit_reason} | PnL: {pnl:.2f}%")
            else:
                # רק עדכון נתונים
                update_trade_monitor(
                    ticker,
                    current_price=last_price,
                    high=high,
                    low=low,
                    mfe=mfe,
                    mae=mae
                )
                print(f"[TradeMonitor] ✅ {ticker} updated: ${last_price:.2f} | MFE: {mfe:.2f}% | MAE: {mae:.2f}%")
            
            updated += 1
            
        except Exception as e:
            print(f"[TradeMonitor] ❌ {ticker} failed: {e}")
    
    print(f"[TradeMonitor] Updated {updated} trades")

if __name__ == "__main__":
    update_all_trades()
