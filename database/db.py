from datetime import datetime
import sqlite3

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
                exit_price REAL,
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

def get_open_trades():
    """מחזיר רשימת עסקאות פתוחות (עוד לא נסגרו)"""
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
    conn = sqlite3.connect(DB_PATH)
    
    # מציאת העסקה הפתוחה האחרונה
    cursor = conn.execute("""
        SELECT id, entry, tp1, tp2, stop FROM trades
        WHERE ticker = ? AND exit_time IS NULL
        ORDER BY entry_time DESC LIMIT 1
    """, (ticker,))
    row = cursor.fetchone()
    
    if not row:
        print(f"[DB] No open trade found for {ticker}")
        conn.close()
        return
    
    trade_id, entry, tp1, tp2, stop = row
    
    # חישוב PnL
    pnl = ((exit_price - entry) / entry) * 100 if entry else 0
    win = 1 if pnl > 0 else 0
    
    # בדיקה אם TP1/TP2/Stop הושגו
    tp1_hit = 1 if tp1 and high >= tp1 else 0
    tp2_hit = 1 if tp2 and high >= tp2 else 0
    stop_hit = 1 if stop and low <= stop else 0
    
    # עדכון העסקה במידע הנסגר
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
    print(f"[DB] ✅ Updated trade for {ticker}: PnL={pnl:.2f}%")
