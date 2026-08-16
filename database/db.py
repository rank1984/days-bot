"""
Database module for DAYS-BOT
"""
import sqlite3
import os
from datetime import datetime

DB_PATH = os.path.join(os.path.dirname(__file__), "..", "data", "alerts.db")

def _ensure_db_dir():
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)

def _ensure_db():
    _ensure_db_dir()
    if not os.path.exists(DB_PATH):
        init_db()

def init_db():
    _ensure_db_dir()
    conn = sqlite3.connect(DB_PATH)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS alerts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            ticker TEXT NOT NULL,
            sent_at TEXT NOT NULL,
            price REAL,
            gap_pct REAL,
            score REAL,
            catalyst TEXT,
            UNIQUE(ticker, sent_at)
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS trades (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            ticker TEXT,
            entry_price REAL,
            stop_price REAL,
            tp1 REAL,
            tp2 REAL,
            rr1 REAL,
            rr2 REAL,
            score REAL,
            rvol REAL,
            gap REAL,
            dvol REAL,
            catalyst TEXT,
            entry_time TEXT,
            exit_time TEXT,
            exit_price REAL,
            high REAL,
            low REAL,
            close REAL,
            current_price REAL,
            pnl REAL,
            win INTEGER,
            tp1_hit INTEGER,
            tp2_hit INTEGER,
            stop_hit INTEGER,
            mfe REAL,
            mae REAL,
            trigger_price REAL,
            pm_high REAL,
            vwap REAL,
            entry_type TEXT
        )
    """)
    conn.commit()
    conn.close()
    print("[Database] DB Initialized and ready.")

def save_alert(ticker, price, gap_pct, score, catalyst):
    """שומר הודעת התראה שנשלחה לטלגרם"""
    _ensure_db()
    conn = sqlite3.connect(DB_PATH)
    conn.execute("""
        INSERT OR IGNORE INTO alerts (ticker, sent_at, price, gap_pct, score, catalyst)
        VALUES (?, ?, ?, ?, ?, ?)
    """, (ticker, datetime.now().isoformat(), price, gap_pct, score, catalyst))
    conn.commit()
    conn.close()
    print(f"[Database] Alert for {ticker} saved.")

def save_trade(ticker, entry, stop, tp1, tp2, rr1, rr2, score, rvol, gap, dvol, catalyst,
               trigger_price=None, pm_high=None, vwap=None, entry_type='MARKET'):
    _ensure_db()
    conn = sqlite3.connect(DB_PATH)
    conn.execute("""
        INSERT INTO trades (
            ticker, entry_price, stop_price, tp1, tp2,
            rr1, rr2, score, rvol, gap, dvol, catalyst,
            trigger_price, pm_high, vwap, entry_type, entry_time
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        ticker, entry, stop, tp1, tp2,
        rr1, rr2, score, rvol, gap, dvol, catalyst,
        trigger_price, pm_high, vwap, entry_type,
        datetime.now().isoformat()
    ))
    conn.commit()
    conn.close()
    print(f"[Database] Trade for {ticker} saved.")

def get_open_trades():
    if not os.path.exists(DB_PATH):
        return []
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.execute("""
        SELECT * FROM trades 
        WHERE exit_time IS NULL 
        ORDER BY entry_time DESC
    """)
    rows = cursor.fetchall()
    conn.close()
    return [dict(row) for row in rows]

def update_trade_monitor(ticker: str, current_price: float = None, high: float = None, 
                         low: float = None, mfe: float = None, mae: float = None,
                         tp1_hit: bool = None, tp2_hit: bool = None, stop_hit: bool = None,
                         exit_price: float = None, pnl: float = None, win: int = None):
    if not os.path.exists(DB_PATH):
        return
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.execute("""
        SELECT id FROM trades
        WHERE ticker = ? AND exit_time IS NULL
        ORDER BY entry_time DESC LIMIT 1
    """, (ticker,))
    row = cursor.fetchone()
    if not row:
        conn.close()
        return
    trade_id = row[0]
    updates = []
    params = []
    if current_price is not None:
        updates.append("current_price = ?"); params.append(current_price)
    if high is not None:
        updates.append("high = ?"); params.append(high)
    if low is not None:
        updates.append("low = ?"); params.append(low)
    if mfe is not None:
        updates.append("mfe = ?"); params.append(mfe)
    if mae is not None:
        updates.append("mae = ?"); params.append(mae)
    if tp1_hit is not None:
        updates.append("tp1_hit = ?"); params.append(1 if tp1_hit else 0)
    if tp2_hit is not None:
        updates.append("tp2_hit = ?"); params.append(1 if tp2_hit else 0)
    if stop_hit is not None:
        updates.append("stop_hit = ?"); params.append(1 if stop_hit else 0)
    if exit_price is not None:
        updates.append("exit_price = ?"); params.append(exit_price)
        updates.append("exit_time = ?"); params.append(datetime.now().isoformat())
    if pnl is not None:
        updates.append("pnl = ?"); params.append(pnl)
    if win is not None:
        updates.append("win = ?"); params.append(win)
    if not updates:
        conn.close()
        return
    params.append(trade_id)
    query = f"UPDATE trades SET {', '.join(updates)} WHERE id = ?"
    conn.execute(query, params)
    conn.commit()
    conn.close()

def get_all_trades():
    if not os.path.exists(DB_PATH):
        return []
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.execute("SELECT * FROM trades ORDER BY entry_time DESC")
    rows = cursor.fetchall()
    conn.close()
    return [dict(row) for row in rows]

def already_sent_today(ticker, date_str=None):
    if not os.path.exists(DB_PATH):
        return False
    if date_str is None:
        date_str = datetime.now().strftime("%Y-%m-%d")
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.execute("""
        SELECT id FROM alerts 
        WHERE ticker = ? AND sent_at LIKE ?
        LIMIT 1
    """, (ticker, f"{date_str}%"))
    row = cursor.fetchone()
    conn.close()
    return row is not None
