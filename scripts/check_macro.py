#!/usr/bin/env python3
"""
check_macro.py - V5.0.9 (Fixed)
- Saves UNKNOWN on failure (fail-closed)
- Checks bar count AFTER removing the open bar
- Uses DB_PATH from env
"""
import sqlite3
import yfinance as yf
import pandas as pd
import os
import pytz
from datetime import datetime

ET = pytz.timezone("America/New_York")
DB_PATH = os.environ.get("DB_PATH", "data/alerts.db")

def init_macro_table(conn):
    cur = conn.cursor()
    cur.execute("""
        CREATE TABLE IF NOT EXISTS macro_state (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            scan_date TEXT NOT NULL,
            status TEXT NOT NULL,
            spy_price REAL,
            sma20 REAL,
            source TEXT,
            checked_at TEXT,
            UNIQUE(scan_date)
        )
    """)
    conn.commit()

def check_macro():
    now_et = datetime.now(ET)
    scan_date = now_et.strftime("%Y-%m-%d")
    checked_at = now_et.strftime("%Y-%m-%dT%H:%M:%S%z")

    os.makedirs("data", exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    init_macro_table(conn)
    cur = conn.cursor()

    status = "UNKNOWN"
    spy_price = 0.0
    sma20 = 0.0

    print(f"[Macro] Checking market regime for {scan_date}...")
    try:
        spy = yf.download("SPY", period="40d", interval="1d", progress=False, auto_adjust=False)
        
        if isinstance(spy.columns, pd.MultiIndex):
            spy.columns = spy.columns.get_level_values(0)

        if not spy.empty:
            # --- הסרת הנר הפתוח ---
            last_bar_date = spy.index[-1].date()
            if last_bar_date >= now_et.date():
                spy = spy.iloc[:-1]

            # --- בדיקת מספר נרות אחרי הסרה ---
            if len(spy) >= 20:
                spy['SMA20'] = spy['Close'].rolling(window=20).mean()
                last_row = spy.iloc[-1]
                spy_price = float(last_row['Close'])
                sma20 = float(last_row['SMA20'])

                if pd.notna(sma20) and spy_price > 0:
                    status = "BULLISH" if spy_price > sma20 else "BEARISH"
                else:
                    status = "UNKNOWN"
            else:
                print(f"[Macro] WARNING: Only {len(spy)} closed bars available (need 20).")
                status = "UNKNOWN"

    except Exception as e:
        print(f"[Macro] FATAL: {e}")
        status = "UNKNOWN"

    # --- שמירה ל-DB (גם UNKNOWN נשמר, כדי למנוע שימוש במידע ישן) ---
    try:
        cur.execute("""
            INSERT INTO macro_state (scan_date, status, spy_price, sma20, source, checked_at)
            VALUES (?, ?, ?, ?, 'yfinance_daily', ?)
            ON CONFLICT(scan_date) DO UPDATE SET
                status = excluded.status,
                spy_price = excluded.spy_price,
                sma20 = excluded.sma20,
                checked_at = excluded.checked_at
        """, (scan_date, status, spy_price, sma20, checked_at))
        conn.commit()
        print(f"[Macro] Saved: {scan_date} | Status: {status} | SPY: ${spy_price:.2f} | SMA20: ${sma20:.2f}")
    except Exception as e:
        print(f"[Macro] ERROR saving to DB: {e}")
    finally:
        conn.close()

    return status

if __name__ == "__main__":
    check_macro()