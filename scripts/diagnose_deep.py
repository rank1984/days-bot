#!/usr/bin/env python3
"""
diagnose_deep.py - Read-only deep diagnostic for the Outcomes DB.
Prints 7 reports to help identify if the strategy is losing or if the measurement is flawed.
"""
import sqlite3
import os
import sys
from collections import defaultdict

DB_PATH = os.environ.get("DB_PATH", "data/alerts.db")

def get_conn():
    if not os.path.exists(DB_PATH):
        print(f"::error::DB not found at {DB_PATH}")
        sys.exit(1)
    return sqlite3.connect(DB_PATH)

def print_header(title):
    print(f"\n{'='*60}")
    print(f"  {title}")
    print(f"{'='*60}")

def main():
    conn = get_conn()
    cursor = conn.cursor()

    # 1. Profitability
    print_header("1. OVERALL PROFITABILITY (VALID ONLY)")
    cur = cursor.execute("""
        SELECT
            COUNT(*) AS total,
            SUM(CASE WHEN net_r > 0 THEN 1 ELSE 0 END) AS wins,
            SUM(CASE WHEN net_r <= 0 THEN 1 ELSE 0 END) AS losses,
            ROUND(100.0 * SUM(CASE WHEN net_r > 0 THEN 1 ELSE 0 END) / MAX(COUNT(*),1), 2) AS win_rate,
            ROUND(AVG(net_r), 4) AS avg_net_r
        FROM outcomes
        WHERE net_r_status = 'VALID'
    """)
    row = cur.fetchone()
    if row:
        total, wins, losses, win_rate, avg_net_r = row
        print(f"  Total Trades:  {total}")
        print(f"  Wins:          {wins}")
        print(f"  Losses:        {losses}")
        print(f"  Win Rate:      {win_rate}%")
        print(f"  Avg Net R:     {avg_net_r}")

    # 2. Win/Loss Sizes
    print_header("2. WIN / LOSS SIZES")
    cur = cursor.execute("""
        SELECT
            ROUND(AVG(CASE WHEN net_r > 0 THEN net_r END), 4) AS avg_win_r,
            ROUND(MIN(CASE WHEN net_r > 0 THEN net_r END), 4) AS min_win_r,
            ROUND(MAX(CASE WHEN net_r > 0 THEN net_r END), 4) AS max_win_r,
            ROUND(AVG(CASE WHEN net_r <= 0 THEN net_r END), 4) AS avg_loss_r,
            ROUND(MIN(CASE WHEN net_r <= 0 THEN net_r END), 4) AS min_loss_r,
            ROUND(MAX(CASE WHEN net_r <= 0 THEN net_r END), 4) AS max_loss_r
        FROM outcomes
        WHERE net_r_status = 'VALID'
    """)
    row = cur.fetchone()
    if row:
        print(f"  Avg Win R:     {row[0]} (min {row[1]}, max {row[2]})")
        print(f"  Avg Loss R:    {row[3]} (min {row[4]}, max {row[5]})")

    # 3. Exit Reasons
    print_header("3. EXIT REASONS")
    cur = cursor.execute("""
        SELECT exit_reason, COUNT(*) AS count, ROUND(AVG(net_r), 4) AS avg_net_r
        FROM outcomes
        WHERE net_r_status = 'VALID'
        GROUP BY exit_reason
        ORDER BY count DESC
    """)
    for reason, count, avg_r in cur.fetchall():
        print(f"  {reason:<20} | Count: {count:<5} | Avg Net R: {avg_r}")

    # 4. Profitability per Scan Date
    print_header("4. PROFITABILITY PER SCAN DATE")
    cur = cursor.execute("""
        SELECT
            s.scan_date,
            COUNT(o.snapshot_id) AS n,
            ROUND(100.0 * SUM(CASE WHEN o.net_r > 0 THEN 1 ELSE 0 END) / MAX(COUNT(o.snapshot_id),1), 2) AS win_pct,
            ROUND(AVG(o.net_r), 4) AS avg_net_r
        FROM outcomes o
        JOIN snapshots s ON s.snapshot_id = o.snapshot_id
        WHERE o.net_r_status = 'VALID'
        GROUP BY s.scan_date
        ORDER BY s.scan_date DESC
    """)
    for date, n, win_pct, avg_r in cur.fetchall():
        print(f"  {date} | Trades: {n:<4} | Win%: {win_pct:<6} | Avg Net R: {avg_r}")

    # 5. Top 20 Best/Worst Tickers
    print_header("5. TOP 20 BEST / WORST TICKERS (MIN 3 TRADES)")
    print("--- Top 20 Best ---")
    cur = cursor.execute("""
        SELECT s.ticker, COUNT(o.snapshot_id) AS n, ROUND(AVG(o.net_r), 4) AS avg_r
        FROM outcomes o
        JOIN snapshots s ON s.snapshot_id = o.snapshot_id
        WHERE o.net_r_status = 'VALID'
        GROUP BY s.ticker
        HAVING n >= 3
        ORDER BY avg_r DESC
        LIMIT 20
    """)
    for ticker, n, avg_r in cur.fetchall():
        print(f"  {ticker:<10} | Trades: {n:<4} | Avg Net R: {avg_r}")

    print("\n--- Top 20 Worst ---")
    cur = cursor.execute("""
        SELECT s.ticker, COUNT(o.snapshot_id) AS n, ROUND(AVG(o.net_r), 4) AS avg_r
        FROM outcomes o
        JOIN snapshots s ON s.snapshot_id = o.snapshot_id
        WHERE o.net_r_status = 'VALID'
        GROUP BY s.ticker
        HAVING n >= 3
        ORDER BY avg_r ASC
        LIMIT 20
    """)
    for ticker, n, avg_r in cur.fetchall():
        print(f"  {ticker:<10} | Trades: {n:<4} | Avg Net R: {avg_r}")

    # 6. Pending vs Valid
    print_header("6. STATUS DISTRIBUTION")
    cur = cursor.execute("""
        SELECT net_r_status, COUNT(*) AS count
        FROM outcomes
        GROUP BY net_r_status
    """)
    for status, count in cur.fetchall():
        print(f"  {status:<20} | {count}")

    # 7. Data Integrity Checks
    print_header("7. DATA INTEGRITY CHECKS")
    
    # Duplicates
    cur = cursor.execute("""
        SELECT COUNT(*) FROM (
            SELECT snapshot_id, COUNT(*) 
            FROM outcomes 
            GROUP BY snapshot_id 
            HAVING COUNT(*) > 1
        )
    """)
    dupes = cur.fetchone()[0]
    print(f"  Duplicate snapshot_ids in outcomes: {dupes}")

    # Orphaned Outcomes
    cur = cursor.execute("""
        SELECT COUNT(*) 
        FROM outcomes o
        LEFT JOIN snapshots s ON s.snapshot_id = o.snapshot_id
        WHERE s.snapshot_id IS NULL
    """)
    orphans = cur.fetchone()[0]
    print(f"  Orphaned outcomes (no matching snapshot): {orphans}")

    # Missing Net R
    cur = cursor.execute("""
        SELECT COUNT(*) FROM outcomes 
        WHERE net_r_status = 'VALID' AND (net_r IS NULL OR net_r = 0)
    """)
    missing_r = cur.fetchone()[0]
    print(f"  VALID outcomes with missing/zero net_r: {missing_r}")

    conn.close()

if __name__ == "__main__":
    main()