"""
Trade Database – stores every signal and its outcome
"""
import sqlite3
import json
from datetime import datetime
from typing import Dict, Any, Optional, List

DB_PATH = "data/trades.db"

def init_trade_db():
    conn = sqlite3.connect(DB_PATH)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS trades (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            ticker TEXT,
            entry_time TEXT,
            entry_price REAL,
            score REAL,
            rvol REAL,
            gap REAL,
            float_shares REAL,
            news_score REAL,
            pm_high_dist REAL,
            atr REAL,
            trigger_price REAL,
            stop_price REAL,
            tp1 REAL,
            tp2 REAL,
            exit_time TEXT,
            exit_price REAL,
            high REAL,
            low REAL,
            close REAL,
            tp1_hit INTEGER,
            tp2_hit INTEGER,
            stop_hit INTEGER,
            pnl REAL,
            win INTEGER
        )
    """)
    conn.commit()
    conn.close()
    print("[TradeDB] Initialized.")

def save_signal(signal: Dict[str, Any]):
    """שומר איתות לפני ביצוע"""
    conn = sqlite3.connect(DB_PATH)
    conn.execute("""
        INSERT INTO trades (
            ticker, entry_time, entry_price, score, rvol, gap,
            float_shares, news_score, pm_high_dist, atr,
            trigger_price, stop_price, tp1, tp2
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        signal['ticker'],
        signal['entry_time'],
        signal['entry_price'],
        signal.get('score', 0),
        signal.get('rvol', 0),
        signal.get('gap', 0),
        signal.get('float_shares', 0),
        signal.get('news_score', 0),
        signal.get('pm_high_dist', 0),
        signal.get('atr', 0),
        signal.get('trigger_price', 0),
        signal.get('stop_price', 0),
        signal.get('tp1', 0),
        signal.get('tp2', 0)
    ))
    conn.commit()
    conn.close()

def update_trade_outcome(ticker: str, exit_price: float, high: float, low: float, close: float):
    """מעדכן תוצאות אחרי סיום היום"""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.execute("""
        SELECT id, entry_price, tp1, tp2, stop_price FROM trades
        WHERE ticker = ? AND exit_time IS NULL
        ORDER BY entry_time DESC LIMIT 1
    """, (ticker,))
    row = cursor.fetchone()
    if not row:
        return
    
    trade_id, entry, tp1, tp2, stop = row
    pnl = ((exit_price - entry) / entry) * 100 if entry else 0
    win = 1 if pnl > 0 else 0
    tp1_hit = 1 if high >= tp1 else 0
    tp2_hit = 1 if high >= tp2 else 0
    stop_hit = 1 if low <= stop else 0
    
    conn.execute("""
        UPDATE trades SET
            exit_time = ?,
            exit_price = ?,
            high = ?,
            low = ?,
            close = ?,
            pnl = ?,
            win = ?,
            tp1_hit = ?,
            tp2_hit = ?,
            stop_hit = ?
        WHERE id = ?
    """, (datetime.now().isoformat(), exit_price, high, low, close, pnl, win, tp1_hit, tp2_hit, stop_hit, trade_id))
    conn.commit()
    conn.close()

def get_all_trades() -> List[Dict]:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.execute("SELECT * FROM trades ORDER BY entry_time DESC")
    rows = cursor.fetchall()
    conn.close()
    return [dict(row) for row in rows]
