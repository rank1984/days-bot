#!/usr/bin/env python3
"""
Trade Monitor – tracks open trades and updates MFE/MAE/TP/Stop
"""
import yfinance as yf
import time
from datetime import datetime, timedelta
from typing import Dict, List, Any
from database.db import get_open_trades, update_trade_monitor

MARKET_OPEN = 9.5  # 09:30 ET
MARKET_CLOSE = 16.0  # 16:00 ET

def is_market_open() -> bool:
    now = datetime.now()
    if now.weekday() >= 5:  # Weekend
        return False
    hour = now.hour + now.minute / 60.0
    return MARKET_OPEN <= hour <= MARKET_CLOSE

def update_all_trades():
    """מעדכן את כל העסקאות הפתוחות"""
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
        
        try:
            # שליפת נתונים אחרונים (תוך 5 דקות)
            data = yf.Ticker(ticker).history(period="1d", interval="1m")
            if data.empty:
                continue
            
            last_price = data['Close'].iloc[-1]
            high = data['High'].max()
            low = data['Low'].min()
            
            # חישוב MFE/MAE
            mfe = ((high - entry) / entry) * 100 if entry else 0
            mae = ((low - entry) / entry) * 100 if entry else 0
            
            # בדיקה אם TP1/TP2/Stop הושגו
            tp1_hit = high >= tp1 if tp1 else False
            tp2_hit = high >= tp2 if tp2 else False
            stop_hit = low <= stop if stop else False
            
            # יציאה לפי תזמון (ליד סגירה)
            now = datetime.now()
            hour = now.hour + now.minute / 60.0
            if hour >= MARKET_CLOSE - 0.15:  # 15 דקות לפני סגירה
                exit_price = last_price
                exit_time = now.isoformat()
                pnl = ((exit_price - entry) / entry) * 100
                win = 1 if pnl > 0 else 0
                update_trade_monitor(
                    ticker, current_price=last_price, high=high, low=low,
                    mfe=mfe, mae=mae, tp1_hit=tp1_hit, tp2_hit=tp2_hit,
                    stop_hit=stop_hit, exit_price=exit_price, pnl=pnl, win=win
                )
                print(f"[TradeMonitor] ✅ {ticker} closed at {exit_price:.2f} (PnL: {pnl:.2f}%)")
            else:
                # רק עדכון נתונים (בלי יציאה)
                update_trade_monitor(
                    ticker, current_price=last_price, high=high, low=low,
                    mfe=mfe, mae=mae, tp1_hit=tp1_hit, tp2_hit=tp2_hit,
                    stop_hit=stop_hit
                )
                print(f"[TradeMonitor] ✅ {ticker} updated: ${last_price:.2f} | MFE: {mfe:.2f}% | MAE: {mae:.2f}%")
            
            updated += 1
            
        except Exception as e:
            print(f"[TradeMonitor] ❌ {ticker} failed: {e}")
    
    print(f"[TradeMonitor] Updated {updated} trades")

def run_continuous(interval: int = 60):
    """הרצה רציפה כל X שניות (תוך שעות המסחר)"""
    print(f"[TradeMonitor] Starting continuous monitor (interval={interval}s)")
    while True:
        try:
            if is_market_open():
                update_all_trades()
            else:
                print("[TradeMonitor] Market closed. Sleeping...")
            time.sleep(interval)
        except KeyboardInterrupt:
            print("[TradeMonitor] Stopped by user.")
            break
        except Exception as e:
            print(f"[TradeMonitor] Error: {e}")
            time.sleep(10)

if __name__ == "__main__":
    # הרצה אחת – לבדיקה
    update_all_trades()
    
    # הרצה רציפה (לשימוש ב-GitHub Actions או מקומי)
    # run_continuous(interval=60)
