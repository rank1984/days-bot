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
    send_message, format_preopen_list,
    format_alert, format_no_candidates
)
from utils.config import TELEGRAM_TOKEN, TELEGRAM_CHAT_ID, MIN_SCORE

ET = pytz.timezone("America/New_York")


def enrich_with_news(candidates):
    print(f"[Main] Fetching news for {len(candidates)} candidates...")
    for idx, row in candidates.iterrows():
        try:
            ns, headline = score_news(row["ticker"])
            candidates.at[idx, "news_score"] = ns
            candidates.at[idx, "catalyst"]   = get_catalyst_label(ns, headline)
        except Exception:
            candidates.at[idx, "news_score"] = 0
            candidates.at[idx, "catalyst"]   = "—"
        time.sleep(0.5)
    return candidates


def run_full_pipeline():
    print(f"=== [DAYS-BOT] {datetime.now(ET).strftime('%Y-%m-%d %H:%M ET')} ===")
    init_db()
    today = datetime.now(ET).strftime("%Y-%m-%d")

    # שלב 1 — Universe
    universe = build_universe()
    if universe.empty:
        send_message(TELEGRAM_TOKEN, TELEGRAM_CHAT_ID,
                     format_no_candidates(today, 0))
        return

    # שלב 2 — Premarket scan
    candidates = scan_premarket(universe)

    # שלב 3 — אם אין כלום — שלח בכל זאת top 5 לפי גאפ בלבד
    if candidates.empty:
        print("[Main] No candidates passed filters — sending top gap list.")
        candidates = universe.copy()
        candidates["gap_pct"]       = 0.0
        candidates["pm_volume"]     = 0
        candidates["pm_high"]       = candidates["price"]
        candidates["pm_high_dist"]  = 0.0
        candidates["dollar_volume"] = 0
        candidates["daily_rvol"]    = 0.0
        candidates["pm_rvol"]       = 0.0
        candidates["vol_ratio"]     = 0.0
        candidates["prev_close"]    = candidates["price"]
        candidates["float"]         = candidates.get("float", 0)
        candidates["news_score"]    = 0
        candidates["catalyst"]      = "—"
        candidates["is_leader"]     = False
        candidates["leader"]        = ""
        candidates["reason"]        = ""
        candidates["score"]         = 0.0
        candidates["grade"]         = "C"
        candidates = candidates.head(5)
        send_message(TELEGRAM_TOKEN, TELEGRAM_CHAT_ID,
                     format_no_candidates(today, len(universe)))
        return

    # שלב 4 — Sympathy + News + Score
    candidates = tag_sympathy(candidates)
    candidates = enrich_with_news(candidates)
    candidates = candidates[candidates["news_score"] >= -10].copy()
    candidates = score_candidates(candidates)

    # שלב 5 — שלח רשימה תמיד
    top5 = candidates.head(5)
    rows = top5.to_dict("records")

    send_message(
        TELEGRAM_TOKEN, TELEGRAM_CHAT_ID,
        format_preopen_list(rows, today)
    )
    print(f"[Main] Sent list of {len(rows)} candidates.")

    # שלב 6 — שמור בDB
    for _, row in top5.iterrows():
        ticker = row["ticker"]
        if not already_sent_today(today, ticker):
            save_alert(today, row.to_dict())

    print("[Main] Done.")


if __name__ == "__main__":
    mode = sys.argv[1] if len(sys.argv) > 1 else "full"
    print(f"[Main] Mode: {mode}")
    run_full_pipeline()
