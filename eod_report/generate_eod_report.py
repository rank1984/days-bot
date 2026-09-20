#!/usr/bin/env python3
"""
DAYS-BOT V5.0.6 — Daily EOD Report Generator
Answers: "What did DAYS-BOT say at the morning — and what happened after?"

V5.0.6 changes:
- Respects net_r_status (VALID / NON_EXECUTABLE / INCOMPLETE / INVALID)
- NON_EXECUTABLE ≠ BREAKEVEN (shows N/A + EXCLUDED)
- Summary uses VALID-only statistics (no misleading 0R)
- Distinguishes ACTIONABLE vs RESEARCH vs NO_TRADE
- Distinguishes NO_TRIGGER / NOT_EXECUTABLE / DATA_UNAVAILABLE

Rules:
    NO_TRIGGER       ≠ LOSS
    NOT_EXECUTABLE   ≠ LOSS
    DATA_UNAVAILABLE ≠ LOSS
"""
import sys
import json
import sqlite3
from pathlib import Path
from argparse import ArgumentParser

BASE_DIR = Path(__file__).resolve().parent.parent
DB_PATH = BASE_DIR / "data" / "alerts.db"

sys.path.insert(0, str(BASE_DIR))
from eod_report.format_helpers import (
    fmt_price, fmt_pct, fmt_int, fmt_r, fmt_time,
    recommendation_state, trigger_outcome_label,
)


# ============================================================
# HELPERS
# ============================================================
def _safe_col(row, key, default=None):
    """Safely get a column value from sqlite3.Row (returns None if missing)."""
    try:
        return row[key]
    except (IndexError, KeyError):
        return default


def _net_r_status_of(oc):
    """Extract net_r_status from an outcome row (None if column missing)."""
    if oc is None:
        return None
    return _safe_col(oc, "net_r_status", None)


# ============================================================
# FETCHERS
# ============================================================
def fetch_snapshots(cur, scan_date):
    return cur.execute("""
        SELECT * FROM snapshots WHERE scan_date = ? ORDER BY snapshot_id
    """, (scan_date,)).fetchall()


def fetch_triggers(cur, snapshot_id):
    return cur.execute("""
        SELECT * FROM trigger_results WHERE snapshot_id = ? ORDER BY trigger_method
    """, (snapshot_id,)).fetchall()


def fetch_outcomes(cur, trigger_result_id, horizon):
    return cur.execute("""
        SELECT * FROM outcomes
        WHERE trigger_result_id = ? AND outcome_horizon = ?
        LIMIT 1
    """, (trigger_result_id, horizon)).fetchone()


# ============================================================
# HORIZON RENDERER
# ============================================================
def _render_horizon(hz_name, oc):
    """Render a single horizon line respecting net_r_status."""
    if oc is None:
        return None

    status = _net_r_status_of(oc)
    exit_reason = oc["exit_reason"] or "—"
    mfe_str = fmt_pct(oc["mfe_pct"], sign=True)
    mae_str = fmt_pct(oc["mae_pct"], sign=True)

    # NON_EXECUTABLE — show MFE/MAE (research value) but no Net R
    if status == "NON_EXECUTABLE":
        return (
            f"  - **{hz_name}**: exit=`{exit_reason}` | "
            f"MFE {mfe_str} | MAE {mae_str} | "
            f"Net N/A (NON_EXECUTABLE) | Performance: EXCLUDED"
        )

    # No net_r value — incomplete or invalid
    if oc["net_r"] is None:
        return (
            f"  - **{hz_name}**: exit=`{exit_reason}` | "
            f"MFE {mfe_str} | MAE {mae_str} | "
            f"Net N/A ({status or 'INCOMPLETE'}) | Performance: EXCLUDED"
        )

    # Valid outcome — show full data
    gross_str = fmt_r(oc["gross_r"])
    net_str = fmt_r(oc["net_r"])
    return (
        f"  - **{hz_name}**: exit=`{exit_reason}` | "
        f"MFE {mfe_str} | MAE {mae_str} | "
        f"Gross {gross_str} | Net {net_str} | "
        f"Status: {status or 'VALID'}"
    )


# ============================================================
# SNAPSHOT BLOCK
# ============================================================
def render_snapshot_block(cur, snap):
    lines = []
    ticker = snap["ticker"]
    state = recommendation_state(dict(snap))

    lines.append(f"### {ticker} — {state}")
    lines.append("")

    # ---- S0 (immutable) ----
    lines.append("**S0 (Snapshot, immutable):**")
    lines.append(f"- Snapshot time ET: `{snap['snapshot_time_et']}`")
    lines.append(f"- Price: {fmt_price(snap['price'])} "
                 f"(prev close {fmt_price(snap['prev_close'])})")
    lines.append(f"- Gap: {fmt_pct(snap['gap_pct'], sign=True)}")
    lines.append(f"- PM High/Low: {fmt_price(snap['pm_high'])} / {fmt_price(snap['pm_low'])}")
    lines.append(f"- PM VWAP: {fmt_price(snap['pm_vwap'])}")
    lines.append(f"- PM Volume: {fmt_int(snap['pm_volume'])} "
                 f"({snap['pm_volume_status'] or '—'})")
    lines.append(f"- PM Bars: {fmt_int(snap['pm_bars'])} "
                 f"({snap['pm_source'] or '—'})")
    lines.append(f"- Float: {fmt_int(int(snap['float']) if snap['float'] else None)}")
    lines.append(f"- Spread: {fmt_pct(snap['spread_pct'])}")
    lines.append(f"- Composite: "
                 f"{snap['composite_score'] if snap['composite_score'] is not None else '—'}")
    lines.append(f"- Swing: "
                 f"{snap['swing_score'] if snap['swing_score'] is not None else '—'}")
    lines.append(f"- Trade type: `{snap['trade_type'] or '—'}`")
    lines.append(f"- Data status: `{snap['data_status'] or '—'}`")
    lines.append("")

    # ---- Trade Plan (as captured at S0) ----
    if snap["entry"] is not None:
        lines.append("**Trade Plan (as captured at S0):**")
        lines.append(f"- Entry: {fmt_price(snap['entry'])}")
        lines.append(f"- Stop: {fmt_price(snap['stop'])}")
        lines.append(f"- T1: {fmt_price(snap['target_1'])}")
        lines.append(f"- T2: {fmt_price(snap['target_2'])}")
        lines.append(f"- Position: {fmt_int(snap['position_size'])}")
        lines.append(f"- Risk/share: {fmt_price(snap['risk_per_share'])}")
        lines.append(f"- Max loss: {fmt_price(snap['max_loss'])}")
        lines.append(f"- Hold: {snap['hold_type'] or '—'}")
    else:
        lines.append("**Trade Plan:** N/A (no valid plan at S0)")
    lines.append("")

    # ---- What happened after S0 ----
    lines.append("**What happened after S0:**")
    triggers = fetch_triggers(cur, snap["snapshot_id"])

    if not triggers:
        lines.append("- No trigger results recorded")
    else:
        for trig in triggers:
            method = trig["trigger_method"]
            hit = trig["hit"]
            mode = trig["trigger_data_mode"] or "—"
            window = trig["window"] or "—"
            tt = trig["trigger_time_et"] or "—"
            tp = trig["trigger_price"]
            trig_id = trig["trigger_result_id"]

            intra = fetch_outcomes(cur, trig_id, "INTRADAY_EOD")
            mom = fetch_outcomes(cur, trig_id, "MOMENTUM_90M")
            swing = fetch_outcomes(cur, trig_id, "SWING_3D")

            label = trigger_outcome_label(
                dict(trig),
                dict(intra) if intra else None,
            )
            lines.append(f"- **{method}** [{mode}/{window}]: {label}")

            if hit == 1:
                lines.append(f"  - Trigger time: {tt} | "
                             f"Trigger price: {fmt_price(tp)}")

            for hz_name, oc in (
                ("MOMENTUM_90M", mom),
                ("INTRADAY_EOD", intra),
                ("SWING_3D", swing),
            ):
                rendered = _render_horizon(hz_name, oc)
                if rendered is not None:
                    lines.append(rendered)

    lines.append("")
    return lines


# ============================================================
# SUMMARY
# ============================================================
def render_summary(cur, scan_date):
    lines = []
    lines.append("## Daily Summary")
    lines.append("")

    # ---- Snapshot counts ----
    total_snapshots = cur.execute(
        "SELECT COUNT(*) FROM snapshots WHERE scan_date = ?",
        (scan_date,),
    ).fetchone()[0]

    rows = cur.execute(
        "SELECT * FROM snapshots WHERE scan_date = ?",
        (scan_date,),
    ).fetchall()

    n_actionable = sum(1 for r in rows if recommendation_state(dict(r)) == "ACTIONABLE")
    n_research = sum(1 for r in rows if recommendation_state(dict(r)) == "RESEARCH")
    n_no_trade = sum(1 for r in rows if recommendation_state(dict(r)) == "NO_TRADE")

    # ---- Trigger stats ----
    trig_stats = cur.execute("""
        SELECT
            COUNT(*) AS total,
            SUM(CASE WHEN hit = 1 THEN 1 ELSE 0 END) AS hits,
            SUM(CASE WHEN hit = 0 THEN 1 ELSE 0 END) AS misses,
            SUM(CASE WHEN hit IS NULL THEN 1 ELSE 0 END) AS unknowns
        FROM trigger_results
        WHERE snapshot_id IN (
            SELECT snapshot_id FROM snapshots WHERE scan_date = ?
        )
    """, (scan_date,)).fetchone()

    total_t = trig_stats[0] or 0
    hits = trig_stats[1] or 0
    misses = trig_stats[2] or 0
    unknowns = trig_stats[3] or 0
    trigger_rate = (hits / total_t * 100) if total_t > 0 else 0

    # ---- Outcome stats: VALID-only ----
    # Valid trades only — excludes NON_EXECUTABLE, INCOMPLETE, INVALID
    valid_stats = cur.execute("""
        SELECT
            COUNT(*) AS n,
            SUM(CASE WHEN outcome = 'WIN' THEN 1 ELSE 0 END) AS wins,
            SUM(CASE WHEN outcome = 'LOSS' THEN 1 ELSE 0 END) AS losses,
            SUM(CASE WHEN outcome = 'BREAKEVEN' THEN 1 ELSE 0 END) AS be,
            AVG(gross_r) AS avg_gross_r,
            AVG(net_r) AS avg_net_r,
            AVG(mfe_pct) AS avg_mfe,
            AVG(mae_pct) AS avg_mae
        FROM outcomes
        WHERE outcome_horizon = 'INTRADAY_EOD'
          AND net_r_status = 'VALID'
          AND net_r IS NOT NULL
          AND snapshot_id IN (
              SELECT snapshot_id FROM snapshots WHERE scan_date = ?
          )
    """, (scan_date,)).fetchone()

    n_valid = valid_stats[0] or 0
    n_wins = valid_stats[1] or 0
    n_losses = valid_stats[2] or 0
    n_be = valid_stats[3] or 0
    avg_gross = valid_stats[4]
    avg_net = valid_stats[5]
    avg_mfe = valid_stats[6]
    avg_mae = valid_stats[7]
    win_rate = (n_wins / n_valid * 100) if n_valid > 0 else None

    # ---- Excluded outcomes (all horizons) ----
    excluded_stats = cur.execute("""
        SELECT
            SUM(CASE WHEN net_r_status = 'NON_EXECUTABLE' THEN 1 ELSE 0 END) AS non_exec,
            SUM(CASE WHEN net_r_status = 'INCOMPLETE' THEN 1 ELSE 0 END) AS incomplete,
            SUM(CASE WHEN net_r_status = 'INVALID' THEN 1 ELSE 0 END) AS invalid,
            SUM(CASE WHEN net_r_status IS NULL THEN 1 ELSE 0 END) AS null_status
        FROM outcomes
        WHERE snapshot_id IN (
            SELECT snapshot_id FROM snapshots WHERE scan_date = ?
        )
    """, (scan_date,)).fetchone()

    n_non_exec = excluded_stats[0] or 0
    n_incomplete = excluded_stats[1] or 0
    n_invalid = excluded_stats[2] or 0
    n_null_status = excluded_stats[3] or 0

    # ============================================================
    # Render
    # ============================================================
    lines.append(f"- Snapshots: {total_snapshots}")
    lines.append(f"- Actionable setups: {n_actionable}")
    lines.append(f"- Research candidates: {n_research}")
    lines.append(f"- NO_TRADE: {n_no_trade}")
    lines.append("")

    lines.append(f"- Triggers: {total_t} evaluated "
                 f"({hits} hit, {misses} miss, {unknowns} unknown)")
    lines.append(f"- Trigger rate: {trigger_rate:.1f}%")
    lines.append("")

    lines.append(f"- **Valid outcomes (INTRADAY_EOD)**: {n_valid}")
    lines.append(f"  - Win / Loss / BE: {n_wins} / {n_losses} / {n_be}")

    if win_rate is not None:
        lines.append(f"  - Win rate: {win_rate:.1f}%")
        lines.append(f"  - Avg MFE: {fmt_pct(avg_mfe, sign=True)}")
        lines.append(f"  - Avg MAE: {fmt_pct(avg_mae, sign=True)}")
        lines.append(f"  - Avg Gross R: {fmt_r(avg_gross)}")
        lines.append(f"  - Avg Net R: {fmt_r(avg_net)}")
    else:
        lines.append(f"  - Win rate: N/A (no valid trades)")
        lines.append(f"  - Avg Net R: N/A")

    lines.append("")

    # ---- Excluded section (all horizons, all statuses) ----
    total_excluded = n_non_exec + n_incomplete + n_invalid + n_null_status
    if total_excluded > 0:
        lines.append(f"- **Excluded from performance** (all horizons): {total_excluded}")
        if n_non_exec > 0:
            lines.append(f"  - NON_EXECUTABLE: {n_non_exec}")
        if n_incomplete > 0:
            lines.append(f"  - INCOMPLETE: {n_incomplete}")
        if n_invalid > 0:
            lines.append(f"  - INVALID: {n_invalid}")
        if n_null_status > 0:
            lines.append(f"  - NULL status: {n_null_status}")
        lines.append("")

    return lines


# ============================================================
# MAIN
# ============================================================
def generate_report(scan_date, output_path=None):
    if not DB_PATH.exists():
        print(f"ERROR: DB not found at {DB_PATH}")
        return 1

    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()

    snapshots = fetch_snapshots(cur, scan_date)
    if not snapshots:
        print(f"No snapshots for {scan_date}")
        conn.close()
        return 1

    lines = []
    lines.append("# DAYS-BOT V5.0.6 — Daily EOD Report")
    lines.append("")
    lines.append(f"**Scan date:** {scan_date}")
    lines.append(f"**Snapshots:** {len(snapshots)}")
    lines.append("")
    lines.append("---")
    lines.append("")
    lines.append("## Per-Setup Detail")
    lines.append("")

    for snap in snapshots:
        lines.extend(render_snapshot_block(cur, snap))

    lines.append("---")
    lines.append("")
    lines.extend(render_summary(cur, scan_date))
    lines.append("")
    lines.append("---")
    lines.append("")
    lines.append("**Notes:**")
    lines.append("- `NO_TRIGGER`, `NON_EXECUTABLE`, and `DATA_UNAVAILABLE` are **NOT losses**.")
    lines.append("- Only `net_r_status = 'VALID'` outcomes are included in Win Rate / Avg Net R.")
    lines.append("- MFE/MAE are preserved for all outcomes (research value) even when excluded.")
    lines.append("")

    report = "\n".join(lines)

    if output_path:
        Path(output_path).write_text(report, encoding="utf-8")
        print(f"Report written to {output_path}")
    else:
        print(report)

    conn.close()
    return 0


if __name__ == "__main__":
    parser = ArgumentParser()
    parser.add_argument("--scan-date", required=True)
    parser.add_argument("--output", default=None)
    args = parser.parse_args()
    sys.exit(generate_report(args.scan_date, args.output))
