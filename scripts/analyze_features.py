#!/usr/bin/env python3
import sqlite3
import os
import sys
import statistics
from collections import defaultdict

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
    gap = t.get('gap_pct') or 0
    return gap > 0

def main():
    conn = get_conn()
    trades = fetch_data(conn)
    
    # 1. קביעת מצב השוק לכל יום (לפי אחוז המניות עם גאפ שלילי באותו יום)
    date_gaps = defaultdict(list)
    for t in trades:
        date_str = str(t['scan_date'])[:10]
        date_gaps[date_str].append(t.get('gap_pct') or 0)
        
    bear_dates = set()
    for date, gaps in date_gaps.items():
        if not gaps: continue
        neg_gaps = sum(1 for g in gaps if g < 0)
        pct_neg = neg_gaps / len(gaps)
        # אם יותר מ-60% מהמניות ירדו - זה יום BEAR
        if pct_neg > 0.6:
            bear_dates.add(date)

    print("\n" + "=" * 90)
    print("  MARKET REGIME ANALYSIS (Based on % of Negative Gaps)")
    print("=" * 90)
    print(f"  Total Trading Days: {len(date_gaps)} | Bear Days (>60% neg gaps): {len(bear_dates)}")

    # 2. חלוקה לתקופות
    bull_trades = []
    bear_trades = []
    
    for t in trades:
        date_str = str(t['scan_date'])[:10]
        if date_str in bear_dates:
            bear_trades.append(t)
        else:
            bull_trades.append(t)

    for label, group in [("BULL Market (Normal Days)", bull_trades), ("BEAR Market (Broad Selloff Days)", bear_trades)]:
        print(f"\n--- {label} ---")
        if not group:
            print("  No trades in this regime.")
            continue
            
        st_all = calc_stats(group)
        print(f"  All Trades:       | N={st_all['n']:>4} | Win%={st_all['win_pct']:>5.1f}% | AvgR={st_all['avg_r']:>+6.3f} | TotalR={st_all['total_r']:>+7.1f}")
        
        mom = [t for t in group if is_momentum_trade(t)]
        st_mom = calc_stats(mom)
        if st_mom:
            print(f"  Momentum (Gap>0): | N={st_mom['n']:>4} | Win%={st_mom['win_pct']:>5.1f}% | AvgR={st_mom['avg_r']:>+6.3f} | TotalR={st_mom['total_r']:>+7.1f}")
        else:
             print(f"  Momentum (Gap>0): | No trades")

        dip = [t for t in group if is_dip_trade(t)]
        st_dip = calc_stats(dip)
        if st_dip:
            print(f"  Dip Filter:       | N={st_dip['n']:>4} | Win%={st_dip['win_pct']:>5.1f}% | AvgR={st_dip['avg_r']:>+6.3f} | TotalR={st_dip['total_r']:>+7.1f}")
        else:
            print(f"  Dip Filter:       | No trades")

    print("\n" + "=" * 90)
    print("  FINAL DECISION:")
    print("  1. If Dip has positive AvgR in BOTH regimes -> Use Dip everywhere.")
    print("  2. If Momentum works in BULL and Dip works in BEAR -> Regime Switch.")
    print("=" * 90)
    conn.close()

if __name__ == "__main__":
    main()