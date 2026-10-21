#!/usr/bin/env python3
"""
DAYS-BOT - Swing Trade Evaluator
בודק את ביצועי תוכניות ה-Swing שנוצרו ב-DB.
עובד על בסיס נרות יומיים (Daily Bars) ולא על בסיס דקות.
"""
import sqlite3
import pandas as pd
import yfinance as yf
from datetime import datetime, timedelta
import pytz
import os

ET = pytz.timezone("America/New_York")
DB_PATH = "data/alerts.db"

def evaluate_swing_trades():
    if not os.path.exists(DB_PATH):
        print("DB not found.")
        return

    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()

    # שולף את כל ה-Snapshots שעדיין לא נבדקו ויש להם תוכנית מסחר תקפה
    # (כרגע נבדוק את כל מי שמ-2026-10-20)
    rows = cur.execute("""
        SELECT s.snapshot_id, s.ticker, s.scan_date, s.entry, s.stop, s.target_1, s.target_2
        FROM snapshots s
        LEFT JOIN outcomes o ON o.snapshot_id = s.snapshot_id
        WHERE s.trade_type = 'SWING_1_3D' 
          AND s.plan_valid = 1
          AND o.outcome_id IS NULL
    """).fetchall()

    if not rows:
        print("No new swing trades to evaluate.")
        return

    print(f"Evaluating {len(rows)} swing trades...")

    for row in rows:
        ticker = row["ticker"]
        scan_date = row["scan_date"]
        entry = float(row["entry"])
        stop = float(row["stop"])
        t1 = float(row["target_1"])
        t2 = float(row["target_2"])
        snap_id = row["snapshot_id"]

        # מושך נרות יומיים מהיום שאחרי הסריקה והלאה (עד 5 ימים)
        start_dt = datetime.strptime(scan_date, "%Y-%m-%d") + timedelta(days=1)
        end_dt = start_dt + timedelta(days=5) # בודקים שבוע קדימה
        
        try:
            df = yf.download(
                ticker,
                start=start_dt.strftime("%Y-%m-%d"),
                end=end_dt.strftime("%Y-%m-%d"),
                interval="1d",
                progress=False,
                auto_adjust=False,
                threads=False,
            )
            if df is None or df.empty:
                continue
            if isinstance(df.columns, pd.MultiIndex):
                df.columns = df.columns.get_level_values(0)
            
            df = df.dropna()
            if df.empty:
                continue

            # מחפשים את הפגיעה הראשונה
            exit_reason = "HORIZON_END"
            exit_price = float(df.iloc[-1]['Close'])
            exit_date = df.index[-1]
            days_held = len(df)
            
            t1_hit = False
            
            for i, (date, bar) in enumerate(df.iterrows()):
                high = float(bar['High'])
                low = float(bar['Low'])
                
                # בדיקת סטופ קודם (שמרני)
                if low <= stop:
                    exit_reason = "STOP_HIT"
                    exit_price = stop
                    exit_date = date
                    days_held = i + 1
                    break
                
                # בדיקת T1
                if not t1_hit and high >= t1:
                    t1_hit = True
                    # אם הגענו ל-T1, מזיזים סטופ ל-Breakeven
                    stop = entry
                
                # בדיקת T2
                if t1_hit and high >= t2:
                    exit_reason = "T2_HIT"
                    exit_price = t2
                    exit_date = date
                    days_held = i + 1
                    break
            
            # חישוב Net R
            risk = entry - float(row["stop"])
            reward = exit_price - entry
            gross_r = reward / risk if risk > 0 else 0
            
            # הערכת עלויות (ספרד + החלקה, נניח 0.5% לכל צד)
            cost_pct = 1.0 / 100.0 # 1% הלוך ושוב
            cost_dollars = entry * cost_pct
            net_r = (reward - cost_dollars) / risk if risk > 0 else 0

            if net_r > 0.1:
                outcome = "WIN"
            elif net_r < -0.1:
                outcome = "LOSS"
            else:
                outcome = "BREAKEVEN"

            # שמירה ל-DB
            cur.execute("""
                INSERT INTO outcomes 
                (snapshot_id, outcome_horizon, t0_price, exit_price, exit_reason, hold_minutes, gross_r, net_r, net_r_status, outcome, exit_rules_version)
                VALUES (?, 'SWING_3D', ?, ?, ?, ?, ?, ?, 'VALID', ?, 'SWING-E1')
            """, (snap_id, entry, exit_price, exit_reason, days_held * 390, gross_r, net_r, outcome)) # 390 דקות ביום מסחר
            
            print(f"✅ {ticker:5s} | {exit_reason:15s} | Net R: {net_r:+.2f} | {outcome}")

        except Exception as e:
            print(f"ERR {ticker}: {e}")

    conn.commit()
    conn.close()
    print("Swing evaluation complete.")

if __name__ == "__main__":
    evaluate_swing_trades()
