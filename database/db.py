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
            run_mode TEXT,
            event_score REAL
        )
    """)

    # Auto-migration safety for existing SQLite tables
    columns_to_add = [
        ("pm_dist_signed", "REAL"),
        ("pm_high_dist", "REAL"),
        ("pm_data_quality", "TEXT"),
        ("rvol_status", "TEXT"),
        ("catalyst_status", "TEXT"),
        ("strategy_version", "TEXT"),
        ("run_mode", "TEXT"),
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
