"""
Database module for DAYS-BOT
"""
import sqlite3
import os
from datetime import datetime, timedelta

DB_PATH = os.path.join(os.path.dirname(__file__), "..", "data", "alerts.db")

def init_db():
    """Initialize database with proper schema"""
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    try:
        # Create tables
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
            CREATE TABLE IF NOT EXISTS performance (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                ticker TEXT NOT NULL,
                date TEXT NOT NULL,
                score REAL,
                price REAL,
                gap_pct REAL,
                sent_at TEXT,
                UNIQUE(ticker, date)
            )
        """)
        
        # Check and fix missing columns in alerts
        cursor = conn.execute("PRAGMA table_info(alerts)")
        columns = [row[1] for row in cursor.fetchall()]
        
        if 'sent_at' not in columns:
            print("[DB] Adding missing 'sent_at' column...")
            conn.execute("ALTER TABLE alerts ADD COLUMN sent_at TEXT NOT NULL DEFAULT '1970-01-01'")
        
        if 'price' not in columns:
            print("[DB] Adding missing 'price' column...")
            conn.execute("ALTER TABLE alerts ADD COLUMN price REAL DEFAULT 0")
        
        if 'gap_pct' not in columns:
            print("[DB] Adding missing 'gap_pct' column...")
            conn.execute("ALTER TABLE alerts ADD COLUMN gap_pct REAL DEFAULT 0")
        
        if 'score' not in columns:
            print("[DB] Adding missing 'score' column...")
            conn.execute("ALTER TABLE alerts ADD COLUMN score REAL DEFAULT 0")
        
        if 'catalyst' not in columns:
            print("[DB] Adding missing 'catalyst' column...")
            conn.execute("ALTER TABLE alerts ADD COLUMN catalyst TEXT DEFAULT ''")
        
        conn.commit()
        print("[DB] ✅ Database initialized successfully")
    except Exception as e:
        print(f"[DB] ❌ Error: {e}")
    finally:
        conn.close()


def already_sent_today(ticker: str, date_str: str = None) -> bool:
    """Check if a ticker was already sent today"""
    if date_str is None:
        date_str = datetime.now().strftime("%Y-%m-%d")
    
    conn = sqlite3.connect(DB_PATH)
    try:
        row = conn.execute(
            "SELECT id FROM alerts WHERE ticker = ? AND sent_at LIKE ? LIMIT 1",
            (ticker, f"{date_str}%")
        ).fetchone()
        return row is not None
    except Exception as e:
        print(f"[DB] ❌ already_sent_today error: {e}")
        return False
    finally:
        conn.close()


def save_alert(ticker: str, price: float, gap_pct: float, score: float, catalyst: str = ""):
    """Save an alert to the database"""
    sent_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    conn = sqlite3.connect(DB_PATH)
    try:
        conn.execute(
            "INSERT OR IGNORE INTO alerts (ticker, sent_at, price, gap_pct, score, catalyst) VALUES (?, ?, ?, ?, ?, ?)",
            (ticker, sent_at, price, gap_pct, score, catalyst)
        )
        conn.commit()
        print(f"[DB] ✅ Saved: {ticker} at {sent_at}")
    except Exception as e:
        print(f"[DB] ❌ Save error: {e}")
    finally:
        conn.close()


def update_performance(ticker: str, date: str, score: float, price: float, gap_pct: float):
    """Update daily performance tracking"""
    conn = sqlite3.connect(DB_PATH)
    try:
        conn.execute(
            """INSERT OR REPLACE INTO performance 
               (ticker, date, score, price, gap_pct, sent_at) 
               VALUES (?, ?, ?, ?, ?, ?)""",
            (ticker, date, score, price, gap_pct, datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
        )
        conn.commit()
    except Exception as e:
        print(f"[DB] ❌ update_performance error: {e}")
    finally:
        conn.close()


def get_week_performance(date: str) -> list:
    """Get performance for the week ending on given date"""
    conn = sqlite3.connect(DB_PATH)
    try:
        target_date = datetime.strptime(date, "%Y-%m-%d")
        week_start = target_date - timedelta(days=target_date.weekday())
        week_end = week_start + timedelta(days=6)
        
        start_str = week_start.strftime("%Y-%m-%d")
        end_str = week_end.strftime("%Y-%m-%d")
        
        rows = conn.execute(
            """SELECT ticker, date, score, price, gap_pct 
               FROM performance 
               WHERE date BETWEEN ? AND ?
               ORDER BY date DESC, score DESC""",
            (start_str, end_str)
        ).fetchall()
        return rows
    except Exception as e:
        print(f"[DB] ❌ get_week_performance error: {e}")
        return []
    finally:
        conn.close()


def get_today_alerts():
    """Get all alerts sent today"""
    today = datetime.now().strftime("%Y-%m-%d")
    conn = sqlite3.connect(DB_PATH)
    try:
        rows = conn.execute(
            "SELECT * FROM alerts WHERE sent_at LIKE ? ORDER BY sent_at DESC",
            (f"{today}%",)
        ).fetchall()
        return rows
    except Exception as e:
        print(f"[DB] ❌ get_today_alerts error: {e}")
        return []
    finally:
        conn.close()
