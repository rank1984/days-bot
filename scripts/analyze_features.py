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
    # שאילתה פשוטה שמושכת רק את מה שצריך לפילטר
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

def is_target_trade(t):
    price = t.get('price') or 0
    gap = t.get('gap_pct') or 0
    atr = t.get('atr') or 0
    return (10 <= price <= 50) and (gap < -2) and (price > 0) and ((atr / price) > 0.03)

def main():
    conn = get_conn()
    trades = fetch_data(conn)
    
    # 1. הורדת נתוני SPY כדי לבדוק את מצב השוק
    print("Fetching SPY data for market context...")
    spy = yf.download("SPY", start="2026-10-01", end="2026-11-01", progress=False)
    if isinstance(spy.columns, pd.MultiIndex):
        spy.columns = spy.columns.get_level_values(0)
    
    # חישוב SMA20
    spy['SMA20'] = spy['Close'].rolling(window=20).mean()
    
    # האם SPY היה מעל ה-SMA20 בכל יום?
    spy_ok_dates = {}
    for date, row in spy.iterrows():
        date_str = date.strftime('%Y-%m-%d')
        if pd.notna(row['SMA20']):
            spy_ok_dates[date_str] = row['Close'] > row['SMA20']
        else:
            spy_ok_dates[date_str] = False # אם אין SMA, לא סוחרים

    # 2. סינון העסקאות
    target_trades = [t for t in trades if is_target_trade(t)]
    
    # פילטור לפי SPY
    filtered_by_spy = []
    for t in target_trades:
        date_str = str(t['scan_date'])[:10]
        if spy_ok_dates.get(date_str, False):
            filtered_by_spy.append(t)

    print("\n" + "=" * 90)
    print("  FINAL STRATEGY: DIP + ATR + SPY MARKET FILTER")
    print("=" * 90)
    
    print(f"  All Trades (Baseline):        | N={len(trades):>4} | Win%= {calc_stats(trades)['win_pct']}% | AvgR={calc_stats(trades)['avg_r']:+.3f} | TotalR={calc_stats(trades)['total_r']:+.1f}")
    print(f"  Dip Filter (10-50$, Gap<-2, ATR>3%): | N={len(target_trades):>4} | Win%= {calc_stats(target_trades)['win_pct']}% | AvgR={calc_stats(target_trades)['avg_r']:+.3f} | TotalR={calc_stats(target_trades)['total_r']:+.1f}")
    
    if filtered_by_spy:
        st_spy = calc_stats(filtered_by_spy)
        print(f"  + SPY > SMA20 Filter:         | N={st_spy['n']:>4} | Win%= {st_spy['win_pct']}% | AvgR={st_spy['avg_r']:+.3f} | TotalR={st_spy['total_r']:+.1f}  << THE EDGE")
    else:
        print("  + SPY > SMA20 Filter: No trades passed the market filter.")

    print("=" * 90)
    conn.close()

if __name__ == "__main__":
    main()