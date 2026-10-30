#!/usr/bin/env python3
"""
analyze_features.py v3 - Feature Attribution & Out-of-Sample Validation
"""
import sqlite3
import os
import sys
import statistics
from collections import defaultdict

DB_PATH = os.environ.get("DB_PATH", "data/alerts.db")
MIN_SAMPLE_SIZE = 20

def get_conn():
    if not os.path.exists(DB_PATH):
        print(f"::error::DB not found at {DB_PATH}")
        sys.exit(1)
    return sqlite3.connect(DB_PATH)

def get_columns(conn, table):
    cur = conn.cursor()
    return [row[1] for row in cur.execute(f"PRAGMA table_info({table})")]

def fetch_data(conn):
    snap_cols = get_columns(conn, "snapshots")
    out_cols = get_columns(conn, "outcomes")
    
    required_snap = ['snapshot_id', 'scan_date', 'entry', 'price', 'atr', 'gap_pct', 'composite_score']
    required_out = ['net_r', 'net_r_status']
    
    sel_snap = [f"s.{c}" for c in required_snap if c in snap_cols]
    sel_out = [f"o.{c}" for c in required_out if c in out_cols]
        
    query = f"""
        SELECT {', '.join(sel_snap)}, {', '.join(sel_out)}
        FROM outcomes o
        JOIN snapshots s ON s.snapshot_id = o.snapshot_id
        WHERE o.net_r_status = 'VALID'
    """
    
    cur = conn.cursor()
    cur.execute(query)
    rows = cur.fetchall()
    keys = [d[0].split('.')[-1] for d in cur.description]
    
    return [dict(zip(keys, row)) for row in rows]

def calc_stats(rows):
    if not rows: return None
    net_rs = [r['net_r'] for r in rows if r.get('net_r') is not None]
    if not net_rs: return None
        
    n = len(net_rs)
    wins = [r for r in net_rs if r > 0]
    losses = [r for r in net_rs if r <= 0]
    
    return {
        'n': n,
        'win_pct': round(100.0 * len(wins) / n, 1),
        'avg_r': round(statistics.mean(net_rs), 3),
        'total_r': round(sum(net_rs), 1)
    }

def is_target_trade(t):
    """הפילטר המנצח שמצאנו"""
    price = t.get('price') or 0
    gap = t.get('gap_pct') or 0
    atr = t.get('atr') or 0
    
    if not (10 <= price <= 50): return False
    if gap >= -2: return False
    if price == 0: return False
    if (atr / price) <= 0.03: return False
    
    return True

def main():
    conn = get_conn()
    trades = fetch_data(conn)
    total_stats = calc_stats(trades)
    
    print("\n" + "=" * 90)
    print("  OUT-OF-SAMPLE & SEGMENT VALIDATION")
    print("=" * 90)
    print(f"  Baseline (All Trades): N={total_stats['n']}, Win%={total_stats['win_pct']}%, AvgR={total_stats['avg_r']:+.3f}, TotalR={total_stats['total_r']:+.1f}\n")

    # 1. חלוקה ל-In-Sample ו-Out-of-Sample
    # נניח שהימים הראשונים היו 18-21.10, והימים הקשים היו 22-25.10
    print("-" * 90)
    print("  TEST 1: Split by Date (In-Sample vs Out-of-Sample)")
    print("-" * 90)
    
    is_trades = [t for t in trades if str(t.get('scan_date', '')) <= '2026-10-21']
    oos_trades = [t for t in trades if str(t.get('scan_date', '')) > '2026-10-21']
    
    for label, group in [("In-Sample (<= 21.10)", is_trades), ("Out-of-Sample (> 21.10)", oos_trades)]:
        st = calc_stats(group)
        if st:
            print(f"  {label:<25} | N={st['n']:>4} | Win%={st['win_pct']:>5.1f}% | AvgR={st['avg_r']:>+6.3f} | TotalR={st['total_r']:>+7.1f}")

    print("\n  >> Applying the WINNING FILTER to these periods:")
    for label, group in [("In-Sample (<= 21.10)", is_trades), ("Out-of-Sample (> 21.10)", oos_trades)]:
        filtered = [t for t in group if is_target_trade(t)]
        st = calc_stats(filtered)
        if st and st['n'] >= 5: # סף מינימום קטן יותר כי אנחנו מפצלים
            print(f"  FILTERED {label:<15} | N={st['n']:>4} | Win%={st['win_pct']:>5.1f}% | AvgR={st['avg_r']:>+6.3f} | TotalR={st['total_r']:>+7.1f}")
        else:
            print(f"  FILTERED {label:<15} | Not enough trades (N<5)")

    # 2. בדיקת מודלי היציאה (האם 5 ימים זה יותר מדי?)
    print("\n" + "-" * 90)
    print("  TEST 2: Time Horizon (Days Held) for the FILTERED trades")
    print("-" * 90)
    
    # ננסה למשוך את מספר הימים מהטבלה outcomes_sim אם קיים
    out_cols = get_columns(conn, "outcomes_sim")
    if 'days_held' in out_cols:
        query = """
            SELECT s.price, s.gap_pct, s.atr, sim.days_held, sim.net_r
            FROM outcomes_sim sim
            JOIN snapshots s ON s.snapshot_id = sim.snapshot_id
            WHERE sim.net_r_status = 'VALID' AND sim.model_name = 'E1_Original'
        """
        cur = conn.cursor()
        cur.execute(query)
        sim_trades = [dict(zip(['price', 'gap_pct', 'atr', 'days_held', 'net_r'], row)) for row in cur.fetchall()]
        
        filtered_sim = [t for t in sim_trades if is_target_trade(t)]
        
        for days_limit in [1, 2, 3, 4, 5]:
            # אנחנו מניחים שאם days_held > limit, אנחנו יוצאים ב-HORIZON_END
            # זה חישוב מקורב כי אין לנו את מחיר היציאה המדויק בכל יום
            group = []
            for t in filtered_sim:
                if t['days_held'] <= days_limit:
                    group.append(t)
            
            st = calc_stats(group)
            if st and st['n'] >= 10:
                print(f"  Exit after {days_limit} days or earlier | N={st['n']:>4} | Win%={st['win_pct']:>5.1f}% | AvgR={st['avg_r']:>+6.3f}")
    else:
        print("  [Skip] outcomes_sim table not found or missing days_held column.")

    print("\n" + "=" * 90)
    conn.close()

if __name__ == "__main__":
    main()