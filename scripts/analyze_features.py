#!/usr/bin/env python3
"""
analyze_features.py - Feature Attribution Analysis (Read-Only)
Does NOT modify the DB.
Produces 3 reports: Feature Performance, Best/Worst Groups, Candidate Filters.
"""
import sqlite3
import os
import sys
import statistics
from collections import defaultdict

DB_PATH = os.environ.get("DB_PATH", "data/alerts.db")
MIN_SAMPLE_SIZE = 20  # Below this, we flag the group as "small sample"

def get_conn():
    if not os.path.exists(DB_PATH):
        print(f"::error::DB not found at {DB_PATH}")
        sys.exit(1)
    return sqlite3.connect(DB_PATH)

def get_columns(conn, table):
    cur = conn.cursor()
    return [row[1] for row in cur.execute(f"PRAGMA table_info({table})")]

def fetch_data(conn):
    """Fetches all valid trades with their snapshot features."""
    snap_cols = get_columns(conn, "snapshots")
    out_cols = get_columns(conn, "outcomes")
    
    # Build a dynamic query that only includes columns that exist
    required_snap = ['snapshot_id', 'ticker', 'scan_date', 'entry', 'stop', 'target_1', 'target_2',
                     'composite_score', 'gap_pct', 'price', 'atr', 'avg_volume', 'sector',
                     'float', 'spread_pct', 'rs_score', 'rvol']
    required_out = ['net_r', 'net_r_status', 'exit_reason']
    
    sel_snap = [f"s.{c}" for c in required_snap if c in snap_cols]
    sel_out = [f"o.{c}" for c in required_out if c in out_cols]
    
    if not sel_snap or not sel_out:
        print("::error::Missing required columns in DB")
        print(f"snapshots has: {snap_cols}")
        print(f"outcomes has: {out_cols}")
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
    """Calculates stats for a list of trades."""
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
    data_missing = n - len(rows)  # Trades skipped due to missing net_r
    
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
        'missing': data_missing,
        'small_sample': n < MIN_SAMPLE_SIZE
    }

def print_table(title, groups, total_avg_r):
    """Prints a formatted table of groups with their stats."""
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
    # REPORT A: FEATURE PERFORMANCE
    # ============================================================
    print("\n\n" + "#" * 110)
    print("# REPORT A: FEATURE PERFORMANCE")
    print("#" * 110)

    # 1. Score Bins
    score_groups = defaultdict(list)
    for t in trades:
        score = t.get('composite_score')
        if score is None: continue
        if score >= 99: score_groups['Score 99-100'].append(t)
        elif score >= 97: score_groups['Score 97-98'].append(t)
        elif score >= 95: score_groups['Score 95-96'].append(t)
        elif score >= 85: score_groups['Score 85-94'].append(t)
        else: score_groups['Score < 85'].append(t)
    print_table("BY COMPOSITE SCORE", score_groups, total_avg_r)

    # 2. Gap Bins
    gap_groups = defaultdict(list)
    for t in trades:
        gap = t.get('gap_pct')
        if gap is None: continue
        if gap < -2: gap_groups['Gap < -2%'].append(t)
        elif gap < 0: gap_groups['Gap -2% to 0%'].append(t)
        elif gap < 2: gap_groups['Gap 0% to 2%'].append(t)
        elif gap < 5: gap_groups['Gap 2% to 5%'].append(t)
        else: gap_groups['Gap > 5%'].append(t)
    print_table("BY GAP", gap_groups, total_avg_r)

    # 3. Price Bins
    price_groups = defaultdict(list)
    for t in trades:
        price = t.get('price')
        if price is None: continue
        if price < 10: price_groups['Price < $10'].append(t)
        elif price < 50: price_groups['Price $10-$50'].append(t)
        elif price < 100: price_groups['Price $50-$100'].append(t)
        else: price_groups['Price > $100'].append(t)
    print_table("BY PRICE", price_groups, total_avg_r)

    # 4. ATR Bins
    atr_groups = defaultdict(list)
    for t in trades:
        atr = t.get('atr')
        price = t.get('price')
        if atr is None or price is None or price == 0: continue
        atr_pct = 100.0 * atr / price
        if atr_pct < 2: atr_groups['ATR < 2%'].append(t)
        elif atr_pct < 4: atr_groups['ATR 2%-4%'].append(t)
        elif atr_pct < 6: atr_groups['ATR 4%-6%'].append(t)
        else: atr_groups['ATR > 6%'].append(t)
    print_table("BY ATR (% of price)", atr_groups, total_avg_r)

    # 5. Volume Bins
    vol_groups = defaultdict(list)
    for t in trades:
        vol = t.get('avg_volume')
        if vol is None: continue
        if vol < 1_000_000: vol_groups['Vol < 1M'].append(t)
        elif vol < 5_000_000: vol_groups['Vol 1M-5M'].append(t)
        elif vol < 20_000_000: vol_groups['Vol 5M-20M'].append(t)
        else: vol_groups['Vol > 20M'].append(t)
    print_table("BY AVG VOLUME", vol_groups, total_avg_r)

    # 6. RS vs SPY
    rs_groups = defaultdict(list)
    for t in trades:
        rs = t.get('rs_score')
        if rs is None: continue
        if rs < 0: rs_groups['RS < 0'].append(t)
        elif rs < 10: rs_groups['RS 0-10'].append(t)
        elif rs < 25: rs_groups['RS 10-25'].append(t)
        else: rs_groups['RS > 25'].append(t)
    print_table("BY RELATIVE STRENGTH", rs_groups, total_avg_r)

    # 7. Sector
    sector_groups = defaultdict(list)
    for t in trades:
        sec = t.get('sector') or 'Unknown'
        sector_groups[sec].append(t)
    print_table("BY SECTOR", sector_groups, total_avg_r)

    # ============================================================
    # REPORT B: BEST AND WORST GROUPS
    # ============================================================
    print("\n\n" + "#" * 110)
    print("# REPORT B: BEST AND WORST GROUPS")
    print("#" * 110)

    all_groups = []
    for name, group_dict in [('Score', score_groups), ('Gap', gap_groups), ('Price', price_groups),
                              ('ATR', atr_groups), ('Volume', vol_groups), ('RS', rs_groups),
                              ('Sector', sector_groups)]:
        for label, rows in group_dict.items():
            stats = calc_stats(rows)
            if stats and not stats['small_sample']:
                all_groups.append((f"{name}: {label}", stats))

    all_groups.sort(key=lambda x: x[1]['avg_r'], reverse=True)

    print(f"\n{'='*110}")
    print("  TOP 10 BEST GROUPS (avg_r > 0, min 20 trades)")
    print(f"{'='*110}")
    for name, stats in all_groups[:10]:
        if stats['avg_r'] > 0:
            print(f"  {name:<40} | N={stats['n']:>4} | Win%={stats['win_pct']:>5.1f}% | AvgR={stats['avg_r']:>+6.3f} | TotalR={stats['total_r']:>+7.1f}")

    print(f"\n{'='*110}")
    print("  BOTTOM 10 WORST GROUPS")
    print(f"{'='*110}")
    for name, stats in all_groups[-10:]:
        print(f"  {name:<40} | N={stats['n']:>4} | Win%={stats['win_pct']:>5.1f}% | AvgR={stats['avg_r']:>+6.3f} | TotalR={stats['total_r']:>+7.1f}")

    # ============================================================
    # REPORT C: CANDIDATE FILTERS
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

    test_filter("Score >= 99 only", lambda t: (t.get('composite_score') or 0) >= 99)
    test_filter("Score >= 97 only", lambda t: (t.get('composite_score') or 0) >= 97)
    test_filter("Gap > 0 only", lambda t: (t.get('gap_pct') or 0) > 0)
    test_filter("Gap between 0 and 5%", lambda t: 0 < (t.get('gap_pct') or 0) < 5)
    test_filter("Price > $10", lambda t: (t.get('price') or 0) > 10)
    test_filter("Price between $10-$100", lambda t: 10 <= (t.get('price') or 0) <= 100)
    test_filter("ATR > 3%", lambda t: t.get('atr') and t.get('price') and (t['atr'] / t['price']) > 0.03)
    test_filter("ATR > 4%", lambda t: t.get('atr') and t.get('price') and (t['atr'] / t['price']) > 0.04)
    test_filter("Volume > 1M", lambda t: (t.get('avg_volume') or 0) > 1_000_000)
    test_filter("Volume > 2M", lambda t: (t.get('avg_volume') or 0) > 2_000_000)
    test_filter("RS > 0", lambda t: (t.get('rs_score') or 0) > 0)
    test_filter("RS > 10", lambda t: (t.get('rs_score') or 0) > 10)
    test_filter("Score >= 97 + Gap > 0", lambda t: (t.get('composite_score') or 0) >= 97 and (t.get('gap_pct') or 0) > 0)
    test_filter("Score >= 95 + ATR > 3%", lambda t: (t.get('composite_score') or 0) >= 95 and t.get('atr') and t.get('price') and (t['atr'] / t['price']) > 0.03)
    test_filter("Score >= 95 + Volume > 2M", lambda t: (t.get('composite_score') or 0) >= 95 and (t.get('avg_volume') or 0) > 2_000_000)
    test_filter("Score >= 95 + Gap>0 + ATR>3%", lambda t: (t.get('composite_score') or 0) >= 95 and (t.get('gap_pct') or 0) > 0 and t.get('atr') and t.get('price') and (t['atr'] / t['price']) > 0.03)
    test_filter("Score>=97 + Price>$10 + Vol>2M", lambda t: (t.get('composite_score') or 0) >= 97 and (t.get('price') or 0) > 10 and (t.get('avg_volume') or 0) > 2_000_000)
    test_filter("Score>=97 + RS>10 + Gap>0", lambda t: (t.get('composite_score') or 0) >= 97 and (t.get('rs_score') or 0) > 10 and (t.get('gap_pct') or 0) > 0)

    print("\n" + "=" * 110)
    print("  Analysis complete.")
    print("=" * 110)

    conn.close()

if __name__ == "__main__":
    main()