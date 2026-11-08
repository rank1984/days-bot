#!/usr/bin/env python3
import yfinance as yf
import pandas as pd
import numpy as np
from datetime import datetime, timedelta

# רשימת 100 מניות גדולות (S&P 100) - בדיוק כמו קודם
TICKERS = [
    "AAPL", "MSFT", "AMZN", "NVDA", "GOOGL", "META", "TSLA", "BRK-B", "UNH", "XOM",
    "JNJ", "JPM", "V", "PG", "MA", "HD", "CVX", "MRK", "ABBV", "LLY",
    "PEP", "KO", "AVGO", "COST", "WMT", "MCD", "TMO", "CSCO", "ACN", "ABT",
    "DHR", "LIN", "ADBE", "CRM", "TXN", "NFLX", "AMD", "PM", "NEE", "WFC",
    "BMY", "UPS", "RTX", "QCOM", "HON", "T", "LOW", "INTU", "SPGI", "CAT",
    "GS", "ELV", "DE", "BLK", "AXP", "BKNG", "PLD", "MDT", "SYK", "GILD",
    "ADI", "MMC", "VRTX", "C", "LMT", "ADP", "CB", "SBUX", "CI", "MO",
    "NOW", "ZTS", "PGR", "SCHW", "SO", "DUK", "REGN", "BSX", "ETN", "ITW",
    "AON", "MDLZ", "CL", "CME", "EQIX", "SNPS", "CDNS", "KLAC",
    "LRCX", "PANW", "MU", "FTNT", "MRNA", "PYPL", "ADSK", "WDAY", "ROP", "APH"
]

def get_bullish_days():
    """מוריד SPY ומחזיר סט של תאריכים שבהם SPY היה מעל SMA20"""
    print("Fetching SPY data for macro filter...")
    spy = yf.download("SPY", period="1y", interval="1d", progress=False, auto_adjust=False)
    if spy.empty:
        return set()
    
    if isinstance(spy.columns, pd.MultiIndex):
        spy.columns = spy.columns.get_level_values(0)
        
    spy['SMA20'] = spy['Close'].rolling(window=20).mean()
    
    bullish_days = set()
    for date, row in spy.iterrows():
        if pd.notna(row['SMA20']) and row['Close'] > row['SMA20']:
            bullish_days.add(date.strftime("%Y-%m-%d"))
            
    print(f"Found {len(bullish_days)} bullish days out of {len(spy)} total days.")
    return bullish_days

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
    bullish_days = get_bullish_days()
    if not bullish_days:
        print("No bullish days found. Cannot run backtest.")
        return

    print(f"\nTesting {len(TICKERS)} tickers with MACRO FILTER (only trading on bullish days)...")
    end_date = datetime.today()
    start_date = end_date - timedelta(days=365)
    
    results = []
    skipped_due_to_macro = 0
    
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
                    trade_date = df.index[i].strftime("%Y-%m-%d")
                    
                    # --- הפילטר המאקרו ---
                    if trade_date not in bullish_days:
                        skipped_due_to_macro += 1
                        continue
                        
                    r = simulate_trade(df, i)
                    results.append(r)
        except Exception:
            continue

    print("\n" + "=" * 80)
    print("  BACKTEST WITH MACRO FILTER (SPY > SMA20)")
    print("=" * 80)
    print(f"  Trades skipped due to BEARISH market: {skipped_due_to_macro}")
    
    if not results:
        print("  No trades executed under bullish conditions.")
        return

    n = len(results)
    wins = [r for r in results if r > 0]
    losses = [r for r in results if r <= 0]
    
    win_rate = (len(wins) / n) * 100
    avg_r = np.mean(results)
    total_r = np.sum(results)
    
    print(f"  Total Trades Executed: {n}")
    print(f"  Win Rate:              {win_rate:.1f}%")
    print(f"  Avg R per Trade:       {avg_r:+.3f}R")
    print(f"  Total Return:          {total_r:+.1f}R")
    print("=" * 80)
    
    if avg_r > 0.5:
        print("  ✅ VERDICT: The Macro Filter SAVES the strategy. Edge is real.")
    elif avg_r > 0:
        print("  ⚠️ VERDICT: Marginal. Macro filter helps, but edge is thin.")
    else:
        print("  ❌ VERDICT: Even with macro filter, the Dip strategy fails.")

if __name__ == "__main__":
    main()
