import sqlite3
from pathlib import Path
from datetime import datetime
from typing import List, Dict, Any, Tuple

DB_PATH = Path(__file__).resolve().parent.parent / "days_bot.db"


def get_connection():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    """Initializes schema including alerts and executed trade logs."""
    with get_connection() as conn:
        cursor = conn.cursor()
        
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS alerts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                ticker TEXT NOT NULL,
                price REAL,
                gap_pct REAL,
                score REAL,
                catalyst TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS trades (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                ticker TEXT NOT NULL,
                shares INTEGER NOT NULL,
                entry_price REAL NOT NULL,
                exit_price REAL,
                entry_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                exit_time TIMESTAMP,
                pnl REAL,
                status TEXT DEFAULT 'OPEN'
            )
        """)
        conn.commit()


def save_alert(ticker: str, price: float, gap_pct: float, score: float, catalyst: str):
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO alerts (ticker, price, gap_pct, score, catalyst)
            VALUES (?, ?, ?, ?, ?)
        """, (ticker, price, gap_pct, score, catalyst))
        conn.commit()


def get_all_trades() -> List[Dict[str, Any]]:
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM trades ORDER BY id DESC")
        rows = cursor.fetchall()
        return [dict(row) for row in rows]


def get_open_trades() -> List[Dict[str, Any]]:
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM trades WHERE status = 'OPEN'")
        rows = cursor.fetchall()
        return [dict(row) for row in rows]


def get_monthly_usage(year_month: str = None) -> Tuple[int, int]:
    """
    Calculates monthly operations (legs) and total shares traded for current month.
    Used by calculate_fee to determine free quota consumption.
    """
    if year_month is None:
        year_month = datetime.now().strftime("%Y-%m")

    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT shares, exit_time FROM trades 
            WHERE strftime('%Y-%m', entry_time) = ?
        """, (year_month,))
        rows = cursor.fetchall()

    total_ops = 0
    total_shares = 0

    for row in rows:
        shares = row['shares']
        # Buy leg
        total_ops += 1
        total_shares += shares
        # Sell leg (if completed)
        if row['exit_time'] is not None:
            total_ops += 1
            total_shares += shares

    return total_ops, total_shares
