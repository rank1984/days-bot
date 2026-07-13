"""
DAYS-BOT Main Entry Point
"""
import sys
import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(BASE_DIR))
sys.path.insert(0, str(BASE_DIR / "utils"))

from datetime import datetime
import argparse

from utils.config import *
from scanner.premarket import scan_premarket
from scanner.universe import load_universe
from database.db import init_db, save_alert, already_sent_today
from telegram_formatter import format_preopen_list, format_no_candidates, send_message

# backtester ו-paper_trader מושבתים זמנית
# from backtester.backtester import Backtester
# from paper_trader.paper_trader import PaperTrader


def run_full_pipeline():
    """Run the full scan pipeline"""
    today = datetime.now().strftime("%Y-%m-%d")
    print(f"[Main] Mode: full")
    print(f"=== [DAYS-BOT] {today} {datetime.now().strftime('%H:%M')} ET ===")
    
    init_db()
    
    candidates = scan_premarket(today)
    
    if not candidates:
        universe = load_universe()
        msg = format_no_candidates(today, len(universe) if universe else 0)
        send_message(TELEGRAM_TOKEN, TELEGRAM_CHAT_ID, msg)
        print("[Main] No candidates found")
        return
    
    filtered = []
    for c in candidates:
        if not already_sent_today(c['ticker'], today):
            filtered.append(c)
    
    if not filtered:
        print("[Main] All candidates already sent today")
        return
    
    msg = format_preopen_list(filtered, today)
    success = send_message(TELEGRAM_TOKEN, TELEGRAM_CHAT_ID, msg)
    
    if success:
        for c in filtered:
            save_alert(
                ticker=c['ticker'],
                price=c['price'],
                gap_pct=c['gap_pct'],
                score=c.get('score', 0),
                catalyst=c.get('catalyst', '—')
            )
        print(f"[Main] Sent {len(filtered)} candidates")


def run_backtest():
    """Run backtest - מושבת זמנית"""
    print("[Main] Backtest disabled - need to fix data_fetcher")


def run_paper_trade():
    """Run paper trading - מושבת זמנית"""
    print("[Main] Paper trading disabled - need to fix data_fetcher")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument('mode', choices=['full', 'backtest', 'paper'])
    args = parser.parse_args()
    
    if args.mode == 'full':
        run_full_pipeline()
    elif args.mode == 'backtest':
        run_backtest()
    elif args.mode == 'paper':
        run_paper_trade()
