import sqlite3
import os

DB_PATH = os.path.join(os.path.dirname(__file__), "database.db")


def get_conn():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    with get_conn() as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS alerts (
                id        INTEGER PRIMARY KEY AUTOINCREMENT,
                date      TEXT    NOT NULL,
                ticker    TEXT    NOT NULL,
                score     REAL,
                price     REAL,
                gap_pct   REAL,
                vol_ratio REAL,
                industry  TEXT,
                reason    TEXT,
                sent      INTEGER DEFAULT 0
            )
        """)
        conn.commit()


def save_alert(date: str, row: dict):
    with get_conn() as conn:
        conn.execute("""
            INSERT OR IGNORE INTO alerts
                (date, ticker, score, price, gap_pct, vol_ratio, industry, reason, sent)
            VALUES
                (:date, :ticker, :score, :price, :gap_pct, :vol_ratio, :industry, :reason, 1)
        """, {**row, "date": date})
        conn.commit()


def already_sent_today(date: str, ticker: str) -> bool:
    with get_conn() as conn:
        row = conn.execute(
            "SELECT 1 FROM alerts WHERE date=? AND ticker=?", (date, ticker)
        ).fetchone()
    return row is not None
