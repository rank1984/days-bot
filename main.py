"""
main.py — DAYS-BOT V2
----------------------
Phase 1 (15:30 IL): Universe + Watchlist
Phase 2 (16:45 IL): Final Alerts
"""

import sys
import time
from datetime import datetime
import pytz

from scanner.universe  import build_universe, load_universe
from scanner.premarket import scan_premarket
from scanner.sympathy  import tag_sympathy
from scanner.scoring   import score_candidates
from database.db       import init_db, save_alert, already_sent_today
from telegram.sender   import (
    send_message, format_alert,
    format_watchlist
)
from utils.config import TELEGRAM_TOKEN, TELEGRAM_CHAT_ID, MIN_SCORE

ET = pytz.timezone("America/New_York")

def run_universe_build():
    print("=== [DAYS-BOT V2] Phase 1: Universe ===")
    return build_universe()

def run_alert_pipeline(send_watchlist: bool = True):
    print("=== [DAYS-BOT V2] Phase 2: Scan + Score + Alert ===")
    init_db()
    today = datetime.now(ET).strftime("%Y-%m-%d")
    universe = load_universe()

    if universe.empty:
        send_message(TELEGRAM_TOKEN, TELEGRAM_CHAT_ID, "⚠️ DAYS-BOT: שגיאה - יוניברס ריק.")
        return

    # סריקת פרימרקט
    candidates = scan_premarket(universe)

    # שדרוג קריטי: מניעת קריסת טלגרם (400 Bad Request) כשהרשימה ריקה
    if candidates.empty:
        print("[Main] No candidates passed the filters today.")
        send_message(
            TELEGRAM_TOKEN, 
            TELEGRAM_CHAT_ID, 
            "⚠️ DAYS-BOT: הסריקה הסתיימה. אין היום מניות שעברו את סינוני המחיר והווליום הקשוחים בפרימרקט."
        )
        return

    # Sympathy Engine
    candidates = tag_sympathy(candidates)

    # ציון מומנטום נקי מבוסס פרייס אקשן וווליום
    candidates = score_candidates(candidates)

    # Watchlist בוקר
    if send_watchlist and len(candidates) > 0:
        watchlist_rows = candidates.head(15).to_dict("records")
        send_message(TELEGRAM_TOKEN, TELEGRAM_CHAT_ID,
                     format_watchlist(watchlist_rows, today))
        print(f"[Main] Watchlist sent ({len(watchlist_rows)} candidates)")

    # Final Top 5
    top = candidates[candidates["score"] >= MIN_SCORE].head(5)

    if top.empty:
        print(f"[Main] No candidates scored above {MIN_SCORE}.")
        send_message(
            TELEGRAM_TOKEN, 
            TELEGRAM_CHAT_ID, 
            f"⚠️ DAYS-BOT: יש מניות בסריקה, אך אף אחת לא עברה את ציון המינימום ({MIN_SCORE})."
        )
        return

    sent = 0
    for _, row in top.iterrows():
        ticker = row["ticker"]

        # Cooldown
        if already_sent_today(today, ticker):
            print(f"[Main] {ticker} in cooldown — skipping.")
            continue

        msg = format_alert(row.to_dict())
        ok  = send_message(TELEGRAM_TOKEN, TELEGRAM_CHAT_ID, msg)

        if ok:
            save_alert(today, row.to_dict())
            sent += 1
            print(f"[Main] ✅ {ticker} score={row['score']:.1f}")
        time.sleep(1)

    print(f"[Main] Done. {sent} alerts sent.")


def detect_mode() -> str:
    now = datetime.now(ET)
    h, m = now.hour, now.minute
    if h == 7 and 25 <= m <= 45:
        return "universe"
    if (h == 8 and m >= 40) or (h == 9 and m == 0):
        return "alerts"
    return "full"


if __name__ == "__main__":
    mode = sys.argv[1] if len(sys.argv) > 1 else detect_mode()
    print(f"[Main] Mode: {mode} | {datetime.now(ET).strftime('%Y-%m-%d %H:%M ET')}")

    if mode == "universe":
        run_universe_build()
    elif mode == "alerts":
        run_alert_pipeline(send_watchlist=False)
    else:
        run_universe_build()
        run_alert_pipeline(send_watchlist=True)
