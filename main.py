"""
DAYS-BOT V3.3 – DECISION ENGINE + FULL ANALYSIS
Modes:
    python main.py scan [--manual]         # Premarket scan only
    python main.py fullscan [--manual]     # Full analysis with all metrics
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
    GEMINI_API_KEY,
    ACCOUNT_SIZE,
    MAX_RISK_PER_TRADE_V31
)

from scanner.premarket import scan_premarket
from scanner.universe import load_universe
from database.db import init_db, save_alert
from watchlist_manager import WatchlistManager
from telegram_formatter import format_no_candidates, send_message
from risk.trade_plan import build_trade_plan
from telegram_v3 import format_trade_card_v31, format_full_alert_v33

# ============================================================
# V3.0 MODULES (for backward compatibility)
# ============================================================
try:
    from risk_engine import RiskEngine
    from ai_decision import AIDecisionLayer
    from telegram_v3 import format_decision_card
    V30_AVAILABLE = True
except ImportError:
    V30_AVAILABLE = False

# ============================================================
# V3.3 FULL SCAN
# ============================================================
from scanner.full_scan_v33 import full_scan_v33


def scan_mode(manual: bool = False):
    init_db()
    wm = WatchlistManager()

    now_et = datetime.now(ET)
    today = now_et.strftime("%Y-%m-%d")

    if manual:
        run_mode = "MANUAL"
    else:
        run_mode = "V3.3_LIVE_EXPERIMENT"

    # Automatic window
    if not manual:
        if now_et.time() < time(8, 0):
            print(f"[Main] Before 08:00 ET – abort.")
            return
        if now_et.time() >= time(9, 30):
            print(f"[Main] After 09:30 ET – abort (use --manual for testing).")
            return

    print("\n" + "=" * 70)
    print(f"[Main] DAYS-BOT V3.3 – PREMARKET SCAN + FULL ANALYSIS")
    print(f"[Main] STRATEGY: {STRATEGY_VERSION}")
    print(f"[Main] MODE: {run_mode}")
    print(f"[Main] DATE: {today}")
    print(f"[Main] TIME: {now_et.strftime('%H:%M:%S')} ET")
    print("=" * 70)

    if manual:
        print("[Main] ⚠️ MANUAL RUN – diagnostic/testing only.")

    # 1. Scan
    candidates = scan_premarket(today)
    if not candidates:
        universe = load_universe()
        msg = format_no_candidates(today, len(universe) if universe else 0)
        send_message(TELEGRAM_TOKEN, TELEGRAM_CHAT_ID, msg)
        print("[Main] No candidates found.")
        return

    # 2. Build Trade Plan for Top 10
    enriched = []
    for c in candidates[:10]:
        plan = build_trade_plan(c)
        c.update(plan)
        c["account_size"] = ACCOUNT_SIZE
        c["risk_pct"] = MAX_RISK_PER_TRADE_V31
        enriched.append(c)

    # 3. Save to DB & Watchlist
    added = 0
    for c in enriched[:5]:
        if "/" in c["ticker"]:
            continue
        c["strategy_version"] = STRATEGY_VERSION
        c["data_version"] = DATA_VERSION
        c["mode"] = run_mode
        wm.add_to_watchlist(c)
        save_alert(**c)
        added += 1
    print(f"[Main] Saved {added} candidates.")

    # 4. Send Telegram (top 1) – V3.1 format
    if enriched:
        top = enriched[0]
        msg = format_trade_card_v31(top)
        send_message(TELEGRAM_TOKEN, TELEGRAM_CHAT_ID, msg)
        print(f"[Main] Sent Telegram for {top['ticker']}")

    # 5. Optional: V3.0 Legacy pipeline (if available)
    if V30_AVAILABLE and len(enriched) >= 5:
        print("\n[Main] Running V3.0 legacy pipeline for comparison...")
        run_v30_pipeline(enriched[:5])

    print("\n" + "=" * 70)
    print("[Main] NO AUTOMATIC ORDERS – MANUAL EXECUTION ONLY.")
    print("=" * 70)


def fullscan_mode(manual: bool = False):
    """
    מצב Full Scan V3.3 – מפעיל את כל האנליזות
    """
    init_db()
    now_et = datetime.now(ET)
    today = now_et.strftime("%Y-%m-%d")

    if manual:
        run_mode = "MANUAL_FULLSCAN"
    else:
        run_mode = "V3.3_FULLSCAN"

    print("\n" + "=" * 70)
    print(f"[Main] DAYS-BOT V3.3 – FULL ANALYSIS (ALL METRICS)")
    print(f"[Main] STRATEGY: {STRATEGY_VERSION}")
    print(f"[Main] MODE: {run_mode}")
    print(f"[Main] DATE: {today}")
    print(f"[Main] TIME: {now_et.strftime('%H:%M:%S')} ET")
    print("=" * 70)

    if manual:
        print("[Main] ⚠️ MANUAL RUN – diagnostic/testing only.")

    # 1. Run Full Scan V3.3
    top5 = full_scan_v33(manual)

    if not top5:
        print("[Main] No candidates passed all V3.3 filters.")
        return

    # 2. Save to DB
    for c in top5:
        c["strategy_version"] = STRATEGY_VERSION
        c["data_version"] = DATA_VERSION
        c["mode"] = run_mode
        save_alert(**c)

    # 3. Send Telegram for each Top 5
    for i, c in enumerate(top5):
        msg = format_full_alert_v33(c)
        send_message(TELEGRAM_TOKEN, TELEGRAM_CHAT_ID, msg)
        print(f"[Main] Sent V3.3 alert for {c['ticker']} ({i+1}/5)")

    print("\n" + "=" * 70)
    print("[Main] NO AUTOMATIC ORDERS – MANUAL EXECUTION ONLY.")
    print("=" * 70)


def run_v30_pipeline(candidates):
    """V3.0 legacy pipeline for reference"""
    try:
        risk_engine = RiskEngine()
        ai_layer = AIDecisionLayer(api_key=GEMINI_API_KEY)

        regime_name, regime_mult, regime_reasons = risk_engine.get_market_regime()
        print(f"[V3.0] Market Regime: {regime_name} (Multiplier: {regime_mult})")

        for i, c in enumerate(candidates):
            ticker = c['ticker']
            stock_price = c.get("price", c.get("close", 0))
            pm_high = c.get("pm_high", stock_price * 1.02)
            pm_vwap = c.get("pm_vwap", stock_price * 0.98)

            stock_data = {
                "ticker": ticker,
                "price": stock_price,
                "gap_pct": c.get("gap_pct", 0),
                "pm_volume": c.get("pm_volume", 0)
            }

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

            ai_decision = ai_layer.analyze_setup(stock_data, quant_data)
            msg = format_decision_card(stock_data, quant_data, ai_decision)
            send_message(TELEGRAM_TOKEN, TELEGRAM_CHAT_ID, msg)
            print(f"[V3.0] Sent card for {ticker}")
    except Exception as e:
        print(f"[V3.0] Error running legacy pipeline: {e}")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage:")
        print("  python main.py scan [--manual]        # Premarket scan")
        print("  python main.py fullscan [--manual]    # Full V3.3 analysis")
        sys.exit(1)

    mode = sys.argv[1].lower()
    manual_run = "--manual" in sys.argv or "--force" in sys.argv

    if mode == "scan":
        scan_mode(manual=manual_run)
    elif mode == "fullscan":
        fullscan_mode(manual=manual_run)
    else:
        print(f"Unknown mode: {mode}")
        print("Available modes: scan, fullscan")
        sys.exit(1)
