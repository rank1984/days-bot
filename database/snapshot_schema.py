"""
DAYS-BOT V5.0.6 – Snapshot Schema
Three-table design for V5.0.6 Measurement Engine:

    snapshots          — T0 immutable record (per Strict Candidate per Scan)
    trigger_results    — one row per (snapshot, trigger_method)
    outcomes           — one row per (snapshot, trigger_method, horizon)

Design principles:
- snapshots: immutable, never updated
- trigger_results: filled by entry_trigger.py after scan (T+0 to T+1)
- outcomes: filled by execution_engine.py at EOD / T+1 / T+3
- No UPDATE on snapshots. Ever.
- Versioning at every level (strategy / filter / score / plan / trigger / exit / cost)

DO NOT write to these tables during the scan.
Only save_snapshot() is called during scan.
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

    -- === T0 MARKET DATA ===
    price                 REAL,
    prev_close            REAL,
    gap_pct               REAL,
    gap_sign              TEXT,
    gap_bucket            TEXT,
    is_extreme_gap        INTEGER,

    -- === PRE-MARKET ===
    pm_high               REAL,
    pm_low                REAL,
    pm_vwap               REAL,
    pm_volume             INTEGER,
    pm_bars               INTEGER,
    pm_source             TEXT,
    pm_data_quality       TEXT,
    pm_volume_status      TEXT,

    -- === FUNDAMENTALS ===
    float                 REAL,
    float_source          TEXT,
    short_interest        REAL,
    short_ratio           REAL,

    -- === MARKET CONTEXT ===
    spread_pct            REAL,
    atr                   REAL,
    rs_score              REAL,
    regime                TEXT,

    -- === CATALYST ===
    catalyst_type         TEXT,
    catalyst_score        REAL,
    catalyst_summary      TEXT,

    -- === SCORING ===
    composite_score       REAL,
    swing_score           REAL,
    early_score           REAL,

    -- === TRADE PLAN AT T0 ===
    entry                 REAL,
    stop                  REAL,
    target_1              REAL,
    target_2              REAL,
    position_size         INTEGER,
    risk_per_share        REAL,
    max_loss              REAL,
    hold_type             TEXT,

    -- === DECISION ===
    data_status           TEXT,
    trade_type            TEXT,

    -- === VERSIONING ===
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
    trigger_method        TEXT    NOT NULL,   -- 'A_PMH','B_VOLUME','C_VWAP','D_RETEST'
    trigger_version       TEXT    NOT NULL,   -- 'T1' — bump when trigger logic changes
    hit                   INTEGER NOT NULL,   -- 0/1
    trigger_time_utc      TEXT,
    trigger_time_et       TEXT,
    trigger_price         REAL,
    elapsed_sec_from_t0   INTEGER,            -- seconds from snapshot_time
    window                TEXT,               -- 'PM' / 'RTH'
    metadata_json         TEXT,               -- trigger-specific details
    created_at            DATETIME DEFAULT CURRENT_TIMESTAMP,

    FOREIGN KEY (snapshot_id) REFERENCES snapshots(snapshot_id),
    UNIQUE(snapshot_id, trigger_method, trigger_version)
);
"""

OUTCOMES_DDL = """
CREATE TABLE IF NOT EXISTS outcomes (
    outcome_id                INTEGER PRIMARY KEY AUTOINCREMENT,
    snapshot_id               INTEGER NOT NULL,
    trigger_method            TEXT,           -- NULL = market-only (no specific trigger)
    trigger_version           TEXT,
    outcome_horizon           TEXT    NOT NULL,  -- 'MOMENTUM_90M','INTRADAY_EOD','SWING_3D'

    -- === MARKET BEHAVIOR (independent of trigger) ===
    t0_price                  REAL,
    mfe                       REAL,
    mae                       REAL,
    mfe_pct                   REAL,
    mae_pct                   REAL,
    time_to_mfe_sec           INTEGER,
    time_to_mae_sec           INTEGER,

    -- === CHASE METRICS (depend on trigger) ===
    absolute_move_before_trigger_pct  REAL,
    relative_move_before_trigger_pct  REAL,
    entry_slippage_pct                REAL,
    entry_efficiency                  REAL,

    -- === EXIT ===
    exit_reason               TEXT,           -- 'STOP','T1','T2','EOD','NO_TRIGGER'
    exit_price                REAL,
    exit_time_utc             TEXT,
    hold_minutes              INTEGER,

    -- === GROSS P&L ===
    gross_r                   REAL,
    gross_pct                 REAL,

    -- === COSTS (filled by cost_model.py) ===
    cost_spread               REAL,
    cost_slippage             REAL,
    cost_commission           REAL,
    cost_tax                  REAL,
    cost_total                REAL,

    -- === NET P&L ===
    net_r                     REAL,
    net_pct                   REAL,

    -- === OUTCOME CLASSIFICATION ===
    outcome                   TEXT,           -- 'WIN','LOSS','BREAKEVEN','NO_TRIGGER'

    -- === VERSIONING ===
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


# =====================================================================
# INIT
# =====================================================================

def init_snapshot_schema():
    """Create the three tables + indexes if they don't exist. Safe to call repeatedly."""
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
# WRITE — Snapshot (called during scan)
# =====================================================================

def save_snapshot(candidate: dict, scan_id: str, now_et: datetime) -> int | None:
    """
    Save an immutable T0 snapshot for one candidate.

    Called from main.py for EVERY Strict Candidate in EVERY scan.

    Returns snapshot_id (int) on success, None on failure.
    """
    if not candidate:
        return None

    ticker = candidate.get("ticker")
    if not ticker:
        return None

    snapshot_time_et = now_et.strftime("%Y-%m-%d %H:%M:%S")
    snapshot_time_utc = now_et.astimezone(tz=None).strftime("%Y-%m-%d %H:%M:%S")
    scan_date = now_et.strftime("%Y-%m-%d")

    params = {
        "scan_id": scan_id,
        "ticker": ticker,
        "snapshot_time_utc": snapshot_time_utc,
        "snapshot_time_et": snapshot_time_et,
        "scan_date": scan_date,

        # Market
        "price": candidate.get("price"),
        "prev_close": candidate.get("prev_close"),
        "gap_pct": candidate.get("gap_pct"),
        "gap_sign": candidate.get("gap_sign"),
        "gap_bucket": candidate.get("gap_bucket"),
        "is_extreme_gap": 1 if candidate.get("is_extreme_gap") else 0,

        # PM
        "pm_high": candidate.get("pm_high"),
        "pm_low": candidate.get("pm_low"),
        "pm_vwap": candidate.get("pm_vwap"),
        "pm_volume": candidate.get("pm_volume"),
        "pm_bars": candidate.get("pm_bars"),
        "pm_source": candidate.get("pm_source"),
        "pm_data_quality": candidate.get("pm_data_quality"),
        "pm_volume_status": candidate.get("pm_volume_status"),

        # Fundamentals
        "float": candidate.get("float"),
        "float_source": candidate.get("float_source"),
        "short_interest": candidate.get("short_interest"),
        "short_ratio": candidate.get("short_ratio"),

        # Context
        "spread_pct": candidate.get("spread_pct"),
        "atr": candidate.get("atr"),
        "rs_score": candidate.get("rs"),
        "regime": candidate.get("regime"),

        # Catalyst
        "catalyst_type": candidate.get("catalyst_type"),
        "catalyst_score": candidate.get("catalyst_score"),
        "catalyst_summary": candidate.get("catalyst_summary"),

        # Scores
        "composite_score": candidate.get("composite_score"),
        "swing_score": candidate.get("swing_score"),
        "early_score": candidate.get("early_score"),

        # Plan
        "entry": candidate.get("entry"),
        "stop": candidate.get("stop"),
        "target_1": candidate.get("target_1"),
        "target_2": candidate.get("target_2"),
        "position_size": candidate.get("position_size"),
        "risk_per_share": candidate.get("risk_per_share"),
        "max_loss": candidate.get("max_loss"),
        "hold_type": candidate.get("hold_type"),

        # Decision
        "data_status": candidate.get("data_status"),
        "trade_type": candidate.get("trade_type"),

        # Versioning
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
        return snap_id
    except sqlite3.IntegrityError as e:
        # UNIQUE constraint — snapshot already saved for this (scan_id, ticker, time)
        # This is expected if the same candidate is saved twice in one scan
        print(f"[Snapshot] Skipping duplicate: {ticker} @ {snapshot_time_et}")
        return None
    except Exception as e:
        print(f"[Snapshot] ERROR for {ticker}: {type(e).__name__}: {e}")
        return None
    finally:
        conn.close()


# =====================================================================
# INIT ON IMPORT
# =====================================================================

if __name__ == "__main__":
    init_snapshot_schema()
    print("✅ snapshot_schema initialized")
    # Print table info for verification
    conn = sqlite3.connect(DB_PATH)
    for table in ("snapshots", "trigger_results", "outcomes"):
        cur = conn.execute(f"PRAGMA table_info({table})")
        cols = [row[1] for row in cur.fetchall()]
        print(f"\n{table}: {len(cols)} columns")
        for c in cols:
            print(f"  - {c}")
    conn.close()
