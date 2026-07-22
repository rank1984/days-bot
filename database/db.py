import sqlite3
from datetime import datetime
# וודא שהמשתנה DB_PATH מוגדר בקובץ הזה

def save_trade(ticker, entry, stop, tp1, tp2, rr1, rr2, score, rvol, gap, dvol, catalyst):
    conn = sqlite3.connect(DB_PATH)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS trades (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            ticker TEXT,
            entry REAL,
            stop REAL,
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
            high REAL,
            low REAL,
            close REAL,
            tp1_hit INTEGER,
            tp2_hit INTEGER,
            stop_hit INTEGER,
            pnl REAL
        )
    """)
    conn.execute("""
        INSERT INTO trades (ticker, entry, stop, tp1, tp2, rr1, rr2, score, rvol, gap, dvol, catalyst, entry_time)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (ticker, entry, stop, tp1, tp2, rr1, rr2, score, rvol, gap, dvol, catalyst, datetime.now().isoformat()))
    conn.commit()
    conn.close()
