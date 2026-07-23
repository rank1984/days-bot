import sqlite3
import os
from datetime import datetime
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "data"
os.makedirs(DATA_DIR, exist_ok=True)
DB_PATH = DATA_DIR / "days_bot.db"


def init_db():
    """אתחול בסיס הנתונים ויצירת הטבלאות במידה ואינן קיימות"""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    # טבלת התראות שנשלחו
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS alerts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            ticker TEXT,
            price REAL,
            gap_pct REAL,
            score REAL,
            catalyst TEXT,
            date_sent TEXT,
            created_at TEXT
        )
    """)
    
    # טבלת מעקב עסקאות ללמידה (כולל השדות החדשים - שלב 5)
    cursor.execute("""
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
            pm_high_dist REAL,
            news_score REAL,
            atr REAL,
            entry_time TEXT,
            exit_time TEXT,
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


def save_alert(ticker: str, price: float, gap_pct: float, score: float, catalyst: str):
    """שמירת התראה ב-DB למניעת שליחה כפולה ומעקב"""
    conn = sqlite3.connect(DB_PATH)
    today = datetime.now().strftime("%Y-%m-%d")
    now_iso = datetime.now().isoformat()
    
    conn.execute("""
        INSERT INTO alerts (ticker, price, gap_pct, score, catalyst, date_sent, created_at)
        VALUES (?, ?, ?, ?, ?, ?, ?)
    """, (ticker, price, gap_pct, score, catalyst, today, now_iso))
    
    conn.commit()
    conn.close()


def already_sent_today(ticker: str, date_str: str = None) -> bool:
    """בדיקה האם המניה כבר נשלחה היום בטלגרם"""
    if date_str is None:
        date_str = datetime.now().strftime("%Y-%m-%d")
        
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    cursor.execute("""
        SELECT COUNT(*) FROM alerts 
        WHERE ticker = ? AND date_sent = ?
    """, (ticker, date_str))
    
    count = cursor.fetchone()[0]
    conn.close()
    
    return count > 0


def save_trade(ticker, entry, stop, tp1, tp2, rr1, rr2, score, rvol, gap, dvol, catalyst, pm_high_dist=0, news_score=0, atr=0):
    """שמירת נתוני תוכנית מסחר למנגנון הלמידה כולל השדות המורחבים"""
    conn = sqlite3.connect(DB_PATH)
    conn.execute("""
        INSERT INTO trades (ticker, entry, stop, tp1, tp2, rr1, rr2, score, rvol, gap, dvol, catalyst, pm_high_dist, news_score, atr, entry_time)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (ticker, entry, stop, tp1, tp2, rr1, rr2, score, rvol, gap, dvol, catalyst, pm_high_dist, news_score, atr, datetime.now().isoformat()))
    conn.commit()
    conn.close()
