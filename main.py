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
from backtester.backtester import Backtester
from paper_trader.paper_trader import PaperTrader


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
    """Run backtest"""
    print("[Main] Running backtest...")
    bt = Backtester()
    
    # Load universe for backtest
    universe = load_universe()
    symbols = [s['symbol'] for s in universe[:50]]  # limit for demo
    
    from datetime import datetime, timedelta
    end = datetime.now()
    start = end - timedelta(days=30)
    
    bt.run_backtest(symbols, start.strftime("%Y-%m-%d"), end.strftime("%Y-%m-%d"))
    bt.save_results()


def run_paper_trade():
    """Run paper trading"""
    print("[Main] Running paper trading...")
    trader = PaperTrader()
    
    # Get account info
    account = trader.get_account()
    print(f"[PaperTrade] Account: {account.status}")
    print(f"[PaperTrade] Equity: ${float(account.equity):.2f}")
    print(f"[PaperTrade] Buying Power: ${float(account.buying_power):.2f}")
    
    # Scan for candidates
    candidates = scan_premarket(datetime.now().strftime("%Y-%m-%d"))
    
    if not candidates:
        print("[PaperTrade] No candidates found")
        return
    
    # Enter first candidate
    candidate = candidates[0]
    ticker = candidate['ticker']
    price = candidate['price']
    
    print(f"[PaperTrade] Entering {ticker} @ ${price:.2f}")
    trader.enter_trade(ticker, price)
    
    # Set stop-loss and take-profit
    stop = price * 0.95
    target = price * 1.20
    trader.set_stop_loss(ticker, stop)
    trader.set_take_profit(ticker, target)
    
    print(f"[PaperTrade] Stop-loss: ${stop:.2f}  |  Target: ${target:.2f}")


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
