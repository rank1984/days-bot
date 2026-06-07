"""
database/db.py — שדרוגים #3 + #4
----------------------------------
#3: Performance Tracker — שומר alert_price ובודק לאחר שעה / סגירה
#4: Cooldown — לא לשלוח אותה מניה תוך 4 שעות
"""

import sqlite3
import os
from datetime import datetime, timedelta
from utils.config import COOLDOWN_HOURS

DB_PATH = os.path.join(os.path.dirname(__file__), "database.db")


def get_conn():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    with get_conn() as conn:
        # טבלת התראות
        conn.execute("""
            CREATE TABLE IF NOT EXISTS alerts (
                id              INTEGER PRIMARY KEY AUTOINCREMENT,
                date            TEXT    NOT NULL,
                ticker          TEXT    NOT NULL,
                score           REAL,
                price           REAL,
                gap_pct         REAL,
                vol_ratio       REAL,
                dollar_volume   REAL,
                float_shares    INTEGER,
                news_score      INTEGER,
                catalyst        TEXT,
                industry        TEXT,
                reason          TEXT,
                sent_at         TEXT,
                sent            INTEGER DEFAULT 0
            )
        """)

        # שדרוג #3 — Performance Tracker
        conn.execute("""
            CREATE TABLE IF NOT EXISTS performance (
                id              INTEGER PRIMARY KEY AUTOINCREMENT,
                ticker          TEXT    NOT NULL,
                alert_date      TEXT    NOT NULL,
                alert_price     REAL,
                price_1h        REAL,
                price_4h        REAL,
                price_close     REAL,
                price_next_day  REAL,
                pnl_1h_pct      REAL,
                pnl_4h_pct      REAL,
                pnl_close_pct   REAL,
                pnl_next_pct    REAL,
                updated_at      TEXT
            )
        """)
        conn.commit()


# ── שדרוג #4: Cooldown ───────────────────────────────────

def already_sent_today(date: str, ticker: str) -> bool:
    """בדיקת cooldown — לא לשלוח אותה מניה תוך COOLDOWN_HOURS."""
    cutoff = (datetime.utcnow() - timedelta(hours=COOLDOWN_HOURS)).strftime("%Y-%m-%d %H:%M:%S")
    with get_conn() as conn:
        row = conn.execute(
            "SELECT 1 FROM alerts WHERE ticker=? AND sent_at > ?",
            (ticker, cutoff)
        ).fetchone()
    return row is not None


def save_alert(date: str, row: dict):
    sent_at = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")
    with get_conn() as conn:
        conn.execute("""
            INSERT INTO alerts
                (date, ticker, score, price, gap_pct, vol_ratio,
                 dollar_volume, float_shares, news_score, catalyst,
                 industry, reason, sent_at, sent)
            VALUES
                (:date, :ticker, :score, :price, :gap_pct, :vol_ratio,
                 :dollar_volume, :float_shares, :news_score, :catalyst,
                 :industry, :reason, :sent_at, 1)
        """, {
            "date":          date,
            "ticker":        row.get("ticker"),
            "score":         row.get("score"),
            "price":         row.get("price"),
            "gap_pct":       row.get("gap_pct"),
            "vol_ratio":     row.get("vol_ratio"),
            "dollar_volume": row.get("dollar_volume"),
            "float_shares":  row.get("float"),
            "news_score":    row.get("news_score", 0),
            "catalyst":      row.get("catalyst", ""),
            "industry":      row.get("industry", ""),
            "reason":        row.get("reason", ""),
            "sent_at":       sent_at,
        })
        conn.commit()

        # שדרוג #3 — צור רשומת performance ריקה לעדכון מאוחר
        conn.execute("""
            INSERT INTO performance (ticker, alert_date, alert_price, updated_at)
            VALUES (?, ?, ?, ?)
        """, (row.get("ticker"), date, row.get("price"), sent_at))
        conn.commit()


# ── שדרוג #3: Performance Tracker ───────────────────────

def update_performance(ticker: str, alert_date: str, field: str, price: float):
    """מעדכן מחיר בשלב מסוים (1h, 4h, close, next_day)."""
    allowed = {"price_1h", "price_4h", "price_close", "price_next_day"}
    if field not in allowed:
        return

    with get_conn() as conn:
        row = conn.execute(
            "SELECT alert_price FROM performance WHERE ticker=? AND alert_date=?",
            (ticker, alert_date)
        ).fetchone()

        if not row:
            return

        alert_price = row["alert_price"]
        pnl = ((price - alert_price) / alert_price * 100) if alert_price else 0

        pnl_field = field.replace("price_", "pnl_") + "_pct"
        conn.execute(f"""
            UPDATE performance
            SET {field}=?, {pnl_field}=?, updated_at=?
            WHERE ticker=? AND alert_date=?
        """, (price, round(pnl, 2), datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S"),
              ticker, alert_date))
        conn.commit()


def get_pending_performance() -> list:
    """מחזיר רשומות שחסר להן עדיין מידע."""
    with get_conn() as conn:
        rows = conn.execute("""
            SELECT ticker, alert_date, alert_price
            FROM performance
            WHERE price_close IS NULL
              AND alert_date >= date('now', '-3 days')
        """).fetchall()
    return [dict(r) for r in rows]
