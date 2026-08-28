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
            event_score REAL
        )
    """)

    # Auto-migration safety for existing tables
    columns_to_add = [
        ("pm_dist_signed", "REAL"),
        ("pm_high_dist", "REAL"),
        ("pm_data_quality", "TEXT"),
        ("rvol_status", "TEXT"),
        ("catalyst_status", "TEXT"),
        ("strategy_version", "TEXT"),
        ("data_version", "TEXT"),
        ("mode", "TEXT"),
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
            strategy_version, data_version, mode, event_score
        ) VALUES (
            :ticker, :price, :gap_pct, :spread_pct,
            :pm_volume, :pm_bars, :pm_high, :pm_vwap,
            :pm_dist_signed, :pm_high_dist, :pm_data_quality,
            :rvol, :rvol_status, :catalyst_score, :catalyst_status,
            :strategy_version, :data_version, :mode, :event_score
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
        "strategy_version": kwargs.get("strategy_version", "V2.14"),
        "data_version": kwargs.get("data_version", "ALPACA_IEX_PM"),
        "mode": kwargs.get("mode", "EXPERIMENT_V2.14"),
        "event_score": kwargs.get("event_score", 75),
    })

    conn.commit()
    conn.close()
