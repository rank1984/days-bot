#!/usr/bin/env python3
"""
analyze_features.py v2 - Feature Attribution Analysis (Read-Only)
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
    
    required_snap = ['snapshot_id', 'ticker', 'scan_date', 'entry', 'stop', 'target_1', 'target_2',
                     'composite_score', 'gap_pct', 'price', 'atr', 'avg_volume', 'sector',
                     'float', 'spread_pct', 'rs_score', 'rvol']
    required_out = ['net_r', 'net_r_status', 'exit_reason']
    
    sel_snap = [f"s.{c}" for c in required_snap if c in snap_cols]
    sel_out = [f"o.{c}" for c in required_out if c in out_cols]
    
    if not sel_snap or not sel_out:
        print("::error::Missing required columns in DB")
        sys.exit(1)
        
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
    if not rows:
        return None
    
    net_rs = [r['net_r'] for r in rows if r.get('net_r') is not None]
    if not net_rs:
        return None
        
    n = len(net_rs)
    wins = [r for r in net_rs if r > 0]
    losses = [r for r in net_rs if r <= 0]
    
    win_pct = 100.0 * len(wins) / n
    avg_r = statistics.mean(net_rs)
    median_r = statistics.median(net_rs)
    
    avg_win_r = statistics.mean(wins) if wins else 0
    avg_loss_r = statistics.mean(losses) if losses else 0
    
    t1_hits = sum(1 for r in rows if r.get('exit_reason') in ('T1_HIT', 'T2_HIT', 'STOP_BE_AFTER_T1'))
    stop_hits = sum(1 for r in rows if r.get('exit_reason') == 'STOP_HIT')
    
    return {
        'n': n,
        'win_pct': round(win_pct, 1),
        'avg_r': round(avg_r, 3),
        'median_r': round(median_r, 3),
        'avg_win_r': round(avg_win_r, 3),
        'avg_loss_r': round(avg_loss_r, 3),
        't1_pct': round(100.0 * t1_hits / n, 1),
        'stop_pct': round(100.0 * stop_hits / n, 1),
        'total_r': round(sum(net_rs), 1),
        'missing': n - len(rows),
        'small_sample': n < MIN_SAMPLE_SIZE
    }

def print_table(title, groups, total_avg_r):
    print(f"\n{'='*110}")
    print(f"  {title}")
    print(f"{'='*110}")
    print(f"{'Group':<25} | {'N':>4} | {'Win%':>5} | {'AvgR':>6} | {'MedR':>6} | {'AvgWin':>6} | {'AvgLoss':>7} | {'T1%':>4} | {'Stop%':>5} | {'Δ vs Avg':>8}")
    print("-" * 110)
    
    for label, rows in sorted(groups.items()):
        stats = calc_stats(rows)
        if not stats: continue
        delta = stats['avg_r'] - total_avg_r
        flag = " ⚠️" if stats['small_sample'] else ""
        print(f"{label:<25} | {stats['n']:>4} | {stats['win_pct']:>4.1f}% | {stats['avg_r']:>+6.3f} | {stats['median_r']:>+6.3f} | {stats['avg_win_r']:>+6.3f} | {stats['avg_loss_r']:>+7.3f} | {stats['t1_pct']:>3.0f}% | {stats['stop_pct']:>4.0f}% | {delta:>+8.3f}{flag}")
    
    print(f"{'='*110}")

def main():
    conn = get_conn()
    trades = fetch_data(conn)
    print(f"[analyze] Loaded {len(trades)} valid trades.")
    
    if not trades:
        print("No valid trades found. Exiting.")
        return
    
    total_stats = calc_stats(trades)
    total_avg_r = total_stats['avg_r']
    print(f"[analyze] Baseline: N={total_stats['n']}, Win%={total_stats['win_pct']}%, AvgR={total_avg_r:+.3f}")

    # ============================================================
    # REPORT C: CANDIDATE FILTERS (המעודכן - השילובים)
    # ============================================================
    print("\n\n" + "#" * 110)
    print("# REPORT C: CANDIDATE FILTERS (What happens if we apply a filter?)")
    print("#" * 110)
    print(f"\n  Baseline: N={total_stats['n']}, Win%={total_stats['win_pct']}%, AvgR={total_avg_r:+.3f}, TotalR={total_stats['total_r']:+.1f}")
    print()

    def test_filter(name, condition):
        filtered = [t for t in trades if condition(t)]
        if len(filtered) < MIN_SAMPLE_SIZE:
            return
        stats = calc_stats(filtered)
        retained = 100.0 * stats['n'] / total_stats['n']
        print(f"  {name:<45} | N={stats['n']:>4} ({retained:>4.1f}%) | Win%={stats['win_pct']:>5.1f}% | AvgR={stats['avg_r']:>+6.3f} | TotalR={stats['total_r']:>+7.1f}")

    # Individual filters
    test_filter("Score >= 99 only", lambda t: (t.get('composite_score') or 0) >= 99)
    test_filter("Price $10-$50 only", lambda t: 10 <= (t.get('price') or 0) <= 50)
    test_filter("Gap < -2% only", lambda t: (t.get('gap_pct') or 0) < -2)
    test_filter("ATR > 3% only", lambda t: t.get('atr') and t.get('price') and (t['atr'] / t['price']) > 0.03)
    
    print("-" * 110)
    
    # The Winners Combos
    test_filter("Price $10-$50 + Gap < -2%", lambda t: 10 <= (t.get('price') or 0) <= 50 and (t.get('gap_pct') or 0) < -2)
    test_filter("Price $10-$50 + ATR > 3%", lambda t: 10 <= (t.get('price') or 0) <= 50 and t.get('atr') and t.get('price') and (t['atr'] / t['price']) > 0.03)
    test_filter("Price $10-$50 + Score >= 95", lambda t: 10 <= (t.get('price') or 0) <= 50 and (t.get('composite_score') or 0) >= 95)
    
    print("-" * 110)
    
    # The Holy Grail Combos
    test_filter("Price $10-$50 + Gap < -2% + ATR>3%", lambda t: 10 <= (t.get('price') or 0) <= 50 and (t.get('gap_pct') or 0) < -2 and t.get('atr') and t.get('price') and (t['atr'] / t['price']) > 0.03)
    test_filter("Price $10-$50 + Gap > 0 + ATR>3%", lambda t: 10 <= (t.get('price') or 0) <= 50 and (t.get('gap_pct') or 0) > 0 and t.get('atr') and t.get('price') and (t['atr'] / t['price']) > 0.03)
    test_filter("Price $10-$50 + Score>=95 + ATR>3%", lambda t: 10 <= (t.get('price') or 0) <= 50 and (t.get('composite_score') or 0) >= 95 and t.get('atr') and t.get('price') and (t['atr'] / t['price']) > 0.03)

    print("\n" + "=" * 110)
    print("  Analysis complete.")
    print("=" * 110)

    conn.close()

if __name__ == "__main__":
    main()