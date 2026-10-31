#!/usr/bin/env python3
"""
simulate_exits.py - Historical Backtester for Exit Models
Fixed: Filter for SWING_1_3D only.
"""
import sqlite3
import pandas as pd
import yfinance as yf
from datetime import datetime, timedelta
import pytz
import os

ET = pytz.timezone("America/New_York")
DB_PATH = os.environ.get("DB_PATH", "data/alerts.db")
FEE_PCT_TOTAL = 0.01 

def init_sim_table(conn):
    cur = conn.cursor()
    cur.execute("""
        CREATE TABLE IF NOT EXISTS outcomes_sim (
            sim_id INTEGER PRIMARY KEY AUTOINCREMENT,
            snapshot_id INTEGER,
            model TEXT,
            exit_reason TEXT,
            exit_price REAL,
            days_held INTEGER,
            gross_r REAL,
            net_r REAL,
            net_r_status TEXT,
            sim_date_utc TEXT
        )
    """)
    cur.execute("CREATE UNIQUE INDEX IF NOT EXISTS idx_sim_snap_model ON outcomes_sim(snapshot_id, model)")
    conn.commit()

def get_candidates(conn):
    cur = conn.cursor()
    rows = cur.execute("""
        SELECT o.snapshot_id, s.ticker, s.scan_date, s.entry, s.stop, s.target_1, s.target_2
        FROM outcomes o
        JOIN snapshots s ON s.snapshot_id = o.snapshot_id
        WHERE o.net_r_status = 'VALID'
          AND s.trade_type = 'SWING_1_3D'
    """).fetchall()
    return rows

def calc_net_r(entry, exit_price, risk, partial_exit=None):
    fee_dollars = (entry + exit_price) * (FEE_PCT_TOTAL / 2)
    if partial_exit:
        t1 = entry + risk 
        gross_pnl = ((t1 - entry) * 0.5) + ((exit_price - entry) * 0.5)
    else:
        gross_pnl = exit_price - entry
    net_pnl = gross_pnl - fee_dollars
    return net_pnl / risk if risk > 0 else 0.0

def run_sim_for_trade(ticker, scan_date_str, entry, stop, t1, t2):
    results = {}
    start_dt = datetime.strptime(scan_date_str, "%Y-%m-%d") + timedelta(days=1)
    end_dt = start_dt + timedelta(days=10)

    try:
        df = yf.download(ticker, start=start_dt.strftime("%Y-%m-%d"), end=end_dt.strftime("%Y-%m-%d"), 
                         interval="1d", progress=False, auto_adjust=False, threads=False)
        if df is None or df.empty: return None
        if isinstance(df.columns, pd.MultiIndex):
            df.columns = df.columns.get_level_values(0)
        df = df.dropna()
        if df.empty: return None
    except Exception:
        return None

    risk = entry - stop
    if risk <= 0: return None

    states = {
        'E1_Original': {'stop': stop, 't1_hit': False, 'exit': None},
        'E2_TimeStop': {'stop': stop, 't1_hit': False, 'exit': None},
        'E3_Trailing': {'stop': stop, 't1_hit': False, 'exit': None},
        'E4_Partial':  {'stop': stop, 't1_hit': False, 'exit': None},
    }
    max_days_map = {'E1_Original': 5, 'E2_TimeStop': 3, 'E3_Trailing': 5, 'E4_Partial': 5}

    for i, (date, bar) in enumerate(df.iterrows()):
        days_held = i + 1
        high = float(bar['High'])
        low = float(bar['Low'])
        close = float(bar['Close'])

        for model_name, state in states.items():
            if state['exit'] is not None: continue
            if days_held > max_days_map[model_name]:
                state['exit'] = ('HORIZON_END', close)
                continue

            if low <= state['stop']:
                state['exit'] = ('STOP_HIT', state['stop'])
                continue

            if model_name == 'E4_Partial' and state['t1_hit']:
                if high >= t2:
                    state['exit'] = ('T2_HIT', t2)
                    continue
            else:
                if not state['t1_hit'] and high >= t1:
                    state['t1_hit'] = True
                    if model_name == 'E4_Partial':
                        state['stop'] = entry
                    else:
                        state['exit'] = ('T1_HIT', t1)
                        continue

            if model_name == 'E3_Trailing' and not state['t1_hit']:
                if high >= (entry + 1.5 * risk):
                    state['t1_hit'] = True
                    state['stop'] = entry

    for model_name, state in states.items():
        if state['exit'] is None:
            state['exit'] = ('HORIZON_END', float(df.iloc[-1]['Close']))
            days_held = len(df)
        else:
            days_held = min(i+1, max_days_map[model_name])

        reason, exit_price = state['exit']
        if model_name == 'E4_Partial':
            net_r = calc_net_r(entry, exit_price, risk, partial_exit=state['t1_hit'])
        else:
            net_r = calc_net_r(entry, exit_price, risk, partial_exit=False)

        results[model_name] = {'reason': reason, 'net_r': net_r, 'days': days_held}

    return results

def main():
    conn = sqlite3.connect(DB_PATH)
    init_sim_table(conn)
    cur = conn.cursor()
    cur.execute("SELECT snapshot_id FROM outcomes_sim")
    simulated_ids = set(row[0] for row in cur.fetchall())
    candidates = get_candidates(conn)
    to_sim = [c for c in candidates if c[0] not in simulated_ids]

    print(f"[sim] Total VALID trades: {len(candidates)}")
    print(f"[sim] Already simulated: {len(simulated_ids)}")
    print(f"[sim] To simulate now: {len(to_sim)}")

    if not to_sim:
        print("[sim] Nothing to simulate. Exiting.")
        return

    now_utc = datetime.now(pytz.UTC).strftime("%Y-%m-%dT%H:%M:%SZ")
    batch_insert = []

    for i, (snap_id, ticker, scan_date, entry, stop, t1, t2) in enumerate(to_sim):
        if i % 20 == 0:
            print(f"[sim] Progress: {i}/{len(to_sim)}")
        res = run_sim_for_trade(ticker, scan_date, entry, stop, t1, t2)
        if not res: continue
        for model_name, data in res.items():
            batch_insert.append((snap_id, model_name, data['reason'], data['net_r'], data['days'], now_utc))

    cur.executemany("""
        INSERT INTO outcomes_sim (snapshot_id, model, exit_reason, net_r, days_held, sim_date_utc)
        VALUES (?, ?, ?, ?, ?, ?)
    """, batch_insert)
    conn.commit()
    print(f"[sim] Inserted {len(batch_insert)} simulation records.")

    print(f"\n{'='*80}")
    print(f"  EXIT MODEL COMPARISON")
    print(f"{'='*80}")
    print(f"{'Model':<15} | {'N':>4} | {'Win%':>6} | {'Avg R':>7} | {'Avg Days':>8}")
    print("-" * 80)

    for model_name in ['E1_Original', 'E2_TimeStop', 'E3_Trailing', 'E4_Partial']:
        res = cur.execute("""
            SELECT COUNT(*), 
                   SUM(CASE WHEN net_r > 0 THEN 1 ELSE 0 END),
                   AVG(net_r),
                   AVG(days_held)
            FROM outcomes_sim 
            WHERE model = ?
        """, (model_name,)).fetchone()

        n = res[0]
        if n > 0:
            win_pct = 100.0 * res[1] / n
            avg_r = res[2]
            avg_days = res[3]
            print(f"{model_name:<15} | {n:>4} | {win_pct:>5.1f}% | {avg_r:>+7.3f} | {avg_days:>8.1f}")

    print("=" * 80)
    conn.close()

if __name__ == "__main__":
    main()