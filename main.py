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
    send_message,
    format_preopen_list,
    format_no_candidates
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
    today    = datetime.now(ET).strftime("%Y-%m-%d")
    universe = build_universe()

    if universe.empty:
        send_message(TELEGRAM_TOKEN, TELEGRAM_CHAT_ID,
                     format_no_candidates(today, 0))
        return

    candidates = scan_premarket(universe)

    if candidates.empty:
        send_message(TELEGRAM_TOKEN, TELEGRAM_CHAT_ID,
                     format_no_candidates(today, len(universe)))
        return

    candidates = tag_sympathy(candidates)
    candidates = enrich_with_news(candidates)
    candidates = candidates[candidates["news_score"] >= -10].copy()

    if candidates.empty:
        send_message(TELEGRAM_TOKEN, TELEGRAM_CHAT_ID,
                     format_no_candidates(today, len(universe)))
        return

    candidates = score_candidates(candidates)

    top = candidates[candidates["score"] >= MIN_SCORE].head(5)

    if top.empty:
        top        = candidates.head(3)
        low_quality = True
    else:
        low_quality = False

    rows = top.to_dict("records")
    send_message(
        TELEGRAM_TOKEN, TELEGRAM_CHAT_ID,
        format_preopen_list(rows, today, low_quality=low_quality)
    )
    print(f"[Main] Sent {len(rows)} candidates.")

    for _, row in top.iterrows():
        if not already_sent_today(today, row["ticker"]):
            save_alert(today, row.to_dict())

    print("[Main] Done.")


if __name__ == "__main__":
    mode = sys.argv[1] if len(sys.argv) > 1 else "full"
    print(f"[Main] Mode: {mode}")
    run_full_pipeline()
