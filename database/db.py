"""
DAYS-BOT DATABASE MODULE (WITH LEGS COUNTING FIX)
"""
import sqlite3
from pathlib import Path
from datetime import datetime
import pytz

BASE_DIR = Path(__file__).resolve().parent.parent
DB_PATH = BASE_DIR / "data" / "alerts.db"

ET = pytz.timezone('America/New_York')


def init_db():
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
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
            pnl REAL,
            status TEXT DEFAULT 'OPEN'
        )
    """)
    
    conn.commit()
    conn.close()


def save_alert(ticker: str, price: float, gap_pct: float, score: int, catalyst: str):
    init_db()
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO alerts (ticker, price, gap_pct, score, catalyst)
        VALUES (?, ?, ?, ?, ?)
    """, (ticker, price, gap_pct, score, catalyst))
    conn.commit()
    conn.close()


def log_buy_trade(ticker: str, entry_price: float, shares: int, entry_time: str = None):
    init_db()
    if not entry_time:
        entry_time = datetime.now(ET).strftime("%Y-%m-%d %H:%M:%S")
    
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO trades (ticker, entry_time, entry_price, shares, status)
        VALUES (?, ?, ?, ?, 'OPEN')
    """, (ticker, entry_time, entry_price, shares))
    conn.commit()
    conn.close()


def log_sell_trade(ticker: str, exit_price: float, exit_time: str = None) -> bool:
    init_db()
    if not exit_time:
        exit_time = datetime.now(ET).strftime("%Y-%m-%d %H:%M:%S")
    
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    cursor.execute("""
        SELECT id, entry_price, shares FROM trades
        WHERE ticker = ? AND status = 'OPEN'
        ORDER BY id DESC LIMIT 1
    """, (ticker,))
    row = cursor.fetchone()
    
    if not row:
        conn.close()
        return False
        
    trade_id, entry_price, shares = row
    pnl = (exit_price - entry_price) * shares
    
    cursor.execute("""
        UPDATE trades
        SET exit_time = ?, exit_price = ?, pnl = ?, status = 'CLOSED'
        WHERE id = ?
    """, (exit_time, exit_price, pnl, trade_id))
    
    conn.commit()
    conn.close()
    return True


def update_trade_monitor(trade_id: int = None, ticker: str = None, exit_price: float = None, pnl: float = None, status: str = None, exit_time: str = None, **kwargs):
    init_db()
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    updates = []
    params = []
    
    if exit_price is not None:
        updates.append("exit_price = ?")
        params.append(exit_price)
    if pnl is not None:
        updates.append("pnl = ?")
        params.append(pnl)
    if status is not None:
        updates.append("status = ?")
        params.append(status)
    if exit_time is not None:
        updates.append("exit_time = ?")
        params.append(exit_time)
        
    for key, value in kwargs.items():
        if value is not None and key not in ('id', 'ticker'):
            updates.append(f"{key} = ?")
            params.append(value)
            
    if updates:
        if trade_id is not None:
            query = f"UPDATE trades SET {', '.join(updates)} WHERE id = ?"
            params.append(trade_id)
            cursor.execute(query, params)
        elif ticker is not None:
            query = f"UPDATE trades SET {', '.join(updates)} WHERE ticker = ? AND status = 'OPEN'"
            params.append(ticker)
            cursor.execute(query, params)
            
    conn.commit()
    conn.close()


def get_all_trades():
    init_db()
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM trades")
    rows = cursor.fetchall()
    conn.close()
    return [dict(row) for row in rows]


def get_open_trades():
    init_db()
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM trades WHERE status = 'OPEN'")
    rows = cursor.fetchall()
    conn.close()
    return [dict(row) for row in rows]


def get_monthly_usage():
    """
    Calculates operational legs and shares traded in current ET month.
    Leg 1: Buy (Entry)
    Leg 2: Sell (Exit - counted only if exit_time is set)
    """
    init_db()
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    current_month_et = datetime.now(ET).strftime("%Y-%m")
    
    cursor.execute("""
        SELECT shares, exit_time
        FROM trades
        WHERE substr(entry_time, 1, 7) = ?
    """, (current_month_et,))
    
    rows = cursor.fetchall()
    conn.close()
    
    total_ops = 0
    total_shares = 0
    
    for shares, exit_time in rows:
        shares_cnt = shares if shares else 0
        
        # Leg 1: Entry
        total_ops += 1
        total_shares += shares_cnt
        
        # Leg 2: Exit (if completed)
        if exit_time is not None:
            total_ops += 1
            total_shares += shares_cnt
            
    return total_ops, total_shares
