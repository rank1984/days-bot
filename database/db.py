import os
import sqlite3
from pathlib import Path

DB_PATH = Path(__file__).resolve().parent.parent / "data" / "alerts.db"


def get_connection():
    os.makedirs(DB_PATH.parent, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS alerts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
            ticker TEXT NOT NULL,
            price REAL,
            gap_pct REAL,
            spread_pct REAL,
            pm_volume INTEGER,
            pm_bars INTEGER,
            pm_high REAL,
            pm_vwap REAL,
            pm_dist_signed REAL,
            pm_high_dist REAL,
            pm_data_quality TEXT,
            rvol REAL,
            rvol_status TEXT,
            catalyst_score REAL,
            catalyst_status TEXT,
            strategy_version TEXT,
            data_version TEXT,
            mode TEXT,
            opportunity_score REAL,
            grade TEXT,
            decision TEXT,
            entry REAL,
            stop REAL,
            target_1 REAL,
            target_2 REAL,
            risk_per_share REAL,
            position_size INTEGER,
            hold_type TEXT,
            hold_min INTEGER,
            hold_max INTEGER,
            risk_model TEXT,
            spread_status TEXT
        )
    """)

    # Auto-migration for new columns (safely add if missing)
    columns_to_add = [
        ("grade", "TEXT"),
        ("decision", "TEXT"),
        ("entry", "REAL"),
        ("stop", "REAL"),
        ("target_1", "REAL"),
        ("target_2", "REAL"),
        ("risk_per_share", "REAL"),
        ("position_size", "INTEGER"),
        ("hold_type", "TEXT"),
        ("hold_min", "INTEGER"),
        ("hold_max", "INTEGER"),
        ("risk_model", "TEXT"),
        ("spread_status", "TEXT"),
        ("opportunity_score", "REAL"),   # if not present
    ]

    cursor.execute("PRAGMA table_info(alerts)")
    existing_columns = [row["name"] for row in cursor.fetchall()]

    for col_name, col_type in columns_to_add:
        if col_name not in existing_columns:
            try:
                cursor.execute(f"ALTER TABLE alerts ADD COLUMN {col_name} {col_type}")
            except Exception:
                pass

    conn.commit()
    conn.close()


def save_alert(**kwargs):
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("""
        INSERT INTO alerts (
            ticker, price, gap_pct, spread_pct,
            pm_volume, pm_bars, pm_high, pm_vwap,
            pm_dist_signed, pm_high_dist, pm_data_quality,
            rvol, rvol_status, catalyst_score, catalyst_status,
            strategy_version, data_version, mode,
            opportunity_score, grade,
            decision, entry, stop, target_1, target_2,
            risk_per_share, position_size,
            hold_type, hold_min, hold_max, risk_model,
            spread_status
        ) VALUES (
            :ticker, :price, :gap_pct, :spread_pct,
            :pm_volume, :pm_bars, :pm_high, :pm_vwap,
            :pm_dist_signed, :pm_high_dist, :pm_data_quality,
            :rvol, :rvol_status, :catalyst_score, :catalyst_status,
            :strategy_version, :data_version, :mode,
            :opportunity_score, :grade,
            :decision, :entry, :stop, :target_1, :target_2,
            :risk_per_share, :position_size,
            :hold_type, :hold_min, :hold_max, :risk_model,
            :spread_status
        )
    """, {
        "ticker": kwargs.get("ticker"),
        "price": kwargs.get("price"),
        "gap_pct": kwargs.get("gap_pct"),
        "spread_pct": kwargs.get("spread_pct"),
        "pm_volume": kwargs.get("pm_volume"),
        "pm_bars": kwargs.get("pm_bars"),
        "pm_high": kwargs.get("pm_high"),
        "pm_vwap": kwargs.get("pm_vwap"),
        "pm_dist_signed": kwargs.get("pm_dist_signed"),
        "pm_high_dist": kwargs.get("pm_high_dist"),
        "pm_data_quality": kwargs.get("pm_data_quality"),
        "rvol": kwargs.get("rvol"),
        "rvol_status": kwargs.get("rvol_status", "UNAVAILABLE"),
        "catalyst_score": kwargs.get("catalyst_score"),
        "catalyst_status": kwargs.get("catalyst_status", "UNAVAILABLE"),
        "strategy_version": kwargs.get("strategy_version", "V3.1"),
        "data_version": kwargs.get("data_version", "YFINANCE_KEYLESS"),
        "mode": kwargs.get("mode", "EXPERIMENT_V3.1"),
        "opportunity_score": kwargs.get("opportunity_score"),
        "grade": kwargs.get("grade"),
        "decision": kwargs.get("decision"),
        "entry": kwargs.get("entry"),
        "stop": kwargs.get("stop"),
        "target_1": kwargs.get("target_1"),
        "target_2": kwargs.get("target_2"),
        "risk_per_share": kwargs.get("risk_per_share"),
        "position_size": kwargs.get("position_size"),
        "hold_type": kwargs.get("hold_type"),
        "hold_min": kwargs.get("hold_min"),
        "hold_max": kwargs.get("hold_max"),
        "risk_model": kwargs.get("risk_model"),
        "spread_status": kwargs.get("spread_status", "UNAVAILABLE"),
    })

    conn.commit()
    conn.close()
