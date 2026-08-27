import sqlite3
from pathlib import Path
from datetime import datetime
from typing import Tuple, List, Dict, Any
import pytz

ET = pytz.timezone('America/New_York')
DB_PATH = Path(__file__).resolve().parent.parent / "days_bot.db"


def get_connection():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    """Initializes schema and runs auto-migration for missing columns."""
    with get_connection() as conn:
        cursor = conn.cursor()

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS trades (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                ticker TEXT NOT NULL,
                shares INTEGER NOT NULL DEFAULT 0,
                entry_price REAL NOT NULL,
                exit_price REAL,
                entry_time TEXT NOT NULL,
                exit_time TEXT,
                pnl REAL,
                status TEXT DEFAULT 'OPEN'
            )
        """)

        # Auto-migration check for 'shares'
        cursor.execute("PRAGMA table_info(trades)")
        columns = [column[1] for column in cursor.fetchall()]
        if 'shares' not in columns:
            cursor.execute("ALTER TABLE trades ADD COLUMN shares INTEGER DEFAULT 0")

        conn.commit()


def log_buy_trade(ticker: str, shares: int, entry_price: float) -> int:
    """Logs a BUY operation (Leg 1) in explicit ET timestamp string."""
    now_et_str = datetime.now(ET).strftime("%Y-%m-%d %H:%M:%S")
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO trades (ticker, shares, entry_price, entry_time, status)
            VALUES (?, ?, ?, ?, 'OPEN')
        """, (ticker.upper(), shares, entry_price, now_et_str))
        conn.commit()
        return cursor.lastrowid


def log_sell_trade(ticker: str, exit_price: float) -> Tuple[bool, str]:
    """
    Updates the latest OPEN trade for ticker (Leg 2).
    Returns (success_flag, warning_or_error_message).
    """
    now_et_str = datetime.now(ET).strftime("%Y-%m-%d %H:%M:%S")
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT id, shares, entry_price FROM trades 
            WHERE ticker = ? AND status = 'OPEN'
            ORDER BY id DESC
        """, (ticker.upper(),))
        rows = cursor.fetchall()

        if not rows:
            return False, f"לא נמצאה עסקה פתוחה עבור `{ticker}`."

        warning = ""
        if len(rows) > 1:
            warning = f"\n⚠️ **אזהרה:** נמצאו {len(rows)} עסקאות פתוחות עבור `{ticker}`! מעדכן את האחרונה (ID #{rows[0]['id']})."

        row = rows[0]
        trade_id = row['id']
        shares = row['shares']
        entry_price = row['entry_price']
        pnl = round((exit_price - entry_price) * shares, 2)

        cursor.execute("""
            UPDATE trades 
            SET exit_price = ?, exit_time = ?, pnl = ?, status = 'CLOSED'
            WHERE id = ?
        """, (exit_price, now_et_str, pnl, trade_id))
        conn.commit()

        return True, warning


def get_monthly_usage(year_month: str = None) -> Tuple[int, int]:
    """Calculates ops and volume using strict string prefix matching on ET timestamps."""
    if year_month is None:
        year_month = datetime.now(ET).strftime("%Y-%m")

    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT shares, exit_time 
            FROM trades 
            WHERE substr(entry_time, 1, 7) = ?
        """, (year_month,))
        rows = cursor.fetchall()

    total_ops = 0
    total_shares = 0

    for row in rows:
        shares = row['shares']
        # Leg 1: Entry
        total_ops += 1
        total_shares += shares
        # Leg 2: Exit
        if row['exit_time'] is not None:
            total_ops += 1
            total_shares += shares

    return total_ops, total_shares
