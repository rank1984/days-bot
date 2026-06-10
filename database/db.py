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
        conn.execute("""
            CREATE TABLE IF NOT EXISTS alerts (
                id            INTEGER PRIMARY KEY AUTOINCREMENT,
                date          TEXT NOT NULL,
                ticker        TEXT NOT NULL,
                alert_price   REAL,
                score         REAL,
                grade         TEXT,
                gap_pct       REAL,
                pm_volume     INTEGER,
                vol_ratio     REAL,
                dollar_volume REAL,
                float_shares  INTEGER,
                news_score    INTEGER,
                catalyst      TEXT,
                sent_at       TEXT
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS performance (
                id            INTEGER PRIMARY KEY AUTOINCREMENT,
                ticker        TEXT NOT NULL,
                alert_date    TEXT NOT NULL,
                alert_price   REAL,
                open_price    REAL,
                hod           REAL,
                close_price   REAL,
                next_day_open REAL,
                pnl_open_pct  REAL,
                pnl_hod_pct   REAL,
                pnl_close_pct REAL,
                updated_at    TEXT,
                UNIQUE(ticker, alert_date)
            )
        """)
        conn.commit()


def already_sent_today(date: str, ticker: str) -> bool:
    cutoff = (
        datetime.utcnow() - timedelta(hours=COOLDOWN_HOURS)
    ).strftime("%Y-%m-%d %H:%M:%S")
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
                (date, ticker, alert_price, score, grade, gap_pct,
                 pm_volume, vol_ratio, dollar_volume, float_shares,
                 news_score, catalyst, sent_at)
            VALUES
                (:date, :ticker, :alert_price, :score, :grade, :gap_pct,
                 :pm_volume, :vol_ratio, :dollar_volume, :float_shares,
                 :news_score, :catalyst, :sent_at)
        """, {
            "date":          date,
            "ticker":        row.get("ticker"),
            "alert_price":   row.get("price"),
            "score":         row.get("score"),
            "grade":         row.get("grade"),
            "gap_pct":       row.get("gap_pct"),
            "pm_volume":     row.get("pm_volume"),
            "vol_ratio":     row.get("vol_ratio", row.get("pm_rvol", 0)),
            "dollar_volume": row.get("dollar_volume"),
            "float_shares":  row.get("float"),
            "news_score":    row.get("news_score", 0),
            "catalyst":      row.get("catalyst", ""),
            "sent_at":       sent_at,
        })
        # פתיחת רשומת performance ריקה
        conn.execute("""
            INSERT OR IGNORE INTO performance
                (ticker, alert_date, alert_price, updated_at)
            VALUES (?, ?, ?, ?)
        """, (row.get("ticker"), date, row.get("price"), sent_at))
        conn.commit()


def update_performance(ticker: str, date: str, field: str, price: float):
    """מעדכן שדה מחיר ברשומת performance."""
    allowed = {"open_price", "hod", "close_price", "next_day_open"}
    if field not in allowed:
        return
    now = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")

    with get_conn() as conn:
        row = conn.execute(
            "SELECT alert_price FROM performance WHERE ticker=? AND alert_date=?",
            (ticker, date)
        ).fetchone()
        if not row:
            return

        alert_price = row["alert_price"] or 0
        pnl = round(((price - alert_price) / alert_price * 100), 2) if alert_price else 0
        pnl_field = field.replace("_price", "_pct").replace("hod", "hod_pct")
        pnl_map = {
            "open_price":    "pnl_open_pct",
            "hod":           "pnl_hod_pct",
            "close_price":   "pnl_close_pct",
            "next_day_open": None,
        }
        pnl_col = pnl_map.get(field)

        if pnl_col:
            conn.execute(f"""
                UPDATE performance
                SET {field}=?, {pnl_col}=?, updated_at=?
                WHERE ticker=? AND alert_date=?
            """, (price, pnl, now, ticker, date))
        else:
            conn.execute(f"""
                UPDATE performance
                SET {field}=?, updated_at=?
                WHERE ticker=? AND alert_date=?
            """, (price, now, ticker, date))
        conn.commit()


def get_week_performance() -> list:
    """מחזיר ביצועים של 7 ימים אחרונים."""
    week_ago = (datetime.utcnow() - timedelta(days=7)).strftime("%Y-%m-%d")
    with get_conn() as conn:
        rows = conn.execute("""
            SELECT p.ticker, p.alert_date, p.alert_price,
                   p.open_price, p.hod, p.close_price,
                   p.pnl_open_pct, p.pnl_hod_pct, p.pnl_close_pct,
                   a.catalyst, a.grade
            FROM performance p
            LEFT JOIN alerts a
                ON p.ticker = a.ticker AND p.alert_date = a.date
            WHERE p.alert_date >= ?
            ORDER BY p.alert_date DESC
        """, (week_ago,)).fetchall()
    return [dict(r) for r in rows]
