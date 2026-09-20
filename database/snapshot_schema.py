"""
DAYS-BOT V5.0.6 – Snapshot Schema

Purpose
-------
Immutable point-in-time snapshots + trigger results + outcomes.

Tables
------
snapshots
    Immutable T0 record.

trigger_results
    One row per snapshot + trigger method/version.

outcomes
    One row per snapshot + trigger method/version + horizon.

Important
---------
DO NOT UPDATE snapshots after creation.

V5.0.6 corrections
-------------------
- net_r_status added to outcomes.
- Existing DBs are migrated safely.
- NON_EXECUTABLE / INVALID are never represented as Net R = 0.
- Valid 0R remains a real BREAKEVEN.
- pm_bars_json is preserved when available.
"""

import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path


DB_PATH = Path(__file__).resolve().parent.parent / "data" / "alerts.db"


# =====================================================================
# DDL
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
    pm_bars_json          TEXT,

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
    risk_per_share       REAL,
    max_loss              REAL,
    hold_type             TEXT,

    data_status            TEXT,
    trade_type             TEXT,

    strategy_version       TEXT NOT NULL,
    filter_version         TEXT NOT NULL,
    score_version          TEXT NOT NULL,
    plan_version           TEXT NOT NULL,

    created_at             DATETIME DEFAULT CURRENT_TIMESTAMP,

    UNIQUE(scan_id, ticker, snapshot_time_utc)
);
"""


TRIGGER_RESULTS_DDL = """
CREATE TABLE IF NOT EXISTS trigger_results (
    trigger_result_id     INTEGER PRIMARY KEY AUTOINCREMENT,

    snapshot_id           INTEGER NOT NULL,

    trigger_method        TEXT NOT NULL,
    trigger_version       TEXT NOT NULL,

    hit                   INTEGER NOT NULL,

    trigger_time_utc      TEXT,
    trigger_time_et       TEXT,
    trigger_price         REAL,

    elapsed_sec_from_t0   INTEGER,

    window                TEXT,

    metadata_json         TEXT,

    created_at            DATETIME DEFAULT CURRENT_TIMESTAMP,

    FOREIGN KEY (snapshot_id)
        REFERENCES snapshots(snapshot_id),

    UNIQUE(
        snapshot_id,
        trigger_method,
        trigger_version
    )
);
"""


OUTCOMES_DDL = """
CREATE TABLE IF NOT EXISTS outcomes (
    outcome_id
        INTEGER PRIMARY KEY AUTOINCREMENT,

    snapshot_id
        INTEGER NOT NULL,

    trigger_method
        TEXT,

    trigger_version
        TEXT,

    outcome_horizon
        TEXT NOT NULL,

    t0_price
        REAL,

    mfe
        REAL,

    mae
        REAL,

    mfe_pct
        REAL,

    mae_pct
        REAL,

    time_to_mfe_sec
        INTEGER,

    time_to_mae_sec
        INTEGER,

    absolute_move_before_trigger_pct
        REAL,

    relative_move_before_trigger_pct
        REAL,

    entry_slippage_pct
        REAL,

    entry_efficiency
        REAL,

    exit_reason
        TEXT,

    exit_price
        REAL,

    exit_time_utc
        TEXT,

    hold_minutes
        INTEGER,

    gross_r
        REAL,

    gross_pct
        REAL,

    cost_spread
        REAL,

    cost_slippage
        REAL,

    cost_commission
        REAL,

    cost_tax
        REAL,

    cost_total
        REAL,

    net_r
        REAL,

    net_pct
        REAL,

    outcome
        TEXT,

    net_r_status
        TEXT,

    exit_rules_version
        TEXT NOT NULL,

    cost_model_version
        TEXT,

    created_at
        DATETIME DEFAULT CURRENT_TIMESTAMP,

    updated_at
        DATETIME DEFAULT CURRENT_TIMESTAMP,

    FOREIGN KEY (snapshot_id)
        REFERENCES snapshots(snapshot_id),

    UNIQUE(
        snapshot_id,
        trigger_method,
        trigger_version,
        outcome_horizon
    )
);
"""


INDEXES_DDL = [
    """
    CREATE INDEX IF NOT EXISTS idx_snapshots_scan
    ON snapshots(scan_id);
    """,

    """
    CREATE INDEX IF NOT EXISTS idx_snapshots_ticker_date
    ON snapshots(ticker, scan_date);
    """,

    """
    CREATE INDEX IF NOT EXISTS idx_snapshots_time
    ON snapshots(snapshot_time_utc);
    """,

    """
    CREATE INDEX IF NOT EXISTS idx_trigger_snapshot
    ON trigger_results(snapshot_id);
    """,

    """
    CREATE INDEX IF NOT EXISTS idx_trigger_method
    ON trigger_results(trigger_method, hit);
    """,

    """
    CREATE INDEX IF NOT EXISTS idx_outcomes_snapshot
    ON outcomes(snapshot_id);
    """,

    """
    CREATE INDEX IF NOT EXISTS idx_outcomes_trigger
    ON outcomes(trigger_method, outcome_horizon);
    """,

    """
    CREATE INDEX IF NOT EXISTS idx_outcomes_outcome
    ON outcomes(outcome);
    """,

    """
    CREATE INDEX IF NOT EXISTS idx_outcomes_net_status
    ON outcomes(net_r_status);
    """,
]


# =====================================================================
# MIGRATION
# =====================================================================

def _table_columns(cur, table_name):
    rows = cur.execute(
        f"PRAGMA table_info({table_name})"
    ).fetchall()

    return {
        row[1]
        for row in rows
    }


def _ensure_column(
    cur,
    table_name,
    column_name,
    column_type,
):
    columns = _table_columns(
        cur,
        table_name,
    )

    if column_name in columns:
        return False

    cur.execute(
        f"""
        ALTER TABLE {table_name}
        ADD COLUMN {column_name} {column_type}
        """
    )

    print(
        f"[schema] Added "
        f"{table_name}.{column_name} "
        f"{column_type}"
    )

    return True


# =====================================================================
# INITIALIZATION
# =====================================================================

def init_snapshot_schema():
    """
    Create tables and safely migrate existing DB.

    This function is idempotent.
    It does NOT delete historical data.
    """

    DB_PATH.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    conn = sqlite3.connect(
        str(DB_PATH)
    )

    try:
        cur = conn.cursor()

        cur.execute(
            SNAPSHOTS_DDL
        )

        cur.execute(
            TRIGGER_RESULTS_DDL
        )

        cur.execute(
            OUTCOMES_DDL
        )

        # -------------------------------------------------------------
        # Safe migrations
        # -------------------------------------------------------------

        _ensure_column(
            cur,
            "snapshots",
            "pm_bars_json",
            "TEXT",
        )

        _ensure_column(
            cur,
            "outcomes",
            "net_r_status",
            "TEXT",
        )

        # -------------------------------------------------------------
        # Indexes
        # -------------------------------------------------------------

        for index_sql in INDEXES_DDL:
            cur.execute(index_sql)

        conn.commit()

    finally:
        conn.close()


# =====================================================================
# SNAPSHOT WRITE
# =====================================================================

def save_snapshot(
    candidate: dict,
    scan_id: str,
    now_et: datetime,
):
    """
    Save immutable T0 snapshot.

    IMPORTANT:
    snapshots are never updated after insertion.
    """

    if not candidate:
        return None

    ticker = candidate.get(
        "ticker"
    )

    if not ticker:
        return None

    # -------------------------------------------------------------
    # HARD LOCK SCORES
    # -------------------------------------------------------------

    composite_score = candidate.get(
        "composite_score"
    )

    swing_score = candidate.get(
        "swing_score"
    )

    event_score = candidate.get(
        "event_score"
    )

    discovery_score = candidate.get(
        "discovery_score"
    )

    print(
        f"[save_snapshot] {ticker} | "
        f"composite={composite_score} "
        f"(type={type(composite_score).__name__}) | "
        f"swing={swing_score} "
        f"(type={type(swing_score).__name__}) | "
        f"event={event_score} | "
        f"discovery={discovery_score}"
    )

    if (
        composite_score is None
        and event_score is not None
    ):
        print(
            f"[save_snapshot] WARNING {ticker}: "
            f"composite_score=None while "
            f"event_score={event_score}. "
            f"Will NOT substitute."
        )

    snapshot_time_et = (
        now_et.strftime(
            "%Y-%m-%d %H:%M:%S"
        )
    )

    if now_et.tzinfo is not None:
        snapshot_time_utc = (
            now_et.astimezone(
                timezone.utc
            ).strftime(
                "%Y-%m-%d %H:%M:%S"
            )
        )
    else:
        snapshot_time_utc = (
            now_et.strftime(
                "%Y-%m-%d %H:%M:%S"
            )
        )

    scan_date = now_et.strftime(
        "%Y-%m-%d"
    )

    pm_bars = candidate.get(
        "pm_bars"
    )

    pm_bars_json = None

    if isinstance(
        pm_bars,
        (list, dict),
    ):
        try:
            pm_bars_json = json.dumps(
                pm_bars,
                default=str,
            )
        except Exception:
            pm_bars_json = None

    elif isinstance(
        candidate.get("pm_bars_json"),
        str,
    ):
        pm_bars_json = candidate.get(
            "pm_bars_json"
        )

    params = {
        "scan_id": scan_id,
        "ticker": ticker,

        "snapshot_time_utc":
            snapshot_time_utc,

        "snapshot_time_et":
            snapshot_time_et,

        "scan_date":
            scan_date,

        "price":
            candidate.get("price"),

        "prev_close":
            candidate.get("prev_close"),

        "gap_pct":
            candidate.get("gap_pct"),

        "gap_sign":
            candidate.get("gap_sign"),

        "gap_bucket":
            candidate.get("gap_bucket"),

        "is_extreme_gap":
            1
            if candidate.get(
                "is_extreme_gap"
            )
            else 0,

        "pm_high":
            candidate.get("pm_high"),

        "pm_low":
            candidate.get("pm_low"),

        "pm_vwap":
            candidate.get("pm_vwap"),

        "pm_volume":
            candidate.get("pm_volume"),

        "pm_bars":
            (
                len(pm_bars)
                if isinstance(
                    pm_bars,
                    list,
                )
                else candidate.get(
                    "pm_bars"
                )
            ),

        "pm_source":
            candidate.get("pm_source"),

        "pm_data_quality":
            candidate.get(
                "pm_data_quality"
            ),

        "pm_volume_status":
            candidate.get(
                "pm_volume_status"
            ),

        "pm_bars_json":
            pm_bars_json,

        "float":
            candidate.get("float"),

        "float_source":
            candidate.get(
                "float_source"
            ),

        "short_interest":
            candidate.get(
                "short_interest"
            ),

        "short_ratio":
            candidate.get(
                "short_ratio"
            ),

        "spread_pct":
            candidate.get(
                "spread_pct"
            ),

        "atr":
            candidate.get("atr"),

        "rs_score":
            candidate.get("rs"),

        "regime":
            candidate.get("regime"),

        "catalyst_type":
            candidate.get(
                "catalyst_type"
            ),

        "catalyst_score":
            candidate.get(
                "catalyst_score"
            ),

        "catalyst_summary":
            candidate.get(
                "catalyst_summary"
            ),

        # HARD LOCK
        "composite_score":
            composite_score,

        "swing_score":
            swing_score,

        "early_score":
            candidate.get(
                "early_score"
            ),

        "entry":
            candidate.get("entry"),

        "stop":
            candidate.get("stop"),

        "target_1":
            candidate.get("target_1"),

        "target_2":
            candidate.get("target_2"),

        "position_size":
            candidate.get(
                "position_size"
            ),

        "risk_per_share":
            candidate.get(
                "risk_per_share"
            ),

        "max_loss":
            candidate.get("max_loss"),

        "hold_type":
            candidate.get(
                "hold_type"
            ),

        "data_status":
            candidate.get(
                "data_status"
            ),

        "trade_type":
            candidate.get(
                "trade_type"
            ),

        "strategy_version":
            candidate.get(
                "strategy_version",
                "V5.0.6",
            ),

        "filter_version":
            candidate.get(
                "filter_version",
                "F1",
            ),

        "score_version":
            candidate.get(
                "score_version",
                "S1",
            ),

        "plan_version":
            candidate.get(
                "plan_version",
                "P1",
            ),
    }

    conn = sqlite3.connect(
        str(DB_PATH)
    )

    try:
        cur = conn.cursor()

        cur.execute(
            """
            INSERT INTO snapshots (
                scan_id,
                ticker,
                snapshot_time_utc,
                snapshot_time_et,
                scan_date,

                price,
                prev_close,
                gap_pct,
                gap_sign,
                gap_bucket,
                is_extreme_gap,

                pm_high,
                pm_low,
                pm_vwap,
                pm_volume,
                pm_bars,
                pm_source,
                pm_data_quality,
                pm_volume_status,
                pm_bars_json,

                float,
                float_source,
                short_interest,
                short_ratio,

                spread_pct,
                atr,
                rs_score,
                regime,

                catalyst_type,
                catalyst_score,
                catalyst_summary,

                composite_score,
                swing_score,
                early_score,

                entry,
                stop,
                target_1,
                target_2,

                position_size,
                risk_per_share,
                max_loss,
                hold_type,

                data_status,
                trade_type,

                strategy_version,
                filter_version,
                score_version,
                plan_version
            )
            VALUES (
                :scan_id,
                :ticker,
                :snapshot_time_utc,
                :snapshot_time_et,
                :scan_date,

                :price,
                :prev_close,
                :gap_pct,
                :gap_sign,
                :gap_bucket,
                :is_extreme_gap,

                :pm_high,
                :pm_low,
                :pm_vwap,
                :pm_volume,
                :pm_bars,
                :pm_source,
                :pm_data_quality,
                :pm_volume_status,
                :pm_bars_json,

                :float,
                :float_source,
                :short_interest,
                :short_ratio,

                :spread_pct,
                :atr,
                :rs_score,
                :regime,

                :catalyst_type,
                :catalyst_score,
                :catalyst_summary,

                :composite_score,
                :swing_score,
                :early_score,

                :entry,
                :stop,
                :target_1,
                :target_2,

                :position_size,
                :risk_per_share,
                :max_loss,
                :hold_type,

                :data_status,
                :trade_type,

                :strategy_version,
                :filter_version,
                :score_version,
                :plan_version
            )
            """,
            params,
        )

        conn.commit()

        snapshot_id = (
            cur.lastrowid
        )

        # ---------------------------------------------------------
        # POST-WRITE VERIFICATION
        # ---------------------------------------------------------

        row = cur.execute(
            """
            SELECT
                composite_score,
                swing_score
            FROM snapshots
            WHERE snapshot_id = ?
            """,
            (snapshot_id,),
        ).fetchone()

        if row:
            db_composite = row[0]
            db_swing = row[1]

            if (
                db_composite
                != composite_score
                or db_swing
                != swing_score
            ):
                print(
                    f"[save_snapshot] "
                    f"❌ SCORE MISMATCH "
                    f"{ticker} | "
                    f"sent=({composite_score},"
                    f"{swing_score}) | "
                    f"db=({db_composite},"
                    f"{db_swing})"
                )
            else:
                print(
                    f"[save_snapshot] "
                    f"✅ {ticker} | "
                    f"snapshot_id="
                    f"{snapshot_id} | "
                    f"composite="
                    f"{db_composite} | "
                    f"swing="
                    f"{db_swing}"
                )

        return snapshot_id

    except sqlite3.IntegrityError:
        print(
            f"[save_snapshot] "
            f"Skipping duplicate: "
            f"{ticker} @ "
            f"{snapshot_time_et}"
        )

        return None

    except Exception as exc:
        print(
            f"[save_snapshot] "
            f"ERROR {ticker}: "
            f"{type(exc).__name__}: "
            f"{exc}"
        )

        return None

    finally:
        conn.close()


# =====================================================================
# DIAGNOSTIC
# =====================================================================

def verify_snapshot_integrity(
    scan_date: str = None,
):
    """
    Verify snapshot scores against latest alert row.

    Returns mismatch count.
    """

    if scan_date is None:
        scan_date = datetime.now().strftime(
            "%Y-%m-%d"
   