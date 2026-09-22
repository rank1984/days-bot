"""
DAYS-BOT V5.0.6 — Snapshot Schema
"""
import json
import sqlite3
from datetime import datetime
from pathlib import Path

DB_PATH = Path(__file__).resolve().parent.parent / "data" / "alerts.db"

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

INDEXES = [
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

MIGRATIONS = [
    ("snapshots", "pm_bars_json", "TEXT"),
    ("trigger_results", "trigger_data_mode", "TEXT"),
    ("outcomes", "trigger_result_id", "INTEGER"),
    ("outcomes", "net_r_status", "TEXT"),
]


def _ensure_column(cur, table, col, col_type):
    cur.execute("PRAGMA table_info(" + table + ")")
    existing = {row[1] for row in cur.fetchall()}
    if col not in existing:
        cur.execute("ALTER TABLE " + table + " ADD COLUMN " + col + " " + col_type)
        print("[schema] Added " + table + "." + col + " (" + col_type + ")")
    else:
        print("[schema] " + table + "." + col + " already present")


def init_snapshot_schema():
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute(SNAPSHOTS_DDL)
    cur.execute(TRIGGER_RESULTS_DDL)
    cur.execute(OUTCOMES_DDL)
    for table, col, col_type in MIGRATIONS:
        _ensure_column(cur, table, col, col_type)
    for idx in INDEXES:
        cur.execute(idx)
    conn.commit()
    conn.close()


def save_snapshot(candidate, scan_id, now_et):
    if not candidate or not candidate.get("ticker"):
        return None

    ticker = candidate["ticker"]
    composite = candidate.get("composite_score")
    swing = candidate.get("swing_score")

    print("[save_snapshot] " + ticker + " | composite=" + str(composite) + " | swing=" + str(swing))

    pm_json = candidate.get("pm_bars_json")
    if pm_json is not None and not isinstance(pm_json, str):
        try:
            pm_json = json.dumps(pm_json, default=str)
        except Exception:
            pm_json = None

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
        "pm_bars_json": pm_json,
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
        "composite_score": composite,
        "swing_score": swing,
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
        print("[save_snapshot] OK " + ticker + " | snapshot_id=" + str(snap_id))
        return snap_id
    except sqlite3.IntegrityError:
        print("[save_snapshot] Duplicate: " + ticker)
        return None
    except Exception as e:
        print("[save_snapshot] ERROR " + ticker + ": " + type(e).__name__ + ": " + str(e))
        return None
    finally:
        conn.close()