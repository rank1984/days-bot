#!/usr/bin/env python3
import yfinance as yf
import pandas as pd
import numpy as np
import random
from datetime import datetime, timedelta
import sys
import os

# טעינת רשימת המניות
try:
    from scanner.universe import load_universe
except ImportError:
    print("Could not load universe.")
    sys.exit(1)

def check_dip_condition(df, i):
    """בודק אם ביום ה-i התקיימו תנאי הפילטר"""
    row = df.iloc[i]
    
    # תנאי 1: מחיר בין 10 ל-50
    if not (10 <= row['Close'] <= 50): return False
    
    # תנאי 2: גאפ שלילי של יותר מ-2% (פתיחה נמוכה מהסגירה הקודמת)
    prev_close = df.iloc[i-1]['Close']
    gap_pct = ((row['Open'] - prev_close) / prev_close) * 100
    if gap_pct >= -2.0: return False
    
    # תנאי 3: ATR (תנודתיות) גבוה - נשתמש בטווח היומי (High-Low) כפרוקסי ל-ATR
    # ATR אמיתי דורש חישוב של 14 יום. כאן נבדוק אם הטווח היומי הוא מעל 3%
    daily_range = ((row['High'] - row['Low']) / row['Close']) * 100
    if daily_range < 3.0: return False
    
    return True

def simulate_trade(df, i):
    """מדמה עסקה: קונה בפתיחה של יום i, מוכר אחרי 5 ימים או בסטופ"""
    entry = df.iloc[i]['Open']
    # סטופ של 2% מתחת לכניסה (כמו בבוט)
    stop = entry * 0.98
    
    # בדיקת 5 הימים הבאים
    for j in range(i+1, min(i+6, len(df))):
        day = df.iloc[j]
        # אם נגע בסטופ
        if day['Low'] <= stop:
            return -1.0 # הפסד של 1R
        # אם הגיע ליעד T1 (2R)
        target = entry + (entry - stop) * 2
        if day['High'] >= target:
            return 2.0 # רווח של 2R
    
    # אם לא הגיע לאף אחד מהם, יוצאים ביום ה-5 לפי מחיר הסגירה
    final_price = df.iloc[min(i+5, len(df)-1)]['Close']
    r_multiple = (final_price - entry) / (entry - stop)
    return r_multiple

def main():
    print("Loading universe...")
    universe = load_universe()
    
    # ניקח 100 מניות אקראיות כדי שהריצה תהיה מהירה (אפשר להגדיל ל-500)
    if len(universe) > 100:
        universe = random.sample(universe, 100)
    
    print(f"Testing {len(universe)} tickers over the last 1 year...")
    
    end_date = datetime.today()
    start_date = end_date - timedelta(days=365)
    
    results = []
    trades_found = 0
    
    for ticker in universe:
        try:
            # הורדת נתונים
            df = yf.download(ticker, start=start_date, end=end_date, progress=False)
            if df.empty or len(df) < 20: continue
            if isinstance(df.columns, pd.MultiIndex):
                df.columns = df.columns.get_level_values(0)
            
            # מעבר על כל יום
            for i in range(14, len(df)-5):
                if check_dip_condition(df, i):
                    r = simulate_trade(df, i)
                    results.append(r)
                    trades_found += 1
        except Exception as e:
            continue

    print("\n" + "=" * 80)
    print("  BACKTEST RESULTS: DIP FILTER (1 Year, 100 Random Tickers)")
    print("=" * 80)
    
    if not results:
        print("  No trades found matching the filter.")
        return

    n = len(results)
    wins = [r for r in results if r > 0]
    losses = [r for r in results if r <= 0]
    
    win_rate = (len(wins) / n) * 100
    avg_r = np.mean(results)
    total_r = np.sum(results)
    
    print(f"  Total Trades Found: {n}")
    print(f"  Win Rate:           {win_rate:.1f}%")
    print(f"  Avg R per Trade:    {avg_r:+.3f}R")
    print(f"  Total Return:       {total_r:+.1f}R")
    print(f"  Avg Win:            {np.mean(wins):.2f}R" if wins else "  No wins")
    print(f"  Avg Loss:           {np.mean(losses):.2f}R" if losses else "  No losses")
    print("=" * 80)
    
    if avg_r > 0.3:
        print("  ✅ VERDICT: The Edge is REAL. Ready for live money.")
    elif avg_r > 0:
        print("  ⚠️ VERDICT: Marginal Edge. Need more data or tighter filter.")
    else:
        print("  ❌ VERDICT: Filter failed on historical data. Do NOT trade live.")

if __name__ == "__main__":
    main()