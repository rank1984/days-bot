import sys
import time
from datetime import datetime
import pytz

from scanner.universe  import build_universe, load_universe
from scanner.premarket import scan_premarket
from scanner.sympathy  import tag_sympathy
from scanner.scoring   import score_candidates
from scanner.news      import score_news, get_catalyst_label
from database.db       import init_db, save_alert, already_sent_today
from telegram.sender   import (
    send_message, format_alert,
    format_watchlist, format_no_candidates
)
from utils.config import TELEGRAM_TOKEN, TELEGRAM_CHAT_ID, MIN_SCORE

ET = pytz.timezone("America/New_York")


def enrich_with_news(candidates):
    print("[Main] Fetching news...")
    for idx, row in candidates.iterrows():
        ns, headline = score_news(row["ticker"])
        candidates.at[idx, "news_score"] = ns
        candidates.at[idx, "catalyst"]   = get_catalyst_label(ns, headline)
        time.sleep(1)
    return candidates


def is_market_hours() -> bool:
    """האם אנחנו בשעות מסחר אמיתיות (09:00–16:00 ET)?"""
    now = datetime.now(ET)
    return now.weekday() < 5 and 9 <= now.hour < 16


def run_universe_build():
    print("=== [DAYS-BOT] Phase 1: Universe ===")
    build_universe()


def run_alert_pipeline(is_watchlist: bool = False):
    """
    is_watchlist=True  → Phase 1, שולח Watchlist בוקר
    is_watchlist=False → Phase 2, שולח Final Alerts
    """
    init_db()
    today    = datetime.now(ET).strftime("%Y-%m-%d")
    now_et   = datetime.now(ET)

    # הגנה — לא לשלוח אם לא בשעות מסחר (מונע הודעות לילה/ערב)
    if not is_market_hours():
        print(f"[Main] Outside market hours ({now_et.strftime('%H:%M ET')}) — skipping alerts.")
        return

    universe   = load_universe()
    candidates = scan_premarket(universe)

    if candidates.empty:
        send_message(
            TELEGRAM_TOKEN, TELEGRAM_CHAT_ID,
            format_no_candidates(today, len(universe))
        )
        return

    candidates = tag_sympathy(candidates)
    candidates = enrich_with_news(candidates)
    candidates = candidates[candidates["news_score"] >= -10]
    candidates = score_candidates(candidates)

    if is_watchlist:
        # Phase 1 — Watchlist: כל המועמדות, ממוינות לפי ציון
        rows = candidates.head(15).to_dict("records")
        send_message(
            TELEGRAM_TOKEN, TELEGRAM_CHAT_ID,
            format_watchlist(rows, today, phase="watchlist")
        )
        print(f"[Main] Watchlist sent — {len(rows)} candidates")
    else:
        # Phase 2 — Final Alerts: רק Grade A/A+
        top  = candidates[candidates["score"] >= MIN_SCORE].head(5)
        if top.empty:
            print(f"[Main] No candidates above score {MIN_SCORE}.")
            return

        sent = 0
        for _, row in top.iterrows():
            ticker = row["ticker"]
            if already_sent_today(today, ticker):
                print(f"[Main] {ticker} cooldown — skip.")
                continue
            ok = send_message(TELEGRAM_TOKEN, TELEGRAM_CHAT_ID, format_alert(row.to_dict()))
            if ok:
                save_alert(today, row.to_dict())
                sent += 1
                print(f"[Main] ✅ {ticker} score={row['score']:.1f} grade={row.get('grade','?')}")
            time.sleep(1)
        print(f"[Main] Done. {sent} alerts sent.")


def detect_mode() -> str:
    now = datetime.now(ET)
    h, m = now.hour, now.minute
    # 07:50-08:10 ET → universe
    if h == 7 and 50 <= m <= 59: return "universe"
    if h == 8 and 0  <= m <= 10: return "universe"
    # 09:30-09:45 ET → alerts
    if h == 9 and 30 <= m <= 45: return "alerts"
    return "full"


if __name__ == "__main__":
    mode   = sys.argv[1] if len(sys.argv) > 1 else detect_mode()
    now_et = datetime.now(ET)
    print(f"[Main] Mode: {mode} | {now_et.strftime('%Y-%m-%d %H:%M ET')}")

    if mode == "universe":
        run_universe_build()
    elif mode == "alerts":
        run_alert_pipeline(is_watchlist=False)
    elif mode == "watchlist":
        run_alert_pipeline(is_watchlist=True)
    else:
        # full — רץ שני שלבים
        run_universe_build()
        run_alert_pipeline(is_watchlist=True)   # Watchlist
        run_alert_pipeline(is_watchlist=False)  # Final Alerts
