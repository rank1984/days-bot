#!/usr/bin/env python3
import yfinance as yf
import pandas as pd
import numpy as np
import random
import sys
from datetime import datetime, timedelta

# =====================================================================
# טעינת ה-Universe בדיוק כמו main.py (עם מנגנון הגנה)
# =====================================================================
try:
    from scanner.universe import load_universe
except ImportError:
    try:
        from scanner.universe import get_universe as load_universe
    except ImportError:
        print("[FATAL] Could not import load_universe from scanner.universe")
        sys.exit(1)

def check_dip_condition(df, i):
    """בודק אם ביום ה-i התקיימו תנאי הפילטר"""
    row = df.iloc[i]
    
    # תנאי 1: מחיר בין 10 ל-50
    if not (10 <= row['Close'] <= 50): 
        return False
    
    # תנאי 2: גאפ שלילי של יותר מ-2%
    prev_close = df.iloc[i-1]['Close']
    if prev_close == 0: return False
    gap_pct = ((row['Open'] - prev_close) / prev_close) * 100
    if gap_pct >= -2.0: 
        return False
    
    # תנאי 3: ATR (תנודתיות) גבוה - טווח יומי מעל 3%
    daily_range = ((row['High'] - row['Low']) / row['Close']) * 100
    if daily_range < 3.0: 
        return False
    
    return True

def simulate_trade(df, i):
    """מדמה עסקה: קונה בפתיחה של יום i, מוכר אחרי 5 ימים או בסטופ"""
    entry = df.iloc[i]['Open']
    stop = entry * 0.98 # סטופ של 2%
    
    # בדיקת 5 הימים הבאים
    for j in range(i+1, min(i+6, len(df))):
        day = df.iloc[j]
        if day['Low'] <= stop:
            return -1.0 # הפסד של 1R
        target = entry + (entry - stop) * 2 # יעד T1 (2R)
        if day['High'] >= target:
            return 2.0 # רווח של 2R
    
    # יציאה ביום ה-5
    final_price = df.iloc[min(i+5, len(df)-1)]['Close']
    if entry == stop: return 0
    r_multiple = (final_price - entry) / (entry - stop)
    return r_multiple

def main():
    print("Loading universe...")
    try:
        universe = load_universe()
        print(f"Loaded {len(universe)} tickers from scanner.universe")
    except Exception as e:
        print(f"[FATAL] load_universe() crashed: {e}")
        sys.exit(1)
    
    if not universe:
        print("[FATAL] Universe is empty. Check scanner/universe.py")
        sys.exit(1)

    # ניקח 100 מניות אקראיות כדי שהריצה תהיה מהירה
    if len(universe) > 100:
        universe = random.sample(universe, 100)
    
    print(f"Testing {len(universe)} random tickers over the last 1 year...")
    
    end_date = datetime.today()
    start_date = end_date - timedelta(days=365)
    
    results = []
    trades_found = 0
    
    for idx, ticker in enumerate(universe):
        if idx % 20 == 0:
            print(f"  Processing ticker {idx+1}/{len(universe)}...")
            
        try:
            df = yf.download(ticker, start=start_date, end=end_date, progress=False)
            if df.empty or len(df) < 20: continue
            if isinstance(df.columns, pd.MultiIndex):
                df.columns = df.columns.get_level_values(0)
            
            for i in range(14, len(df)-5):
                if check_dip_condition(df, i):
                    r = simulate_trade(df, i)
                    results.append(r)
                    trades_found += 1
        except Exception:
            continue

    print("\n" + "=" * 80)
    print("  BACKTEST RESULTS: DIP FILTER (1 Year, 100 Random Tickers)")
    print("=" * 80)
    
    if not results:
        print("  No trades found matching the filter.")
        print("  Try relaxing the conditions (e.g. gap < -1%, ATR > 2%)")
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
    if wins:
        print(f"  Avg Win:            {np.mean(wins):.2f}R")
    if losses:
        print(f"  Avg Loss:           {np.mean(losses):.2f}R")
    print("=" * 80)
    
    if avg_r > 0.3:
        print("  ✅ VERDICT: The Edge is REAL. Ready for live money.")
    elif avg_r > 0:
        print("  ⚠️ VERDICT: Marginal Edge. Need more data or tighter filter.")
    else:
        print("  ❌ VERDICT: Filter failed on historical data. Do NOT trade live.")

if __name__ == "__main__":
    main()