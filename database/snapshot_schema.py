"""
DAYS-BOT V5.0.6 – Snapshot Schema

V5.0.6 changes:
- snapshots.pm_bars_json         (immutable PM Evidence per S0)
- trigger_results.trigger_data_mode  (PM_AWARE | RTH_ONLY)
- outcomes.trigger_result_id     (explicit FK to trigger_results)
- outcomes.net_r_status          (VALID | NON_EXECUTABLE | INCOMPLETE | INVALID)
- Safe migrations via _ensure_column() for existing DBs
- save_snapshot() hard-locks composite_score / swing_score
- save_snapshot() captures pm_bars_json as-is

Three tables:
    snapshots          — T0 immutable record
    trigger_results    — one row per (snapshot, trigger_method, trigger_version)
    outcomes           — one row per (snapshot, trigger_method, trigger_version, outcome_horizon)

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
    pm_bars_json          TEXT,
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
    hit                   INTEGER,
    trigger_time_utc      TEXT,
    trigger_time_et       TEXT,
    trigger_price         REAL,
    elapsed_sec_from_t0   INTEGER,
    window                TEXT,
    trigger_data_mode     TEXT,
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
    trigger_result_id         INTEGER,
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
    net_r_status              TEXT,
    exit_rules_version        TEXT    NOT NULL,
    cost_model_version        TEXT,
    created_at                DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at                DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (snapshot_id) REFERENCES snapshots(snapshot_id),
    FOREIGN KEY (trigger_result_id) REFERENCES trigger_results(trigger_result_id),
    UNIQUE(snapshot_id, trigger_method, trigger_version, outcome_horizon)
);
"""

INDEXES_DDL = [
    "CREATE INDEX IF NOT EXISTS idx_snapshots_scan ON snapshots(scan_id);",
    "CREATE INDEX IF NOT EXISTS idx_snapshots_ticker_date ON snapshots(ticker, scan_date);",
    "CREATE INDEX IF NOT EXISTS idx_snapshots_time ON snapshots(snapshot_time_utc);",
    "CREATE INDEX IF NOT EXISTS idx_trigger_snapshot ON trigger_results(snapshot_id);",
    "CREATE INDEX IF NOT EXISTS idx_trigger_method ON trigger_results(trigger_method, hit);",
    "CREATE INDEX IF NOT EXISTS idx_trigger_data_mode ON trigger_results(trigger_data_mode);",
    "CREATE INDEX IF NOT EXISTS idx_outcomes_snapshot ON outcomes(snapshot_id);",
    "CREATE INDEX IF NOT EXISTS idx_outcomes_trigger ON outcomes(trigger_method, outcome_horizon);",
    "CREATE INDEX IF NOT EXISTS idx_outcomes_outcome ON outcomes(outcome);",
    "CREATE INDEX IF NOT EXISTS idx_outcomes_trigger_result_id ON outcomes(trigger_result_id);",
    "CREATE INDEX IF NOT EXISTS idx_outcomes_net_status ON outcomes(net_r_status);",
]


# =====================================================================
# SAFE MIGRATIONS (V5.0.6)
# =====================================================================

# For existing DBs created before V5.0.6. CREATE TABLE IF NOT EXISTS
# won't add missing columns to an existing table, so we ALTER TABLE.

MIGRATIONS_V506 = [
    ("snapshots",        "pm_bars_json",      "TEXT"),
    ("trigger_results",  "trigger_data_mode", "TEXT"),
    ("outcomes",         "trigger_result_id", "INTEGER"),
    ("outcomes",         "net_r_status",      "TEXT"),
]


def _ensure_column(cur, table_name, column_name, column_type):
    """Add column if missing. Safe to call repeatedly."""
    cur.execute(f"PRAGMA table_info({table_name})")
    existing = {row[1] for row in cur.fetchall()}
    if column_name not in existing:
        cur.execute(
            f"ALTER TABLE {table_name} ADD COLUMN {column_name} {column_type}"
        )
        print(f"[schema] Added {table_name}.{column_name} ({column_type})")
    else:
        print(f"[schema] {table_name}.{column_name} — already present")


def _relax_hit_nullable():
    """
    trigger_results.hit must be nullable to represent UNKNOWN.
    SQLite can't ALTER COLUMN. Drop+recreate — safe only if table is empty.
    """
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()

    try:
        cur.execute("PRAGMA table_info(trigger_results)")
        cols = cur.fetchall()
    except Exception:
        conn.close()
        return

    hit_col = [c for c in cols if c[1] == "hit"]
    if not hit_col:
        conn.close()
        return

    # col[3] = notnull flag. 0 = nullable.
    if hit_col[0][3] == 0:
        conn.close()
        return  # already nullable

    n = cur.execute("SELECT COUNT(*) FROM trigger_results").fetchone()[0]
    if n > 0:
        print(f"[schema] WARNING: trigger_results has {n} rows — cannot relax safely")
        conn.close()
        return

    cur.execute("DROP TABLE trigger_results")
    cur.execute(TRIGGER_RESULTS_DDL)
    cur.execute("CREATE INDEX IF NOT EXISTS idx_trigger_snapshot ON trigger_results(snapshot_id);")
    cur.execute("CREATE INDEX IF NOT EXISTS idx_trigger_method ON trigger_results(trigger_method, hit);")
    cur.execute("CREATE INDEX IF NOT EXISTS idx_trigger_data_mode ON trigger_results(trigger_data_mode);")
    conn.commit()
    conn.close()
    print("[schema] trigger_results.hit relaxed to nullable (V5.0.6)")


def init_snapshot_schema():
    """Create tables + indexes + apply safe migrations. Idempotent."""
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()

    cur.execute(SNAPSHOTS_DDL)
    cur.execute(TRIGGER_RESULTS_DDL)
    cur.execute(OUTCOMES_DDL)

    # ---- Safe migrations for existing DBs ----
    for table, col, col_type in MIGRATIONS_V506:
        _ensure_column(cur, table, col, col_type)

    # ---- Indexes ----
    for idx_sql in INDEXES_DDL:
        cur.execute(idx_sql)

    conn.commit()
    conn.close()

    # ---- Relax hit nullable (separate conn) ----
    _relax_hit_nullable()


# =====================================================================
# WRITE — Snapshot
# =====================================================================

def save_snapshot(candidate: dict, scan_id: str, now_et: datetime):
    """
    Save an immutable T0 snapshot for one candidate.

    V5.0.6:
    - Captures pm_bars_json directly into snapshots (self-contained Evidence)
    - HARD LOCK composite_score / swing_score
    - Post-write verification

    Returns snapshot_id (int) on success, None on failure/skip.
    """
    if not candidate:
        return None

    ticker = candidate.get("ticker")
    if not ticker:
        return None

    # ---- HARD LOCK ----
    _composite = candidate.get("composite_score")
    _swing = candidate.get("swing_score")
    _event = candidate.get("event_score")
    _discovery = candidate.get("discovery_score")

    print(f"[save_snapshot] {ticker} | "
          f"composite={_composite} (type={type(_composite).__name__}) | "
          f"swing={_swing} (type={type(_swing).__name__}) | "
          f"event={_event} | discovery={_discovery}")

    if _composite is None and _event is not None:
        print(f"[save_snapshot] WARNING: {ticker} composite is None but "
              f"event={_event} — NOT substituting. Saving None as-is.")

    # ---- pm_bars_json normalization ----
    _pm_bars_json = candidate.get("pm_bars_json")
    if _pm_bars_json is not None and not isinstance(_pm_bars_json, str):
        try:
            _pm_bars_json = json.dumps(_pm_bars_json, default=str)
        except Exception:
            _pm_bars_json = None

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
        "pm_bars_json": _pm_bars_json,
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

        "composite_score": _composite,   # HARD LOCKED
        "swing_score": _swing,           # HARD LOCKED
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

        "strategy_version": candidate.get("strategy_version", "V5.0.6"),
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
                pm_high, pm_low, pm_vwap, pm_volume, pm_bars, pm_bars_json,
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
                :pm_high, :pm_low, :pm_vwap, :pm_volume, :pm_bars, :pm_bars_json,
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

        # ---- Post-write verification ----
        row = cur.execute(
            "SELECT composite_score, swing_score, "
            "CASE WHEN pm_bars_json IS NULL THEN 0 ELSE 1 END "
            "FROM snapshots WHERE snapshot_id = ?",
            (snap_id,)
        ).fetchone()

        if row:
            db_comp, db_swing, has_pm_json = row
            if db_comp != _composite or db_swing != _swing:
                print(f"[save_snapshot] MISMATCH for {ticker}! "
                      f"sent=({_composite},{_swing}) | got=({db_comp},{db_swing})")
            else:
                print(f"[save_snapshot] OK {ticker} | snapshot_id={snap_id} | "
                      f"composite={db_comp} | swing={db_swing} | "
                      f"pm_bars_json={'present' if has_pm_json else 'NULL'}")

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
# DIAGNOSTICS
# =====================================================================

def verify_v506_schema():
    """Confirm all V5.0.6 columns exist."""
    print()
    print("=" * 74)
    print("V5.0.6 SCHEMA VERIFICATION")
    print("=" * 74)

    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()

    required = [
        ("snapshots",       "pm_bars_json"),
        ("trigger_results", "trigger_data_mode"),
        ("outcomes",        "trigger_result_id"),
        ("outcomes",        "net_r_status"),
    ]

    all_ok = True
    for table, col in required:
        try:
            cur.execute(f"PRAGMA table_info({table})")
            cols = {row[1] for row in cur.fetchall()}
            present = col in cols
            all_ok = all_ok and present
            print(f"  {table:20s}.{col:25s} : {'present' if present else 'MISSING'}")
        except Exception as e:
            print(f"  {table:20s}.{col:25s} : ERROR ({e})")
            all_ok = False

    print()
    for table in ("snapshots", "trigger_results", "outcomes"):
        try:
            n = cur.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
            print(f"  {table:20s} rows: {n}")
        except Exception as e:
            print(f"  {table:20s} rows: ERROR ({e})")

    print("=" * 74)
    print(f"  Result: {'ALL COLUMNS PRESENT' if all_ok else 'SCHEMA INCOMPLETE'}")
    print("=" * 74)

    conn.close()
    return all_ok


def verify_snapshot_integrity(scan_date: str = None):
    """Read back all snapshots and compare against originating alerts."""
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
          f"{'snap_swing':>10s} | {'alerts_swing':>12s} | {'pm_json':>7s} | {'MATCH':>7s}")
    print("  " + "-" * 84)

    mismatches = 0
    for snap_row in cur.execute(
        """SELECT s.snapshot_id, s.ticker, s.composite_score, s.swing_score,
                  s.pm_bars_json
           FROM snapshots s
           WHERE s.scan_date = ?
           ORDER BY s.snapshot_id""",
        (scan_date,)
    ):
        ticker = snap_row["ticker"]
        snap_comp = snap_row["composite_score"]
        snap_swing = snap_row["swing_score"]
        pm_json = "yes" if snap_row["pm_bars_json"] else "no"

        alert_row = cur.execute(
            """SELECT composite_score, swing_score
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
              f"{