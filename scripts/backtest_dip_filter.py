#!/usr/bin/env python3
"""
backtest_dip_filter.py V2 - Regime-Aware Backtest
Tests the Dip Filter under 3 macro regimes:
  - BULLISH: SPY > SMA20 AND SPY > SMA50
  - NEUTRAL: SPY between SMA50 and SMA20 (or within ±1.5% of SMA20)
  - BEARISH: SPY < SMA50 (or >2.5% below SMA20)
"""
import yfinance as yf
import pandas as pd
import numpy as np
from datetime import datetime, timedelta

# רשימת 100 מניות גדולות (S&P 100)
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

def get_market_regime():
    """
    מוריד נתוני SPY ומחזיר מילון של {date: regime}
    """
    print("[Regime] Fetching SPY data...")
    spy = yf.download("SPY", period="1y", interval="1d", progress=False, auto_adjust=False)
    if spy.empty:
        print("[Regime] ERROR: Could not fetch SPY data.")
        return {}

    if isinstance(spy.columns, pd.MultiIndex):
        spy.columns = spy.columns.get_level_values(0)

    spy['SMA20'] = spy['Close'].rolling(window=20).mean()
    spy['SMA50'] = spy['Close'].rolling(window=50).mean()

    regimes = {}
    for date, row in spy.iterrows():
        if pd.isna(row['SMA20']) or pd.isna(row['SMA50']):
            continue

        date_str = date.strftime("%Y-%m-%d")
        price = row['Close']
        sma20 = row['SMA20']
        sma50 = row['SMA50']

        # חישוב מרחק מה-SMA20 באחוזים
        dist_from_sma20_pct = ((price - sma20) / sma20) * 100

        # הגדרת מצב
        if price > sma20 and price > sma50:
            regime = "BULLISH"
        elif price < sma50 or dist_from_sma20_pct < -2.5:
            regime = "BEARISH"
        elif abs(dist_from_sma20_pct) <= 1.5:
            regime = "NEUTRAL"
        else:
            regime = "NEUTRAL"  # בין SMA50 ל-SMA20

        regimes[date_str] = regime

    print(f"[Regime] Calculated regimes for {len(regimes)} days.")
    bull = sum(1 for r in regimes.values() if r == "BULLISH")
    neut = sum(1 for r in regimes.values() if r == "NEUTRAL")
    bear = sum(1 for r in regimes.values() if r == "BEARISH")
    print(f"[Regime] Distribution: BULLISH={bull} | NEUTRAL={neut} | BEARISH={bear}")
    return regimes

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
    # 1. טוען מצבי שוק
    regimes = get_market_regime()
    if not regimes:
        print("Cannot proceed without market regime data.")
        return

    print(f"\nTesting {len(TICKERS)} tickers over the last 1 year...")
    end_date = datetime.today()
    start_date = end_date - timedelta(days=365)

    # 2. מריץ את הפילטר
    results_by_regime = {
        "BULLISH": [],
        "NEUTRAL": [],
        "BEARISH": []
    }
    skipped_no_regime = 0

    for idx, ticker in enumerate(TICKERS):
        if idx % 20 == 0:
            print(f"  Processing ticker {idx+1}/{len(TICKERS)}...")

        try:
            df = yf.download(ticker, start=start_date, end=end_date, progress=False)
            if df.empty or len(df) < 20: continue
            if isinstance(df.columns, pd.MultiIndex):
                df.columns = df.columns.get_level_values(0)

            for i in range(14, len(df)-5):
                if not check_dip_condition(df, i):
                    continue

                # --- בדיקת מצב שוק לאותו יום ---
                trade_date = df.index[i].strftime("%Y-%m-%d")
                if trade_date not in regimes:
                    skipped_no_regime += 1
                    continue

                regime = regimes[trade_date]
                r = simulate_trade(df, i)
                results_by_regime[regime].append(r)

        except Exception as e:
            continue

    # 3. מדפיס תוצאות
    print("\n" + "=" * 90)
    print("  REGIME-AWARE BACKTEST RESULTS")
    print("=" * 90)
    print(f"{'Regime':<12} | {'N':>4} | {'Win%':>6} | {'Avg R':>7} | {'Total R':>8} | {'Avg Win':>8} | {'Avg Loss':>9}")
    print("-" * 90)

    for regime in ["BULLISH", "NEUTRAL", "BEARISH"]:
        results = results_by_regime[regime]
        if not results:
            print(f"{regime:<12} | {0:>4} | {'N/A':>6} | {'N/A':>7} | {'N/A':>8} | {'N/A':>8} | {'N/A':>9}")
            continue

        n = len(results)
        wins = [r for r in results if r > 0]
        losses = [r for r in results if r <= 0]
        win_rate = 100.0 * len(wins) / n
        avg_r = np.mean(results)
        total_r = np.sum(results)
        avg_win = np.mean(wins) if wins else 0
        avg_loss = np.mean(losses) if losses else 0

        print(f"{regime:<12} | {n:>4} | {win_rate:>5.1f}% | {avg_r:>+7.3f} | {total_r:>+8.1f} | {avg_win:>+8.2f} | {avg_loss:>+9.2f}")

    print("-" * 90)

    # 4. סיכום
    print("\n=== VERDICT ===")
    bull = results_by_regime["BULLISH"]
    neut = results_by_regime["NEUTRAL"]
    bear = results_by_regime["BEARISH"]

    if bull:
        print(f"BULLISH: {len(bull)} trades, AvgR = {np.mean(bull):+.3f}")
    if neut:
        print(f"NEUTRAL: {len(neut)} trades, AvgR = {np.mean(neut):+.3f}")
    if bear:
        print(f"BEARISH: {len(bear)} trades, AvgR = {np.mean(bear):+.3f}")

    print("\nRECOMMENDATION:")
    print("  - If BULLISH AvgR > 1.0 → Keep strict filter (current strategy).")
    print("  - If NEUTRAL AvgR > 0.5 → Consider adding NEUTRAL mode in future.")
    print("  - If NEUTRAL AvgR <= 0  → Do NOT add NEUTRAL. Strict is better.")
    print("  - If BEARISH AvgR > 0 → Reconsider the macro filter entirely.")
    print("=" * 90)

if __name__ == "__main__":
    main()