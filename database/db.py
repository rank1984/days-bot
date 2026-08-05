"""
Database module for DAYS-BOT
"""
import sqlite3
import os
from datetime import datetime

DB_PATH = os.path.join(os.path.dirname(__file__), "..", "data", "alerts.db")

def _ensure_db_dir():
    """מוודא שתיקיית data קיימת"""
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)

def _ensure_db():
    """מוודא שקובץ ה-DB קיים, אם לא – יוצר אותו"""
    _ensure_db_dir()
    if not os.path.exists(DB_PATH):
        init_db()  # יוצר את הטבלאות

def init_db():
    """אתחול מסד הנתונים – יוצר את כל הטבלאות"""
    _ensure_db_dir()
    conn = sqlite3.connect(DB_PATH)
    
    # טבלת alerts – היסטוריית שליחות לטלגרם
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
    
    # טבלת trades – כל העסקאות עם כל הפרמטרים
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
    print(f"[Database] Alert for {ticker} saved successfully.")

def save_trade(ticker, entry, stop, tp1, tp2, rr1, rr2, score, rvol, gap, dvol, catalyst):
    """שומר עסקה חדשה"""
    _ensure_db()
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

def get_open_trades():
    """מחזיר רשימת עסקאות פתוחות (עוד לא נסגרו)"""
    if not os.path.exists(DB_PATH):
        return []  # אם אין DB, אין עסקאות פתוחות
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

def update_trade_outcome(ticker: str, exit_price: float, high: float, low: float, close: float):
    """מעדכן תוצאות של עסקה בסוף היום"""
    if not os.path.exists(DB_PATH):
        print(f"[Database] No DB, cannot update {ticker}")
        return
    
    conn = sqlite3.connect(DB_PATH)
    
    # מצא את העסקה הפתוחה האחרונה עבור הטיקר
    cursor = conn.execute("""
        SELECT id, entry_price, tp1, tp2, stop_price FROM trades
        WHERE ticker = ? AND exit_time IS NULL
        ORDER BY entry_time DESC LIMIT 1
    """, (ticker,))
    row = cursor.fetchone()
    
    if not row:
        print(f"[Database] No open trade found for {ticker}")
        conn.close()
        return
    
    trade_id, entry, tp1, tp2, stop = row
    
    # חישוב P&L
    pnl = ((exit_price - entry) / entry) * 100 if entry else 0
    win = 1 if pnl > 0 else 0
    
    # בדיקה אם TP1, TP2 או Stop הושגו
    tp1_hit = 1 if high >= tp1 else 0
    tp2_hit = 1 if high >= tp2 else 0
    stop_hit = 1 if low <= stop else 0
    
    # עדכון
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
    """, (
        datetime.now().isoformat(),
        exit_price,
        high,
        low,
        close,
        pnl,
        win,
        tp1_hit,
        tp2_hit,
        stop_hit,
        trade_id
    ))
    
    conn.commit()
    conn.close()
    print(f"[Database] ✅ Updated trade for {ticker}: PnL={pnl:.2f}%")

def get_all_trades():
    """מחזיר את כל העסקאות מהמסד"""
    if not os.path.exists(DB_PATH):
        return []
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.execute("SELECT * FROM trades ORDER BY entry_time DESC")
    rows = cursor.fetchall()
    conn.close()
    return [dict(row) for row in rows]

def already_sent_today(ticker, date_str=None):
    """בודק אם התראה כבר נשלחה היום עבור טיקר"""
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
