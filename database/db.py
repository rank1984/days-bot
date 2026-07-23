import sqlite3
from datetime import datetime

# נתיב למסד הנתונים - ייווצר אוטומטית בתיקייה שבה תריץ את הקוד
DB_PATH = 'trades.db'

def init_db():
    """
    יוצר את טבלת העסקאות אם היא עדיין לא קיימת.
    מומלץ להריץ פעם אחת בתחילת התוכנית (ב-main.py).
    """
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS trades (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                ticker TEXT,
                entry REAL, stop REAL, tp1 REAL, tp2 REAL,
                rr1 REAL, rr2 REAL,
                score REAL, rvol REAL, gap REAL, dvol REAL,
                catalyst TEXT,
                entry_time TEXT,
                exit_time TEXT,
                high REAL, low REAL, close REAL,
                tp1_hit INTEGER DEFAULT 0, 
                tp2_hit INTEGER DEFAULT 0, 
                stop_hit INTEGER DEFAULT 0,
                pnl REAL DEFAULT 0, 
                win INTEGER DEFAULT 0
            )
        """)
        print("[Database] DB Initialized and ready.")

def save_trade(ticker, entry, stop, tp1, tp2, rr1, rr2, score, rvol, gap, dvol, catalyst):
    """
    שומר עסקה חדשה לתוך מסד הנתונים.
    """
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute("""
            INSERT INTO trades (ticker, entry, stop, tp1, tp2, rr1, rr2, score, rvol, gap, dvol, catalyst, entry_time)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (ticker, entry, stop, tp1, tp2, rr1, rr2, score, rvol, gap, dvol, catalyst, datetime.now().isoformat()))
        print(f"[Database] Trade for {ticker} saved successfully.")
