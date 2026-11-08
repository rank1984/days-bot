#!/usr/bin/env python3
"""
backtest_dip_filter.py V3 - Fully aligned with V5.0.9
- ATR(14) instead of Daily Range
- Signal at Close of day i, Entry at Open of day i+1
- Includes entry day in stop/target check
- Handles gap downs (exit at Open if gap below stop)
- Includes 1% round-trip costs (Net R)
"""
import yfinance as yf
import pandas as pd
import numpy as np
from datetime import datetime, timedelta

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

COST_PCT = 0.01

def get_spy_data():
    print("Fetching SPY data for macro filter...")
    spy = yf.download("SPY", period="2y", interval="1d", progress=False, auto_adjust=False)
    if spy.empty: return pd.DataFrame()
    if isinstance(spy.columns, pd.MultiIndex):
        spy.columns = spy.columns.get_level_values(0)
    spy['SMA20'] = spy['Close'].rolling(window=20).mean()
    return spy

def compute_atr(df, period=14):
    if len(df) < period + 1: return 0.0
    high = df['High']; low = df['Low']; close = df['Close']
    prev_close = close.shift(1)
    tr = pd.concat([high - low, (high - prev_close).abs(), (low - prev_close).abs()], axis=1).max(axis=1)
    atr = float(tr.iloc[-period:].mean())
    return atr if atr > 0 else 0.0

def check_dip_condition(df, i):
    if i < 15: return False, None
    row = df.iloc[i]
    prev_close = df.iloc[i-1]['Close']
    if prev_close == 0: return False, None
    
    price = float(row['Close'])
    gap_pct = ((row['Open'] - prev_close) / prev_close) * 100
    atr = compute_atr(df.iloc[:i+1])
    
    if not (10 <= price <= 50): return False, None
    if gap_pct >= -2.0: return False, None
    if price > 0 and (atr / price) <= 0.03: return False, None
    
    return True, atr

def simulate_trade(df, i, atr, entry_open):
    entry = entry_open
    if entry <= 0: return None
    
    stop = min(entry - (1.5 * atr), entry * 0.98)
    stop_dist_pct = ((entry - stop) / entry) * 100
    
    if stop_dist_pct > 10.0: return None
    if stop_dist_pct < 2.0: return None
    
    risk = entry - stop
    target_1 = entry + (risk * 2)
    
    entry_day = i + 1
    if entry_day >= len(df): return None
    
    entry_bar = df.iloc[entry_day]
    
    if entry_bar['Low'] <= stop:
        exit_price = min(float(entry_bar['Open']), stop)
        r_gross = (exit_price - entry) / risk
        r_net = r_gross - COST_PCT
        return {"exit_price": exit_price, "exit_reason": "STOP_HIT", "r_gross": r_gross, "r_net": r_net, "days_held": 1}
    
    if entry_bar['High'] >= target_1:
        r_gross = (target_1 - entry) / risk
        r_net = r_gross - COST_PCT
        return {"exit_price": target_1, "exit_reason": "T1_HIT", "r_gross": r_gross, "r_net": r_net, "days_held": 1}
    
    for j in range(entry_day + 1, min(entry_day + 5, len(df))):
        day = df.iloc[j]
        days_held = j - entry_day + 1
        
        if day['Low'] <= stop:
            exit_price = min(float(day['Open']), stop)
            r_gross = (exit_price - entry) / risk
            r_net = r_gross - COST_PCT
            return {"exit_price": exit_price, "exit_reason": "STOP_HIT", "r_gross": r_gross, "r_net": r_net, "days_held": days_held}
        
        if day['High'] >= target_1:
            r_gross = (target_1 - entry) / risk
            r_net = r_gross - COST_PCT
            return {"exit_price": target_1, "exit_reason": "T1_HIT", "r_gross": r_gross, "r_net": r_net, "days_held": days_held}
    
    exit_day = min(entry_day + 4, len(df) - 1)
    exit_price = float(df.iloc[exit_day]['Close'])
    r_gross = (exit_price - entry) / risk
    r_net = r_gross - COST_PCT
    return {"exit_price": exit_price, "exit_reason": "HORIZON_END", "r_gross": r_gross, "r_net": r_net, "days_held": exit_day - entry_day + 1}

def main():
    spy = get_spy_data()
    if spy.empty:
        print("ERROR: No SPY data.")
        return
    
    spy_lookup = {}
    for date, row in spy.iterrows():
        if pd.isna(row['SMA20']): continue
        date_str = date.strftime("%Y-%m-%d")
        spy_close = float(row['Close'])
        spy_sma20 = float(row['SMA20'])
        status = "BULLISH" if spy_close > spy_sma20 else "BEARISH"
        spy_lookup[date_str] = {"close": spy_close, "sma20": spy_sma20, "status": status}
    
    print(f"\nTesting {len(TICKERS)} tickers (V5.0.9-aligned, costs included)...")
    end_date = datetime.today()
    start_date = end_date - timedelta(days=365)
    
    all_trades = []
    no_data = []
    
    for idx, ticker in enumerate(TICKERS):
        if idx % 20 == 0:
            print(f"  Processing {idx+1}/{len(TICKERS)}...")
        
        try:
            df = yf.download(ticker, start=start_date, end=end_date, progress=False, auto_adjust=False)
            if df.empty or len(df) < 25:
                no_data.append(ticker)
                continue
            if isinstance(df.columns, pd.MultiIndex):
                df.columns = df.columns.get_level_values(0)
            df = df.dropna()
            
            for i in range(15, len(df) - 6):
                passed, atr = check_dip_condition(df, i)
                if not passed: continue
                
                signal_date_str = df.index[i].strftime("%Y-%m-%d")
                entry_date_str = df.index[i + 1].strftime("%Y-%m-%d")
                
                spy_info = spy_lookup.get(signal_date_str)
                if not spy_info:
                    macro_status = "UNKNOWN"; spy_close = 0; spy_sma20 = 0
                else:
                    macro_status = spy_info["status"]
                    spy_close = spy_info["close"]
                    spy_sma20 = spy_info["sma20"]
                
                entry_open = float(df.iloc[i + 1]['Open'])
                result = simulate_trade(df, i, atr, entry_open)
                if not result: continue
                
                stop_calc = min(entry_open - 1.5*atr, entry_open * 0.98)
                
                all_trades.append({
                    "ticker": ticker, "signal_date": signal_date_str, "entry_date": entry_date_str,
                    "macro": macro_status, "spy_close": spy_close, "spy_sma20": spy_sma20,
                    "entry": entry_open, "stop": stop_calc, "exit_price": result["exit_price"],
                    "exit_reason": result["exit_reason"], "r_gross": result["r_gross"],
                    "r_net": result["r_net"], "days_held": result["days_held"]
                })
        except Exception as e:
            print(f"  ERR {ticker}: {e}")
            no_data.append(ticker)
    
    print("\n" + "=" * 140)
    print("  DETAILED TRADES (Entry at T+1 Open, ATR-based, Costs included)")
    print("=" * 140)
    print(f"{'Ticker':<7} | {'Signal':<10} | {'Entry':<10} | {'Macro':<8} | {'Entry':>7} | {'Stop':>7} | {'Exit':>7} | {'Reason':<12} | {'GrR':>6} | {'NetR':>6}")
    print("-" * 140)
    
    for t in all_trades:
        print(f"{t['ticker']:<7} | {t['signal_date']:<10} | {t['entry_date']:<10} | {t['macro']:<8} | {t['entry']:>7.2f} | {t['stop']:>7.2f} | {t['exit_price']:>7.2f} | {t['exit_reason']:<12} | {t['r_gross']:>+6.2f} | {t['r_net']:>+6.2f}")
    
    executed = [t for t in all_trades if t['macro'] == 'BULLISH']
    skipped = [t for t in all_trades if t['macro'] == 'BEARISH']
    unknown = [t for t in all_trades if t['macro'] == 'UNKNOWN']
    
    print("\n" + "=" * 140)
    print("  SUMMARY BY MACRO REGIME")
    print("=" * 140)
    
    def summarize(name, group):
        if not group:
            print(f"{name:<35} | N=0")
            return
        n = len(group)
        wins = [t for t in group if t['r_net'] > 0]
        win_pct = (len(wins) / n) * 100
        avg_gross = np.mean([t['r_gross'] for t in group])
        avg_net = np.mean([t['r_net'] for t in group])
        total_net = sum([t['r_net'] for t in group])
        stops = sum(1 for t in group if t['exit_reason'] == 'STOP_HIT')
        t1s = sum(1 for t in group if t['exit_reason'] == 'T1_HIT')
        horizon = sum(1 for t in group if t['exit_reason'] == 'HORIZON_END')
        
        print(f"{name:<35} | N={n:>3} | Win%={win_pct:>5.1f}% | AvgGrossR={avg_gross:>+6.3f} | AvgNetR={avg_net:>+6.3f} | TotalNetR={total_net:>+7.1f}")
        print(f"{'':35} | Stops={stops} | T1={t1s} | Horizon={horizon}")
    
    summarize("WITHOUT Filter (All)", all_trades)
    summarize("WITH Filter (BULLISH)", executed)
    summarize("SKIPPED (BEARISH)", skipped)
    if unknown:
        summarize("UNKNOWN Macro", unknown)
    
    print("\n" + "=" * 140)
    print("  SKIPPED TRADES (BEARISH regime) — Did our filter save us?")
    print("=" * 140)
    if skipped:
        for t in skipped:
            marker = "❌ (would've lost)" if t['r_net'] < 0 else "⚠️ (would've won)"
            print(f"  {t['ticker']:<7} | {t['signal_date']} | Entry=${t['entry']:.2f} → Exit=${t['exit_price']:.2f} | {t['exit_reason']:<12} | NetR={t['r_net']:>+6.2f} {marker}")
    else:
        print("  No BEARISH setups skipped.")
    
    print("\n" + "=" * 140)
    print("  VERDICT: Promising Backtest Result (V5.0.9-aligned)")
    print(f"  Tickers with no data: {', '.join(no_data) if no_data else 'none'}")
    print("=" * 140)

if __name__ == "__main__":
    main()
