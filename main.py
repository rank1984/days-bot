"""
DAYS-BOT V3.4 – DECISION ENGINE + FULL ANALYSIS (Personality + Sympathy + VWAP)
Modes:
    python main.py scan [--manual]              # Premarket scan only
    python main.py fullscan [--manual]          # Full V3.3 analysis
    python main.py fullscan_v34 [--manual]      # Full V3.4 with Personality + Sympathy + VWAP

Flags:
    --manual   : Run even outside trading hours
    --debug    : Show all candidates with detailed debug info
"""

import sys
import json
import os
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
from telegram_v3 import format_trade_card_v31, format_full_alert_v33, format_debug_report, format_interim_report

# V3.3 Full Scan
try:
    from scanner.full_scan_v33 import full_scan_v33
    V33_AVAILABLE = True
except ImportError:
    V33_AVAILABLE = False

# V3.4 Full Scan
try:
    from scanner.full_scan_v34 import full_scan_v34
    V34_AVAILABLE = True
except ImportError:
    V34_AVAILABLE = False

# V3.0 Legacy
try:
    from risk_engine import RiskEngine
    from ai_decision import AIDecisionLayer
    from telegram_v3 import format_decision_card
    V30_AVAILABLE = True
except ImportError:
    V30_AVAILABLE = False


def save_daily_log(scan_type: str, candidates: list, mode: str, manual: bool, debug: bool):
    """שומר תיעוד יומי של כל הפעילות"""
    log_dir = BASE_DIR / "data" / "logs"
    log_dir.mkdir(parents=True, exist_ok=True)
    
    today = datetime.now(ET).strftime("%Y-%m-%d")
    log_file = log_dir / f"daily_log_{today}.json"
    
    existing_data = []
    if log_file.exists():
        try:
            with open(log_file, 'r', encoding='utf-8') as f:
                existing_data = json.load(f)
        except:
            existing_data = []
    
    entry = {
        "timestamp": datetime.now(ET).isoformat(),
        "scan_type": scan_type,
        "mode": mode,
        "manual": manual,
        "debug": debug,
        "candidates_count": len(candidates),
        "candidates": candidates[:20]
    }
    existing_data.append(entry)
    
    with open(log_file, 'w', encoding='utf-8') as f:
        json.dump(existing_data, f, indent=2, ensure_ascii=False, default=str)
    
    print(f"[Log] Saved daily log: {log_file}")


def scan_mode(manual: bool = False, debug: bool = False):
    init_db()
    wm = WatchlistManager()

    now_et = datetime.now(ET)
    today = now_et.strftime("%Y-%m-%d")

    if manual:
        run_mode = "MANUAL"
    else:
        run_mode = "V3.4_LIVE_EXPERIMENT"

    if not manual:
        if now_et.time() < time(8, 0):
            print(f"[Main] Before 08:00 ET – abort.")
            return
        if now_et.time() >= time(9, 30):
            print(f"[Main] After 09:30 ET – abort (use --manual for testing).")
            return

    print("\n" + "=" * 70)
    print(f"[Main] DAYS-BOT V3.4 – PREMARKET SCAN")
    print(f"[Main] STRATEGY: {STRATEGY_VERSION}")
    print(f"[Main] MODE: {run_mode}")
    print(f"[Main] DATE: {today}")
    print(f"[Main] TIME: {now_et.strftime('%H:%M:%S')} ET")
    print("=" * 70)

    if manual:
        print("[Main] ⚠️ MANUAL RUN – diagnostic/testing only.")
    if debug:
        print("[Main] 🐞 DEBUG MODE – showing all candidates with details")

    candidates = scan_premarket(today)
    if not candidates:
        universe = load_universe()
        msg = format_no_candidates(today, len(universe) if universe else 0)
        send_message(TELEGRAM_TOKEN, TELEGRAM_CHAT_ID, msg)
        print("[Main] No candidates found.")
        return

    enriched = []
    for c in candidates[:15]:
        plan = build_trade_plan(c)
        c.update(plan)
        c["account_size"] = ACCOUNT_SIZE
        c["risk_pct"] = MAX_RISK_PER_TRADE_V31
        enriched.append(c)

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

    save_daily_log("scan", enriched, run_mode, manual, debug)

    # שליחת טלגרם
    if enriched:
        if debug:
            for c in enriched[:5]:
                msg = format_debug_report(c)
                send_message(TELEGRAM_TOKEN, TELEGRAM_CHAT_ID, msg)
        else:
            top = enriched[0]
            msg = format_trade_card_v31(top)
            send_message(TELEGRAM_TOKEN, TELEGRAM_CHAT_ID, msg)
        print(f"[Main] Sent Telegram for {enriched[0]['ticker']}")

    print("\n" + "=" * 70)
    print("[Main] NO AUTOMATIC ORDERS – MANUAL EXECUTION ONLY.")
    print("=" * 70)


def fullscan_mode(manual: bool = False, debug: bool = False):
    """Full V3.3 mode"""
    if not V33_AVAILABLE:
        print("[Main] V3.3 full scan not available.")
        return

    init_db()
    now_et = datetime.now(ET)
    today = now_et.strftime("%Y-%m-%d")

    if manual:
        run_mode = "MANUAL_FULLSCAN"
    else:
        run_mode = "V3.3_FULLSCAN"

    print("\n" + "=" * 70)
    print(f"[Main] DAYS-BOT V3.3 – FULL ANALYSIS")
    print(f"[Main] STRATEGY: {STRATEGY_VERSION}")
    print(f"[Main] MODE: {run_mode}")
    print(f"[Main] DATE: {today}")
    print(f"[Main] TIME: {now_et.strftime('%H:%M:%S')} ET")
    print("=" * 70)

    if manual:
        print("[Main] ⚠️ MANUAL RUN – diagnostic/testing only.")
    if debug:
        print("[Main] 🐞 DEBUG MODE – showing all candidates with details")

    # נקבל את כל המועמדים (גם אלה שנפסלו) – נשתמש ב-full_scan_v33 עם flag מיוחד
    # כרגע נשתמש בפונקציה הרגילה, ואם אין מועמדים – נשלח דוח ביניים
    top5 = full_scan_v33(manual)
    
    if not top5:
        print("[Main] No candidates passed V3.3 filters.")
        # נשלח דוח ביניים עם המועמדים הקרובים ביותר
        # נצטרך לקבל את כל המועמדים מה-full_scan – נשנה מעט את full_scan_v33
        # כרגע – נשלח הודעה כללית
        msg = "📋 DAYS-BOT V3.3 – Interim Report\n\nNo candidates passed all hard filters today.\n\nCheck the daily log for details.\n\n⏳ Next scan in 15 minutes."
        send_message(TELEGRAM_TOKEN, TELEGRAM_CHAT_ID, msg)
        return

    for c in top5:
        c["strategy_version"] = STRATEGY_VERSION
        c["data_version"] = DATA_VERSION
        c["mode"] = run_mode
        save_alert(**c)

    save_daily_log("fullscan", top5, run_mode, manual, debug)

    for i, c in enumerate(top5):
        msg = format_full_alert_v33(c)
        send_message(TELEGRAM_TOKEN, TELEGRAM_CHAT_ID, msg)
        print(f"[Main] Sent V3.3 alert for {c['ticker']} ({i+1}/5)")

    print("\n" + "=" * 70)
    print("[Main] NO AUTOMATIC ORDERS – MANUAL EXECUTION ONLY.")
    print("=" * 70)


def fullscan_v34_mode(manual: bool = False, debug: bool = False):
    """Full V3.4 mode with Personality + Sympathy + VWAP – תמיד שולחת הודעה"""
    if not V34_AVAILABLE:
        print("[Main] V3.4 full scan not available.")
        return

    init_db()
    now_et = datetime.now(ET)
    today = now_et.strftime("%Y-%m-%d")

    if manual:
        run_mode = "MANUAL_FULLSCAN_V34"
    else:
        run_mode = "V3.4_FULLSCAN"

    print("\n" + "=" * 70)
    print(f"[Main] DAYS-BOT V3.4 – FULL ANALYSIS (Personality + Sympathy + VWAP)")
    print(f"[Main] STRATEGY: {STRATEGY_VERSION}")
    print(f"[Main] MODE: {run_mode}")
    print(f"[Main] DATE: {today}")
    print(f"[Main] TIME: {now_et.strftime('%H:%M:%S')} ET")
    print("=" * 70)

    if manual:
        print("[Main] ⚠️ MANUAL RUN – diagnostic/testing only.")
    if debug:
        print("[Main] 🐞 DEBUG MODE – showing all candidates with details")

    # נפעיל את הסריקה המלאה
    all_candidates = full_scan_v34(manual, return_all=True)  # נשנה את הפונקציה שתחזיר את כל המועמדים
    
    # אם full_scan_v34 לא תומך ב-return_all, נשתמש בגישה אחרת
    # כרגע – נניח שהיא מחזירה רק את המועמדים שעברו
    top5 = full_scan_v34(manual)
    
    # ============================================================
    # קריטי: גם אם אין מועמדים – שולחים הודעה
    # ============================================================
    if not top5:
        print("[Main] No candidates passed V3.4 hard filters.")
        # נשלח הודעה עם דוח ביניים
        msg = format_interim_report()  # פונקציה חדשה ב-telegram_v3
        send_message(TELEGRAM_TOKEN, TELEGRAM_CHAT_ID, msg)
        # נשמור לוג גם כשאין מועמדים
        save_daily_log("fullscan_v34", [], run_mode, manual, debug)
        return

    for c in top5:
        c["strategy_version"] = STRATEGY_VERSION
        c["data_version"] = DATA_VERSION
        c["mode"] = run_mode
        save_alert(**c)

    save_daily_log("fullscan_v34", top5, run_mode, manual, debug)

    for i, c in enumerate(top5):
        msg = format_full_alert_v33(c)
        send_message(TELEGRAM_TOKEN, TELEGRAM_CHAT_ID, msg)
        print(f"[Main] Sent V3.4 alert for {c['ticker']} ({i+1}/5)")

    print("\n" + "=" * 70)
    print("[Main] NO AUTOMATIC ORDERS – MANUAL EXECUTION ONLY.")
    print("=" * 70)


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage:")
        print("  python main.py scan [--manual] [--debug]                # Premarket scan")
        print("  python main.py fullscan [--manual] [--debug]            # Full V3.3 analysis")
        print("  python main.py fullscan_v34 [--manual] [--debug]        # Full V3.4 analysis")
        print("")
        print("  Flags:")
        print("    --manual  : Run even outside trading hours")
        print("    --debug   : Show all candidates with detailed debug info")
        sys.exit(1)

    mode = sys.argv[1].lower()
    manual_run = "--manual" in sys.argv or "--force" in sys.argv
    debug_run = "--debug" in sys.argv

    if mode == "scan":
        scan_mode(manual=manual_run, debug=debug_run)
    elif mode == "fullscan":
        fullscan_mode(manual=manual_run, debug=debug_run)
    elif mode == "fullscan_v34":
        fullscan_v34_mode(manual=manual_run, debug=debug_run)
    else:
        print(f"Unknown mode: {mode}")
        print("Available modes: scan, fullscan, fullscan_v34")
        sys.exit(1)
