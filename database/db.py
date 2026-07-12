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
        # Create table if not exists
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
        
        # Check for missing columns and add them
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
    """
    Check if a ticker was already sent today
    
    Args:
        ticker: Stock symbol
        date_str: Date string in format YYYY-MM-DD (default: today)
    
    Returns:
        True if already sent today
    """
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
    """
    Save an alert to the database
    
    Args:
        ticker: Stock symbol
        price: Current price
        gap_pct: Gap percentage
        score: Score from scanning
        catalyst: News catalyst
    """
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


def get_recent_alerts(days: int = 7):
    """Get alerts from the last N days"""
    cutoff = (datetime.now() - timedelta(days=days)).strftime("%Y-%m-%d")
    conn = sqlite3.connect(DB_PATH)
    try:
        rows = conn.execute(
            "SELECT * FROM alerts WHERE sent_at >= ? ORDER BY sent_at DESC",
            (cutoff,)
        ).fetchall()
        return rows
    except Exception as e:
        print(f"[DB] ❌ get_recent_alerts error: {e}")
        return []
    finally:
        conn.close()
