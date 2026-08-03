"""
Database module for DAYS-BOT
"""
import sqlite3
import os
from datetime import datetime

DB_PATH = os.path.join(os.path.dirname(__file__), "..", "data", "alerts.db")

def init_db():
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
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
    # טבלת trades – עם כל השדות הנדרשים
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
            pnl REAL,
            win INTEGER,
            tp1_hit INTEGER,
            tp2_hit INTEGER,
            stop_hit INTEGER
        )
    """)
    conn.commit()
    conn.close()

def save_trade(ticker, entry, stop, tp1, tp2, rr1, rr2, score, rvol, gap, dvol, catalyst):
    conn = sqlite3.connect(DB_PATH)
    conn.execute("""
        INSERT INTO trades (
            ticker, entry_price, stop_price, tp1, tp2,
            rr1, rr2, score, rvol, gap, dvol, catalyst, entry_time
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        ticker, entry, stop, tp1, tp2,
        rr1, rr2, score, rvol, gap, dvol, catalyst,
        datetime.now().isoformat()
    ))
    conn.commit()
    conn.close()
    print(f"[Database] Trade for {ticker} saved successfully.")
