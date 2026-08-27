import sqlite3
from pathlib import Path
from datetime import datetime

BASE_DIR = Path(__file__).resolve().parent.parent
DB_PATH = BASE_DIR / "days_bot.db"


def init_db():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS alerts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
            ticker TEXT,
            price REAL,
            gap_pct REAL,
            score INTEGER,
            catalyst TEXT
        )
    """)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS trades (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            ticker TEXT,
            entry_time TEXT,
            exit_time TEXT,
            entry_price REAL,
            exit_price REAL,
            shares INTEGER,
            pnl REAL
        )
    """)
    conn.commit()
    conn.close()


def save_alert(ticker: str, price: float, gap_pct: float, score: int, catalyst: str):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO alerts (ticker, price, gap_pct, score, catalyst)
        VALUES (?, ?, ?, ?, ?)
    """, (ticker, price, gap_pct, score, catalyst))
    conn.commit()
    conn.close()


def get_all_trades():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM trades")
    rows = cursor.fetchall()
    conn.close()
    return [dict(row) for row in rows]


def get_open_trades():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM trades WHERE exit_time IS NULL OR exit_time = ''")
    rows = cursor.fetchall()
    conn.close()
    return [dict(row) for row in rows]


def get_monthly_usage():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    current_month = datetime.now().strftime("%Y-%m")
    cursor.execute("""
        SELECT COUNT(*), COALESCE(SUM(shares), 0)
        FROM trades
        WHERE entry_time LIKE ?
    """, (f"{current_month}%",))
    row = cursor.fetchone()
    conn.close()
    monthly_ops = row[0] if row else 0
    monthly_shares = row[1] if row else 0
    return monthly_ops, monthly_shares
