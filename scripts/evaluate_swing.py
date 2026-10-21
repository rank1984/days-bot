#!/usr/bin/env python3
"""
DAYS-BOT - Swing Trade Evaluator
בודק את ביצועי תוכניות ה-Swing שנוצרו ב-DB.
עובד על בסיס נרות יומיים (Daily Bars) וממתין 5 ימים לפני שמכריע.
"""
import sqlite3
import pandas as pd
import yfinance as yf
from datetime import datetime, timedelta
import pytz
import os

ET = pytz.timezone("America/New_York")
DB_PATH = "data/alerts.db"

# כמה ימי מסחר מינימום צריכים לעבור לפני שנחשב את התוצאה
MIN_DAYS_TO_EVALUATE = 5

def evaluate_swing_trades():
    if not os.path.exists(DB_PATH):
        print("DB not found.")
        return

    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()

    # שולף את כל ה-Snapshots שעדיין לא נבדקו ויש להם תוכנית מסחר תקפה
    rows = cur.execute("""
        SELECT s.snapshot_id, s.ticker, s.scan_date, s.entry, s.stop, s.target_1, s.target_2
        FROM snapshots s
        LEFT JOIN outcomes o ON o.snapshot_id = s.snapshot_id
        WHERE s.trade_type = 'SWING_1_3D' 
          AND s.entry IS NOT NULL 
          AND s.stop IS NOT NULL
          AND s.target_1 IS NOT NULL
          AND o.outcome_id IS NULL
    """).fetchall()

    if not rows:
        print("No new swing trades to evaluate.")
        return

    print(f"Checking {len(rows)} swing trades against current date...")
    
    today = datetime.now(ET).date()
    evaluated_count = 0
    pending_count = 0
    wins, losses, breakeven = 0, 0, 0
    total_net_r = 0.0

    for row in rows:
        ticker = row["ticker"]
        scan_date_str = row["scan_date"]
        entry = float(row["entry"])
        stop = float(row["stop"])
        t1 = float(row["target_1"])
        t2 = float(row["target_2"])
        snap_id = row["snapshot_id"]

        # בדיקת גיל העסקה (חייב לעבור 5 ימים)
        scan_date_obj = datetime.strptime(scan_date_str, "%Y-%m-%d").date()
        days_since_scan = (today - scan_date_obj).days
        
        if days_since_scan < MIN_DAYS_TO_EVALUATE:
            print(f"⏳ {ticker:5s} | PENDING — only {days_since_scan} days old (needs {MIN_DAYS_TO_EVALUATE})")
            pending_count += 1
            continue

        # העסקה בשלה להערכה. מושך נתונים למשך 5 ימים מהסריקה
        start_dt = datetime.strptime(scan_date_str, "%Y-%m-%d") + timedelta(days=1)
        end_dt = start_dt + timedelta(days=7)
        
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
            current_stop = stop
            
            for i, (date, bar) in enumerate(df.iterrows()):
                high = float(bar['High'])
                low = float(bar['Low'])
                
                # בדיקת סטופ קודם (שמרני)
                if low <= current_stop:
                    if t1_hit:
                        exit_reason = "STOP_BE_AFTER_T1"
                    else:
                        exit_reason = "STOP_HIT"
                    exit_price = current_stop
                    exit_date = date
                    days_held = i + 1
                    break
                
                # בדיקת T1
                if not t1_hit and high >= t1:
                    t1_hit = True
                    current_stop = entry # מזיזים סטופ ל-Breakeven
                
                # בדיקת T2
                if t1_hit and high >= t2:
                    exit_reason = "T2_HIT"
                    exit_price = t2
                    exit_date = date
                    days_held = i + 1
                    break
            
            # חישוב Net R
            risk = entry - stop
            reward = exit_price - entry
            gross_r = reward / risk if risk > 0 else 0
            
            # הערכת עלויות (ספרד + החלקה, נניח 1% לכל צד עבור שמרנות)
            cost_pct = 1.0 / 100.0 
            cost_dollars = entry * cost_pct
            net_r = (reward - cost_dollars) / risk if risk > 0 else 0

            if net_r > 0.1:
                outcome = "WIN"
                wins += 1
            elif net_r < -0.1:
                outcome = "LOSS"
                losses += 1
            else:
                outcome = "BREAKEVEN"
                breakeven += 1

            total_net_r += net_r
            evaluated_count += 1

            # שמירה ל-DB
            cur.execute("""
                INSERT INTO outcomes 
                (snapshot_id, outcome_horizon, t0_price, exit_price, exit_reason, hold_minutes, gross_r, net_r, net_r_status, outcome, exit_rules_version)
                VALUES (?, 'SWING_3D', ?, ?, ?, ?, ?, ?, 'VALID', ?, 'SWING-E1')
            """, (snap_id, entry, exit_price, exit_reason, days_held * 390, gross_r, net_r, outcome)) 
            
            print(f"✅ {ticker:5s} | {exit_reason:20s} | Net R: {net_r:+.2f} | {outcome}")

        except Exception as e:
            print(f"ERR {ticker}: {e}")

    conn.commit()
    conn.close()
    
    print(f"\n--- SWING EVALUATION SUMMARY ---")
    print(f"Evaluated: {evaluated_count} | Pending: {pending_count}")
    if evaluated_count > 0:
        print(f"Win Rate: {wins/evaluated_count*100:.1f}% ({wins}W / {losses}L / {breakeven}BE)")
        print(f"Avg Net R: {total_net_r/evaluated_count:+.2f}R")
    print(f"Swing evaluation complete.")

if __name__ == "__main__":
    evaluate_swing_trades()
