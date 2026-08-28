
"""
DAYS-BOT V3.0 – DECISION ENGINE & QUANT RISK MODE

Modes:
    python main.py scan
        Automatic/normal scan.
        Runs only during 08:00-09:30 ET.

    python main.py scan --manual
        Manual diagnostic/test run.
        Can be executed at any hour.
"""

import sys
from pathlib import Path
from datetime import datetime, time
import pytz

BASE_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(BASE_DIR))
sys.path.insert(0, str(BASE_DIR / "utils"))

ET = pytz.timezone("America/New_York")

from utils.config import (
    BOT_VERSION,
    STRATEGY_VERSION,
    EXPERIMENT_MODE,
    DATA_VERSION,
    TELEGRAM_TOKEN,
    TELEGRAM_CHAT_ID,
    GEMINI_API_KEY  # <-- REQUIRED FOR V3.0: Make sure this is in your config.py!
)

from scanner.premarket import scan_premarket
from scanner.universe import load_universe
from database.db import init_db, save_alert
from watchlist_manager import WatchlistManager

# Legacy Telegram formatters (kept for fallback/errors)
from telegram_formatter import format_no_candidates, send_message

# ============================================================
# V3.0 MODULES IMPORTS
# ============================================================
from risk_engine import RiskEngine
from ai_decision import AIDecisionLayer
from telegram_v3 import format_decision_card

def scan_mode(manual: bool = False):
    init_db()
    wm = WatchlistManager()

    now_et = datetime.now(ET)
    today = now_et.strftime("%Y-%m-%d")

    # ============================================================
    # MODE
    # ============================================================

    if manual:
        run_mode = "MANUAL"
    else:
        run_mode = "V3_LIVE_EXPERIMENT"

    # ============================================================
    # AUTOMATIC / EXPERIMENT WINDOW
    # ============================================================

    if not manual:
        if now_et.time() < time(8, 0):
            print(f"\n[Main] {BOT_VERSION} – {now_et.strftime('%H:%M:%S')} ET is before experiment window (08:00 ET).")
            print("[Main] Automatic scan aborted.")
            return

        if now_et.time() >= time(9, 30):
            print(f"\n[Main] {BOT_VERSION} – {now_et.strftime('%H:%M:%S')} ET is after experiment window (09:30 ET).")
            print("[Main] Automatic scan aborted.")
            return

    # ============================================================
    # START V3.0
    # ============================================================

    print("\n" + "=" * 70)
    print(f"[Main] DAYS-BOT V3.0 DECISION ENGINE")
    print(f"[Main] STRATEGY: {STRATEGY_VERSION}")
    print(f"[Main] MODE: {run_mode}")
    print(f"[Main] DATE: {today}")
    print(f"[Main] TIME: {now_et.strftime('%H:%M:%S')} ET")
    print("=" * 70)

    if manual:
        print("[Main] ⚠️ MANUAL RUN – diagnostic/testing only.")

    # ============================================================
    # SCAN
    # ============================================================

    candidates = scan_premarket(today)

    if not candidates:
        universe = load_universe()
        msg = format_no_candidates(today, len(universe) if universe else 0)
        send_message(TELEGRAM_TOKEN, TELEGRAM_CHAT_ID, msg)
        print("[Main] No candidates found.")
        return

    # ============================================================
    # SAVE TO DATABASE & WATCHLIST
    # ============================================================
    
    added = 0
    for c in candidates[:10]:
        if "/" in c["ticker"]:
            continue
        c["strategy_version"] = STRATEGY_VERSION
        c["data_version"] = DATA_VERSION
        c["mode"] = run_mode

        wm.add_to_watchlist(c)
        save_alert(**c)
        added += 1

    print(f"\n[Main] Saved {added} candidates to Watchlist & DB.")

    # ============================================================
    # V3.0 DECISION PIPELINE (TOP 5)
    # ============================================================
    print("\n[Main] Initiating V3.0 Quant & AI Decision Pipeline for Top 5...")
    
    risk_engine = RiskEngine()
    try:
        ai_layer = AIDecisionLayer(api_key=GEMINI_API_KEY)
    except NameError:
        print("\n[ERROR] GEMINI_API_KEY is missing from utils/config.py!")
        sys.exit(1)

    # 1. Get Global Market Regime (Applies to all trades today)
    regime_name, regime_mult, regime_reasons = risk_engine.get_market_regime()
    print(f"[Quant] Market Regime: {regime_name} (Multiplier: {regime_mult})")

    # 2. Process Top 5 Candidates
    for i, c in enumerate(candidates[:5]):
        ticker = c['ticker']
        print(f"\n--- Processing {ticker} ({i+1}/5) ---")
        
        # Prepare Data Objects
        stock_price = c.get("price", c.get("close", 0))
        pm_high = c.get("pm_high", stock_price * 1.02) # Fallback if missing
        pm_vwap = c.get("pm_vwap", stock_price * 0.98) # Fallback if missing
        
        stock_data = {
            "ticker": ticker,
            "price": stock_price,
            "gap_pct": c.get("gap_pct", 0),
            "pm_volume": c.get("pm_volume", 0)
        }

        # A. Calculate Quant Trade Plan
        trade_plan = risk_engine.calculate_trade_plan(
            price=stock_price,
            pm_high=pm_high,
            pm_vwap=pm_vwap,
            regime_multiplier=regime_mult
        )
        
        quant_data = {
            "regime": regime_name,
            "regime_reasons": regime_reasons,
            **trade_plan
        }

        # B. AI Analysis
        print(f"[{ticker}] Fetching AI setup evaluation...")
        ai_decision = ai_layer.analyze_setup(stock_data, quant_data)

        # C. Generate & Send Telegram Card
        print(f"[{ticker}] AI Decision: {ai_decision.get('decision')} (Score: {ai_decision.get('score')})")
        msg = format_decision_card(stock_data, quant_data, ai_decision)
        
        send_message(TELEGRAM_TOKEN, TELEGRAM_CHAT_ID, msg)

    # ============================================================
    # END
    # ============================================================

    print("\n" + "=" * 70)
    print(f"[Main] Scan & Decision Pipeline Complete.")
    print("=" * 70)

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python main.py scan [--manual]")
        sys.exit(1)

    mode = sys.argv[1].lower()

    if mode != "scan":
        print(f"Unknown mode: {mode}")
        sys.exit(1)

    manual_run = "--manual" in sys.argv or "--force" in sys.argv
    scan_mode(manual=manual_run)
