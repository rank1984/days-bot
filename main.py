"""
DAYS-BOT Main Entry Point
"""
import sys
import os
from pathlib import Path

# הוסף את ספריית הבסיס וספריית utils לנתיב
BASE_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(BASE_DIR))
sys.path.insert(0, str(BASE_DIR / "utils"))

from datetime import datetime
import time

# עכשיו import מ-utils
from utils.config import *
from scanner.premarket import scan_premarket
from scanner.universe import load_universe
from scanner.news import get_catalyst_label
from database.db import init_db, save_alert, already_sent_today
from telegram_formatter import format_preopen_list, format_no_candidates, send_message


def run_full_pipeline():
    """Run the full scan pipeline"""
    today = datetime.now().strftime("%Y-%m-%d")
    print(f"[Main] Mode: full")
    print(f"=== [DAYS-BOT] {today} {datetime.now().strftime('%H:%M')} ET ===")
    
    # Initialize database
    init_db()
    
    # Scan premarket
    candidates = scan_premarket(today)
    
    if not candidates:
        # No candidates found
        universe = load_universe()
        msg = format_no_candidates(today, len(universe) if universe else 0)
        send_message(TELEGRAM_TOKEN, TELEGRAM_CHAT_ID, msg)
        print("[Main] No candidates found")
        return
    
    # Filter candidates already sent today
    filtered = []
    for c in candidates:
        if not already_sent_today(c['ticker'], today):
            filtered.append(c)
    
    if not filtered:
        print("[Main] All candidates already sent today")
        return
    
    # Send to Telegram
    msg = format_preopen_list(filtered, today)
    send_message(TELEGRAM_TOKEN, TELEGRAM_CHAT_ID, msg)
    
    # Save to database
    for c in filtered:
        save_alert(
            ticker=c['ticker'],
            price=c['price'],
            gap_pct=c['gap_pct'],
            score=c.get('score', 0),
            catalyst=c.get('catalyst', '—')
        )
    
    print(f"[Main] Sent {len(filtered)} candidates")


if __name__ == "__main__":
    run_full_pipeline()
