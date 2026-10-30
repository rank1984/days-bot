#!/usr/bin/env python3
import sqlite3
import os
import sys
import statistics
import yfinance as yf
import pandas as pd

DB_PATH = os.environ.get("DB_PATH", "data/alerts.db")

def get_conn():
    return sqlite3.connect(DB_PATH)

def fetch_data(conn):
    query = """
        SELECT s.scan_date, s.price, s.gap_pct, s.atr, o.net_r
        FROM outcomes o
        JOIN snapshots s ON s.snapshot_id = o.snapshot_id
        WHERE o.net_r_status = 'VALID'
    """
    cur = conn.cursor()
    cur.execute(query)
    rows = cur.fetchall()
    return [dict(zip(['scan_date', 'price', 'gap_pct', 'atr', 'net_r'], row)) for row in rows]

def calc_stats(rows):
    if not rows: return None
    net_rs = [r['net_r'] for r in rows if r.get('net_r') is not None]
    if not net_rs: return None
    wins = [r for r in net_rs if r > 0]
    return {
        'n': len(net_rs),
        'win_pct': round(100.0 * len(wins) / len(net_rs), 1),
        'avg_r': round(statistics.mean(net_rs), 3),
        'total_r': round(sum(net_rs), 1)
    }

def is_dip_trade(t):
    price = t.get('price') or 0
    gap = t.get('gap_pct') or 0
    atr = t.get('atr') or 0
    return (10 <= price <= 50) and (gap < -2) and (price > 0) and ((atr / price) > 0.03)

def is_momentum_trade(t):
    # הבוט הקיים - קונה מניות עם גאפ חיובי
    gap = t.get('gap_pct') or 0
    return gap > 0

def main():
    conn = get_conn()
    trades = fetch_data(conn)
    
    print("Fetching SPY data for market context...")
    spy = yf.download("SPY", start="2026-10-01", end="2026-11-01", progress=False)
    if isinstance(spy.columns, pd.MultiIndex):
        spy.columns = spy.columns.get_level_values(0)
    spy['SMA20'] = spy['Close'].rolling(window=20).mean()
    
    spy_ok_dates = {}
    for date, row in spy.iterrows():
        date_str = date.strftime('%Y-%m-%d')
        if pd.notna(row['SMA20']):
            spy_ok_dates[date_str] = row['Close'] > row['SMA20']
        else:
            spy_ok_dates[date_str] = False

    # סינון לתקופות
    bull_trades = [] # SPY > SMA20
    bear_trades = [] # SPY < SMA20
    
    for t in trades:
        date_str = str(t['scan_date'])[:10]
        if spy_ok_dates.get(date_str, False):
            bull_trades.append(t)
        else:
            bear_trades.append(t)

    print("\n" + "=" * 90)
    print("  MARKET REGIME ANALYSIS (Regime Switching Strategy)")
    print("=" * 90)
    
    for label, group in [("BULL Market (SPY > SMA20)", bull_trades), ("BEAR Market (SPY < SMA20)", bear_trades)]:
        print(f"\n--- {label} ---")
        if not group:
            print("  No trades in this regime.")
            continue
            
        # 1. כל העסקאות
        st_all = calc_stats(group)
        print(f"  All Trades:      | N={st_all['n']:>4} | Win%={st_all['win_pct']:>5.1f}% | AvgR={st_all['avg_r']:>+6.3f} | TotalR={st_all['total_r']:>+7.1f}")
        
        # 2. רק מומנטום (הבוט הישן)
        mom = [t for t in group if is_momentum_trade(t)]
        st_mom = calc_stats(mom)
        if st_mom:
            print(f"  Momentum (Gap>0): | N={st_mom['n']:>4} | Win%={st_mom['win_pct']:>5.1f}% | AvgR={st_mom['avg_r']:>+6.3f} | TotalR={st_mom['total_r']:>+7.1f}")
        else:
             print(f"  Momentum (Gap>0): | No trades")

        # 3. רק Dip (הבוט החדש)
        dip = [t for t in group if is_dip_trade(t)]
        st_dip = calc_stats(dip)
        if st_dip:
            print(f"  Dip Filter:       | N={st_dip['n']:>4} | Win%={st_dip['win_pct']:>5.1f}% | AvgR={st_dip['avg_r']:>+6.3f} | TotalR={st_dip['total_r']:>+7.1f}")
        else:
            print(f"  Dip Filter:       | No trades")

    print("\n" + "=" * 90)
    print("  RECOMMENDATION:")
    print("  If Momentum is better in BULL and Dip is better in BEAR -> WE HAVE A WINNER.")
    print("=" * 90)
    conn.close()

if __name__ == "__main__":
    main()