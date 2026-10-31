#!/usr/bin/env python3
import yfinance as yf
import pandas as pd
import numpy as np
from datetime import datetime, timedelta

# רשימה עצמאית של 100 מניות גדולות (S&P 100) - לא תלויה בקבצים שלך
TICKERS = [
    "AAPL", "MSFT", "AMZN", "NVDA", "GOOGL", "META", "TSLA", "BRK-B", "UNH", "XOM",
    "JNJ", "JPM", "V", "PG", "MA", "HD", "CVX", "MRK", "ABBV", "LLY",
    "PEP", "KO", "AVGO", "COST", "WMT", "MCD", "TMO", "CSCO", "ACN", "ABT",
    "DHR", "LIN", "ADBE", "CRM", "TXN", "NFLX", "AMD", "PM", "NEE", "WFC",
    "BMY", "UPS", "RTX", "QCOM", "HON", "T", "LOW", "INTU", "SPGI", "CAT",
    "GS", "ELV", "DE", "BLK", "AXP", "BKNG", "PLD", "MDT", "SYK", "GILD",
    "ADI", "MMC", "VRTX", "C", "LMT", "ADP", "CB", "SBUX", "CI", "MO",
    "NOW", "ZTS", "PGR", "SCHW", "SO", "DUK", "BMY", "REGN", "VRTX", "BSX",
    "ETN", "ITW", "AON", "MDLZ", "CL", "CME", "EQIX", "SNPS", "CDNS", "KLAC",
    "LRCX", "PANW", "MU", "FTNT", "MRNA", "PYPL", "ADSK", "WDAY", "ROP", "APH"
]

def check_dip_condition(df, i):
    row = df.iloc[i]
    if not (10 <= row['Close'] <= 50): 
        return False
    prev_close = df.iloc[i-1]['Close']
    if prev_close == 0: return False
    gap_pct = ((row['Open'] - prev_close) / prev_close) * 100
    if gap_pct >= -2.0: 
        return False
    daily_range = ((row['High'] - row['Low']) / row['Close']) * 100
    if daily_range < 3.0: 
        return False
    return True

def simulate_trade(df, i):
    entry = df.iloc[i]['Open']
    stop = entry * 0.98
    for j in range(i+1, min(i+6, len(df))):
        day = df.iloc[j]
        if day['Low'] <= stop:
            return -1.0
        target = entry + (entry - stop) * 2
        if day['High'] >= target:
            return 2.0
    final_price = df.iloc[min(i+5, len(df)-1)]['Close']
    if entry == stop: return 0
    r_multiple = (final_price - entry) / (entry - stop)
    return r_multiple

def main():
    print(f"Testing {len(TICKERS)} large-cap tickers over the last 1 year...")
    
    end_date = datetime.today()
    start_date = end_date - timedelta(days=365)
    
    results = []
    
    for idx, ticker in enumerate(TICKERS):
        if idx % 20 == 0:
            print(f"  Processing ticker {idx+1}/{len(TICKERS)}...")
            
        try:
            df = yf.download(ticker, start=start_date, end=end_date, progress=False)
            if df.empty or len(df) < 20: continue
            if isinstance(df.columns, pd.MultiIndex):
                df.columns = df.columns.get_level_values(0)
            
            for i in range(14, len(df)-5):
                if check_dip_condition(df, i):
                    r = simulate_trade(df, i)
                    results.append(r)
        except Exception:
            continue

    print("\n" + "=" * 80)
    print("  BACKTEST RESULTS: DIP FILTER (1 Year, 100 Large-Caps)")
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