import sys
from datetime import datetime
import pytz

from scanner.universe  import build_universe, load_universe
from scanner.premarket import scan_premarket
from scanner.sympathy  import tag_sympathy
from scanner.scoring   import score_candidates
from database.db       import init_db, save_alert, already_sent_today
from telegram.sender   import send_message, format_alert, format_no_candidates
from utils.config      import TELEGRAM_TOKEN, TELEGRAM_CHAT_ID, MIN_SCORE

ET = pytz.timezone("America/New_York")


def run_universe_build():
    print("=== [DAYS-BOT] Phase 1: Building Universe ===")
    build_universe()


def run_alert_pipeline():
    print("=== [DAYS-BOT] Phase 2: Scan + Score + Alert ===")
    init_db()
    today = datetime.now(ET).strftime("%Y-%m-%d")

    universe   = load_universe()
    candidates = scan_premarket(universe)

    if candidates.empty:
        print("[Main] No candidates. Exiting.")
     send_message(TELEGRAM_TOKEN, TELEGRAM_CHAT_ID,
                     format_no_candidates(today, len(universe)))
        return

    candidates = tag_sympathy(candidates)
    candidates = score_candidates(candidates)
    top        = candidates[candidates["score"] >= MIN_SCORE].head(5)

    if top.empty:
        print(f"[Main] No candidates scored above {MIN_SCORE}.")
        return

    sent = 0
    for _, row in top.iterrows():
        ticker = row["ticker"]
        if already_sent_today(today, ticker):
            continue
        msg = format_alert(row.to_dict())
        ok  = send_message(TELEGRAM_TOKEN, TELEGRAM_CHAT_ID, msg)
        if ok:
            save_alert(today, row.to_dict())
            sent += 1
            print(f"[Main] ✅ {ticker} (score={row['score']:.1f})")

    print(f"[Main] Done. {sent} alert(s) sent.")


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
    print(f"[Main] Mode: {mode}")
    if mode == "universe":
        run_universe_build()
    elif mode == "alerts":
        run_alert_pipeline()
    else:
        run_universe_build()
        run_alert_pipeline()
