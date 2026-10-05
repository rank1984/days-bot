#!/usr/bin/env python3
"""
DAYS-BOT V5.0.6.4 — Research Comparison Report

After 50+ Events, compares two cohorts:
  A) ALL outcomes with net_r_status='VALID'
  B) Only outcomes with net_edge_score >= 80

Prints a side-by-side table.
Read-only. Never writes to the DB.
"""
import os
import sys
import sqlite3

DB_PATH = "data/alerts.db"


def _stats(rows):
    if not rows:
        return {"n": 0, "win_rate": None, "avg_r": None,
                "median_r": None, "pf": None, "avg_net_pct": None,
                "max_dd": None, "avg_spread": None, "avg_slip": None}

    net_rs = [r["net_r"] for r in rows if r["net_r"] is not None]
    if not net_rs:
        return {"n": 0, "win_rate": None, "avg_r": None,
                "median_r": None, "pf": None, "avg_net_pct": None,
                "max_dd": None, "avg_spread": None, "avg_slip": None}

    wins = [r for r in net_rs if r > 0.05]
    losses = [r for r in net_rs if r < -0.05]
    sorted_net_rs = sorted(net_rs)
    median_r = sorted_net_rs[len(sorted_net_rs) // 2]

    gross_win = sum(wins) if wins else 0
    gross_loss = abs(sum(losses)) if losses else 0
    pf = (gross_win / gross_loss) if gross_loss > 0 else None

    # Simple max drawdown on cumulative sum
    cumsum = 0
    peak = 0
    max_dd = 0
    for r in net_rs:
        cumsum += r
        peak = max(peak, cumsum)
        dd = peak - cumsum
        max_dd = max(max_dd, dd)

    net_pcts = [r["net_after_tax_pct"] for r in rows if r["net_after_tax_pct"] is not None]
    spreads = [r["spread_at_trigger_pct"] for r in rows if r["spread_at_trigger_pct"] is not None]
    slips = [r["estimated_slippage_pct"] for r in rows if r["estimated_slippage_pct"] is not None]

    return {
        "n": len(rows),
        "win_rate": len(wins) / len(net_rs) * 100 if net_rs else None,
        "avg_r": sum(net_rs) / len(net_rs),
        "median_r": median_r,
        "pf": pf,
        "avg_net_pct": sum(net_pcts) / len(net_pcts) if net_pcts else None,
        "max_dd": max_dd,
        "avg_spread": sum(spreads) / len(spreads) if spreads else None,
        "avg_slip": sum(slips) / len(slips) if slips else None,
    }


def _fmt(v, pct=False, r=False):
    if v is None:
        return "  n/a "
    if pct:
        return f"{v:>7.2f}%"
    if r:
        return f"{v:>7.3f}R"
    return f"{v:>8}"


def main():
    if not os.path.exists(DB_PATH):
        print("DB not found at " + DB_PATH)
        return 0

    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()

    try:
        all_valid = cur.execute("""
            SELECT net_r, net_after_tax_pct, spread_at_trigger_pct,
                   estimated_slippage_pct
            FROM outcomes
            WHERE net_r_status = 'VALID'
              AND outcome_horizon = 'INTRADAY_EOD'
        """).fetchall()

        net_edge_80 = cur.execute("""
            SELECT net_r, net_after_tax_pct, spread_at_trigger_pct,
                   estimated_slippage_pct
            FROM outcomes
            WHERE net_r_status = 'VALID'
              AND outcome_horizon = 'INTRADAY_EOD'
              AND net_edge_score >= 80
        """).fetchall()
    except sqlite3.OperationalError as e:
        print(f"Query failed: {e}")
        conn.close()
        return 1

    conn.close()

    s_all = _stats(all_valid)
    s_edge = _stats(net_edge_80)

    print()
    print("=" * 74)
    print("RESEARCH COMPARISON — RAW vs NET EDGE >= 80")
    print("=" * 74)
    print(f"  {'Metric':<22} {'ALL 50':>14} {'NET EDGE >= 80':>18}")
    print("  " + "-" * 60)
    print(f"  {'N events':<22} {s_all['n']:>14} {s_edge['n']:>18}")
    print(f"  {'Win Rate':<22} {_fmt(s_all['win_rate'], pct=True):>14} {_fmt(s_edge['win_rate'], pct=True):>18}")
    print(f"  {'Avg Net R':<22} {_fmt(s_all['avg_r'], r=True):>14} {_fmt(s_edge['avg_r'], r=True):>18}")
    print(f"  {'Median Net R':<22} {_fmt(s_all['median_r'], r=True):>14} {_fmt(s_edge['median_r'], r=True):>18}")
    print(f"  {'Profit Factor':<22} {_fmt(s_all['pf']):>14} {_fmt(s_edge['pf']):>18}")
    print(f"  {'Avg Net % (after tax)':<22} {_fmt(s_all['avg_net_pct'], pct=True):>14} {_fmt(s_edge['avg_net_pct'], pct=True):>18}")
    print(f"  {'Max Drawdown (R)':<22} {_fmt(s_all['max_dd'], r=True):>14} {_fmt(s_edge['max_dd'], r=True):>18}")
    print(f"  {'Avg Spread %':<22} {_fmt(s_all['avg_spread'], pct=True):>14} {_fmt(s_edge['avg_spread'], pct=True):>18}")
    print(f"  {'Avg Slippage %':<22} {_fmt(s_all['avg_slip'], pct=True):>14} {_fmt(s_edge['avg_slip'], pct=True):>18}")
    print("=" * 74)

    return 0


if __name__ == "__main__":
    sys.exit(main())