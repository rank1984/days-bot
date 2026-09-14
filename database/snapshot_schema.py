"""
DAYS-BOT V5.0.6-prep.1 – Snapshot Schema

FIXES (prep.1):
- HARD LOCK of composite_score / swing_score at function entry
- Debug print at entry (shows exactly what the candidate contains)
- Post-write DB verification (reads back after INSERT)
- Defense in depth: guarantees we never silently write the wrong field

Three tables:
    snapshots          — T0 immutable record
    trigger_results    — one row per (snapshot, trigger_method)
    outcomes           — one row per (snapshot, trigger_method, horizon)

DO NOT UPDATE snapshots. Ever.
"""
import json
import sqlite3
from datetime import datetime
from pathlib import Path

DB_PATH = Path(__file__).resolve().parent.parent / "data" / "alerts.db"

# =====================================================================
# SCHEMA
# =====================================================================

SNAPSHOTS_DDL = """
CREATE TABLE IF NOT EXISTS snapshots (
    snapshot_id           INTEGER PRIMARY KEY AUTOINCREMENT,
    scan_id               TEXT    NOT NULL,
    ticker                TEXT    NOT NULL,
    snapshot_time_utc     TEXT    NOT NULL,
    snapshot_time_et      TEXT    NOT NULL,
    scan_date             TEXT    NOT NULL,
    price                 REAL,
    prev_close            REAL,
    gap_pct               REAL,
    gap_sign              TEXT,
    gap_bucket            TEXT,
    is_extreme_gap        INTEGER,
    pm_high               REAL,
    pm_low                REAL,
    pm_vwap               REAL,
    pm_volume             INTEGER,
    pm_bars               INTEGER,
    pm_source             TEXT,
    pm_data_quality       TEXT,
    pm_volume_status      TEXT,
    float                 REAL,
    float_source          TEXT,
    short_interest        REAL,
    short_ratio           REAL,
    spread_pct            REAL,
    atr                   REAL,
    rs_score              REAL,
    regime                TEXT,
    catalyst_type         TEXT,
    catalyst_score        REAL,
    catalyst_summary      TEXT,
    composite_score       REAL,
    swing_score           REAL,
    early_score           REAL,
    entry                 REAL,
    stop                  REAL,
    target_1              REAL,
    target_2              REAL,
    position_size         INTEGER,
    risk_per_share        REAL,
    max_loss              REAL,
    hold_type             TEXT,
    data_status           TEXT,
    trade_type            TEXT,
    strategy_version      TEXT    NOT NULL,
    filter_version        TEXT    NOT NULL,
    score_version         TEXT    NOT NULL,
    plan_version          TEXT    NOT NULL,
    created_at            DATETIME DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(scan_id, ticker, snapshot_time_utc)
);
"""

TRIGGER_RESULTS_DDL = """
CREATE TABLE IF NOT EXISTS trigger_results (
    trigger_result_id     INTEGER PRIMARY KEY AUTOINCREMENT,
    snapshot_id           INTEGER NOT NULL,
    trigger_method        TEXT    NOT NULL,
    trigger_version       TEXT    NOT NULL,
    hit                   INTEGER NOT NULL,
    trigger_time_utc      TEXT,
    trigger_time_et       TEXT,
    trigger_price         REAL,
    elapsed_sec_from_t0   INTEGER,
    window                TEXT,
    metadata_json         TEXT,
    created_at            DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (snapshot_id) REFERENCES snapshots(snapshot_id),
    UNIQUE(snapshot_id, trigger_method, trigger_version)
);
"""

OUTCOMES_DDL = """
CREATE TABLE IF NOT EXISTS outcomes (
    outcome_id                INTEGER PRIMARY KEY AUTOINCREMENT,
    snapshot_id               INTEGER NOT NULL,
    trigger_method            TEXT,
    trigger_version           TEXT,
    outcome_horizon           TEXT    NOT NULL,
    t0_price                  REAL,
    mfe                       REAL,
    mae                       REAL,
    mfe_pct                   REAL,
    mae_pct                   REAL,
    time_to_mfe_sec           INTEGER,
    time_to_mae_sec           INTEGER,
    absolute_move_before_trigger_pct  REAL,
    relative_move_before_trigger_pct  REAL,
    entry_slippage_pct                REAL,
    entry_efficiency                  REAL,
    exit_reason               TEXT,
    exit_price                REAL,
    exit_time_utc             TEXT,
    hold_minutes              INTEGER,
    gross_r                   REAL,
    gross_pct                 REAL,
    cost_spread               REAL,
    cost_slippage             REAL,
    cost_commission           REAL,
    cost_tax                  REAL,
    cost_total                REAL,
    net_r                     REAL,
    net_pct                   REAL,
    outcome                   TEXT,
    exit_rules_version        TEXT    NOT NULL,
    cost_model_version        TEXT,
    created_at                DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at                DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (snapshot_id) REFERENCES snapshots(snapshot_id),
    UNIQUE(snapshot_id, trigger_method, trigger_version, outcome_horizon)
);
"""

INDEXES_DDL = [
    "CREATE INDEX IF NOT EXISTS idx_snapshots_scan ON snapshots(scan_id);",
    "CREATE INDEX IF NOT EXISTS idx_snapshots_ticker_date ON snapshots(ticker, scan_date);",
    "CREATE INDEX IF NOT EXISTS idx_snapshots_time ON snapshots(snapshot_time_utc);",
    "CREATE INDEX IF NOT EXISTS idx_trigger_snapshot ON trigger_results(snapshot_id);",
    "CREATE INDEX IF NOT EXISTS idx_trigger_method ON trigger_results(trigger_method, hit);",
    "CREATE INDEX IF NOT EXISTS idx_outcomes_snapshot ON outcomes(snapshot_id);",
    "CREATE INDEX IF NOT EXISTS idx_outcomes_trigger ON outcomes(trigger_method, outcome_horizon);",
    "CREATE INDEX IF NOT EXISTS idx_outcomes_outcome ON outcomes(outcome);",
]


def init_snapshot_schema():
    """Create tables + indexes. Safe to call repeatedly."""
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute(SNAPSHOTS_DDL)
    cur.execute(TRIGGER_RESULTS_DDL)
    cur.execute(OUTCOMES_DDL)
    for idx_sql in INDEXES_DDL:
        cur.execute(idx_sql)
    conn.commit()
    conn.close()


# =====================================================================
# WRITE — Snapshot
# =====================================================================

def save_snapshot(candidate: dict, scan_id: str, now_et: datetime):
    """
    Save an immutable T0 snapshot for one candidate.

    V5.0.6-prep.1:
    - HARD LOCK composite_score / swing_score at entry
    - Debug print so we can verify what was passed
    - Post-write verification (read back from DB and compare)

    Returns snapshot_id (int) on success, None on failure/skip.
    """
    if not candidate:
        return None

    ticker = candidate.get("ticker")
    if not ticker:
        return None

    # ================================================================
    # HARD LOCK (V5.0.6-prep.1)
    # Force explicit read — do NOT rely on candidate.get() inside params.
    # ================================================================
    _composite = candidate.get("composite_score")
    _swing = candidate.get("swing_score")
    _event = candidate.get("event_score")
    _discovery = candidate.get("discovery_score")

    print(f"[save_snapshot] {ticker} | "
          f"composite={_composite} (type={type(_composite).__name__}) | "
          f"swing={_swing} (type={type(_swing).__name__}) | "
          f"event={_event} | discovery={_discovery}")

    if _composite is None and _event is not None:
        print(f"[save_snapshot] ⚠️ {ticker} composite is None but event={_event} — "
              f"NOT substituting. Saving None as-is.")

    snapshot_time_et = now_et.strftime("%Y-%m-%d %H:%M:%S")
    snapshot_time_utc = now_et.astimezone(tz=None).strftime("%Y-%m-%d %H:%M:%S")
    scan_date = now_et.strftime("%Y-%m-%d")

    params = {
        "scan_id": scan_id,
        "ticker": ticker,
        "snapshot_time_utc": snapshot_time_utc,
        "snapshot_time_et": snapshot_time_et,
        "scan_date": scan_date,

        "price": candidate.get("price"),
        "prev_close": candidate.get("prev_close"),
        "gap_pct": candidate.get("gap_pct"),
        "gap_sign": candidate.get("gap_sign"),
        "gap_bucket": candidate.get("gap_bucket"),
        "is_extreme_gap": 1 if candidate.get("is_extreme_gap") else 0,

        "pm_high": candidate.get("pm_high"),
        "pm_low": candidate.get("pm_low"),
        "pm_vwap": candidate.get("pm_vwap"),
        "pm_volume": candidate.get("pm_volume"),
        "pm_bars": candidate.get("pm_bars"),
        "pm_source": candidate.get("pm_source"),
        "pm_data_quality": candidate.get("pm_data_quality"),
        "pm_volume_status": candidate.get("pm_volume_status"),

        "float": candidate.get("float"),
        "float_source": candidate.get("float_source"),
        "short_interest": candidate.get("short_interest"),
        "short_ratio": candidate.get("short_ratio"),

        "spread_pct": candidate.get("spread_pct"),
        "atr": candidate.get("atr"),
        "rs_score": candidate.get("rs"),
        "regime": candidate.get("regime"),

        "catalyst_type": candidate.get("catalyst_type"),
        "catalyst_score": candidate.get("catalyst_score"),
        "catalyst_summary": candidate.get("catalyst_summary"),

        # === HARD-LOCKED VALUES ===
        "composite_score": _composite,
        "swing_score": _swing,
        "early_score": candidate.get("early_score"),

        "entry": candidate.get("entry"),
        "stop": candidate.get("stop"),
        "target_1": candidate.get("target_1"),
        "target_2": candidate.get("target_2"),
        "position_size": candidate.get("position_size"),
        "risk_per_share": candidate.get("risk_per_share"),
        "max_loss": candidate.get("max_loss"),
        "hold_type": candidate.get("hold_type"),

        "data_status": candidate.get("data_status"),
        "trade_type": candidate.get("trade_type"),

        "strategy_version": candidate.get("strategy_version", "V5.0.5.2.6"),
        "filter_version": "F1",
        "score_version": "S1",
        "plan_version": "P1",
    }

    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    try:
        cur.execute("""
            INSERT INTO snapshots (
                scan_id, ticker, snapshot_time_utc, snapshot_time_et, scan_date,
                price, prev_close, gap_pct, gap_sign, gap_bucket, is_extreme_gap,
                pm_high, pm_low, pm_vwap, pm_volume, pm_bars,
                pm_source, pm_data_quality, pm_volume_status,
                float, float_source, short_interest, short_ratio,
                spread_pct, atr, rs_score, regime,
                catalyst_type, catalyst_score, catalyst_summary,
                composite_score, swing_score, early_score,
                entry, stop, target_1, target_2,
                position_size, risk_per_share, max_loss, hold_type,
                data_status, trade_type,
                strategy_version, filter_version, score_version, plan_version
            ) VALUES (
                :scan_id, :ticker, :snapshot_time_utc, :snapshot_time_et, :scan_date,
                :price, :prev_close, :gap_pct, :gap_sign, :gap_bucket, :is_extreme_gap,
                :pm_high, :pm_low, :pm_vwap, :pm_volume, :pm_bars,
                :pm_source, :pm_data_quality, :pm_volume_status,
                :float, :float_source, :short_interest, :short_ratio,
                :spread_pct, :atr, :rs_score, :regime,
                :catalyst_type, :catalyst_score, :catalyst_summary,
                :composite_score, :swing_score, :early_score,
                :entry, :stop, :target_1, :target_2,
                :position_size, :risk_per_share, :max_loss, :hold_type,
                :data_status, :trade_type,
                :strategy_version, :filter_version, :score_version, :plan_version
            )
        """, params)
        conn.commit()
        snap_id = cur.lastrowid

        # ================================================================
        # POST-WRITE VERIFICATION
        # ================================================================
        row = cur.execute(
            "SELECT composite_score, swing_score FROM snapshots WHERE snapshot_id = ?",
            (snap_id,)
        ).fetchone()
        if row:
            db_comp, db_swing = row
            if db_comp != _composite or db_swing != _swing:
                print(f"[save_snapshot] ❌ MISMATCH for {ticker}! "
                      f"sent=({_composite},{_swing}) | got=({db_comp},{db_swing})")
            else:
                print(f"[save_snapshot] ✅ {ticker} | snapshot_id={snap_id} | "
                      f"composite={db_comp} | swing={db_swing}")

        return snap_id

    except sqlite3.IntegrityError:
        print(f"[save_snapshot] Skipping duplicate: {ticker} @ {snapshot_time_et}")
        return None
    except Exception as e:
        print(f"[save_snapshot] ERROR for {ticker}: {type(e).__name__}: {e}")
        return None
    finally:
        conn.close()


# =====================================================================
# DIAGNOSTIC
# =====================================================================

def verify_snapshot_integrity(scan_date: str = None):
    """
    Read back all snapshots and compare against their originating alerts.
    Run after a scan to confirm no event_score leakage.
    """
    if scan_date is None:
        scan_date = datetime.now().strftime("%Y-%m-%d")

    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()

    print()
    print("=" * 74)
    print(f"SNAPSHOT INTEGRITY CHECK — scan_date={scan_date}")
    print("=" * 74)
    print(f"  {'ticker':8s} | {'snap_comp':>10s} | {'alerts_comp':>11s} | "
          f"{'snap_swing':>10s} | {'alerts_swing':>12s} | {'MATCH':>7s}")
    print("  " + "-" * 72)

    mismatches = 0
    for snap_row in cur.execute(
        """SELECT s.snapshot_id, s.ticker, s.composite_score, s.swing_score
           FROM snapshots s
           WHERE s.scan_date = ?
           ORDER BY s.snapshot_id""",
        (scan_date,)
    ):
        ticker = snap_row["ticker"]
        snap_comp = snap_row["composite_score"]
        snap_swing = snap_row["swing_score"]

        alert_row = cur.execute(
            """SELECT composite_score, swing_score, raw_candidate_json
               FROM alerts
               WHERE ticker = ? AND scan_date = ?
               ORDER BY id DESC LIMIT 1""",
            (ticker, scan_date)
        ).fetchone()

        alert_comp = alert_row["composite_score"] if alert_row else None
        alert_swing = alert_row["swing_score"] if alert_row else None

        match = "?"
        if snap_comp is not None and alert_comp is not None:
            match = "OK" if abs(float(snap_comp) - float(alert_comp)) < 0.01 else "MISMATCH"
            if match == "MISMATCH":
                mismatches += 1
        elif snap_comp is None and alert_comp is None:
            match = "both-null"

        print(f"  {ticker:8s} | {str(snap_comp):>10s} | {str(alert_comp):>11s} | "
              f"{str(snap_swing):>10s} | {str(alert_swing):>12s} | {match:>7s}")

    print("  " + "-" * 72)
    print(f"  Total mismatches: {mismatches}")
    print("=" * 74)

    conn.close()
    return mismatches


if __name__ == "__main__":
    init_snapshot_schema()
    print("✅ snapshot_schema initialized")
    conn = sqlite3.connect(DB_PATH)
    for table in ("snapshots", "trigger_results", "outcomes"):
        cur = conn.execute(f"PRAGMA table_info({table})")
        cols = [row[1] for row in cur.fetchall()]
        print(f"\n{table}: {len(cols)} columns")
    conn.close()
    verify_snapshot_integrity()
