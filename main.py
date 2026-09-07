"""
DAYS-BOT V4.3 – RESEARCH ENGINE WITH LEARNING
Intraday + Swing 1–3D

Manual execution only.
No automatic orders.
"""

import sys
from pathlib import Path
from datetime import datetime

import pytz


BASE_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(BASE_DIR))

ET = pytz.timezone("America/New_York")


from utils.config import (
    TELEGRAM_TOKEN,
    TELEGRAM_CHAT_ID,
)
from scanner.premarket import scan_premarket
from scanner.full_scan_v34 import full_scan_v34
from scanner.swing_engine import calculate_swing_score
from scanner.discovery_fast import fast_discovery
from database.db import init_db, save_alert
from telegram_v3 import send_message, format_research_report
from learning.lesson_engine import (
    build_lesson,
    save_learning,
    print_lesson,
    load_previous_learning,
    format_lesson_for_telegram,
)


def _safe_swing(candidate):
    try:
        result = calculate_swing_score(candidate)
        if not isinstance(result, dict):
            return {"swing_score": 0, "swing_type": "INVALID"}
        return result
    except Exception as e:
        print(f"[Main] Swing error {candidate.get('ticker')}: {e}")
        return {"swing_score": 0, "swing_type": "ERROR", "error": str(e)}


def _classify_trade_type(candidate):
    intraday_score = float(candidate.get("composite_score", 0) or 0)
    swing_score = float(candidate.get("swing_score", 0) or 0)
    plan_valid = bool(candidate.get("plan_valid", False))
    data_status = candidate.get("data_status", "NO_TRADE")

    # If data is incomplete, downgrade
    if data_status == "NO_TRADE":
        return "NO_TRADE"
    if data_status == "WATCH":
        return "WATCH"

    # Data is complete (ACTIONABLE)
    if intraday_score >= 75 and swing_score >= 70:
        return "BOTH"
    if intraday_score >= 75 and plan_valid:
        return "INTRADAY"
    if swing_score >= 70:
        return "SWING_1_3D"
    if intraday_score >= 60 or swing_score >= 60:
        return "WATCH"
    return "WATCH"


def _get_discovery_stats(candidates: list) -> dict:
    # Extract stats from first candidate (if available)
    for c in candidates[:5]:
        if "rejection_reasons" in c:
            return {
                "universe": 500,
                "returned_snapshots": len(candidates) * 10,
                "valid_price": len(candidates),
                "valid_prev_close": len(candidates),
                "parsed_raw": len(candidates),
                "strict_candidates": len(candidates),
                "fallback_candidates": 0,
                "reject_price_low": 0,
                "reject_price_high": 0,
                "reject_gap": 0,
                "reject_volume": 0,
                "reject_invalid": 0,
            }
    return {
        "universe": 500,
        "returned_snapshots": len(candidates),
        "valid_price": len(candidates),
        "valid_prev_close": len(candidates),
        "parsed_raw": len(candidates),
        "strict_candidates": len(candidates),
        "fallback_candidates": 0,
        "reject_price_low": 0,
        "reject_price_high": 0,
        "reject_gap": 0,
        "reject_volume": 0,
        "reject_invalid": 0,
    }


def run_fullscan_v34(manual=False):
    init_db()
    now_et = datetime.now(ET)

    print("\n" + "=" * 74)
    print("DAYS-BOT V4.3 – RESEARCH ENGINE (Intraday + Swing + Learning)")
    print(f"Date: {now_et.strftime('%Y-%m-%d')} | Mode: {'MANUAL' if manual else 'LIVE'}")
    print("=" * 74)

    # ------------------------------------------------------------
    # 1. DISCOVERY
    # ------------------------------------------------------------
    print("[Main] Starting discovery...")
    candidates = scan_premarket(now_et.strftime("%Y-%m-%d"), manual)

    if not candidates:
        print("[Main] ❌ No candidates found by discovery.")
        msg = "😴 DAYS-BOT\n\nלא נמצאו מועמדים.\nאין מספיק market data כרגע.\n\n⚠️ אין לבצע עסקה על בסיס סריקה ריקה."
        send_message(TELEGRAM_TOKEN, TELEGRAM_CHAT_ID, msg)
        return

    print(f"[Main] ✅ Discovery returned {len(candidates)} candidates")
    if candidates:
        print(f"[Main] First candidate: {candidates[0].get('ticker')} (score={candidates[0].get('event_score', 0)})")

    # ------------------------------------------------------------
    # 2. FULL ANALYSIS
    # ------------------------------------------------------------
    print("[Main] Running full analysis...")
    top5 = full_scan_v34(candidates, manual)

    if not top5:
        print("[Main] ❌ Full analysis returned empty.")
        msg = "😴 DAYS-BOT\n\nה-Discovery עבד, אבל לא התקבל מועמד לניתוח מלא."
        send_message(TELEGRAM_TOKEN, TELEGRAM_CHAT_ID, msg)
        return

    print(f"[Main] ✅ Full analysis returned {len(top5)} candidates")

    # ------------------------------------------------------------
    # 3. SWING ANALYSIS
    # ------------------------------------------------------------
    print("[Main] Running swing analysis...")
    for candidate in top5:
        swing = _safe_swing(candidate)
        candidate["swing_score"] = float(swing.get("swing_score", 0) or 0)
        candidate["swing_data"] = swing
        candidate["trade_type"] = _classify_trade_type(candidate)

        try:
            save_alert(**candidate)
        except Exception as e:
            print(f"[Main] DB save error {candidate.get('ticker')}: {e}")

    # ------------------------------------------------------------
    # 4. LEARNING
    # ------------------------------------------------------------
    print("[Main] Building daily lesson...")
    discovery_stats = _get_discovery_stats(candidates)
    previous_lesson = load_previous_learning()
    lesson = build_lesson(
        candidates=candidates,
        top5=top5,
        discovery_stats=discovery_stats,
        previous_lesson=previous_lesson,
        config_params={
            "DISCOVERY_MIN_PRICE": 1.00,
            "DISCOVERY_MAX_PRICE": 30.00,
            "DISCOVERY_MIN_GAP": 3.0,
            "DISCOVERY_MIN_VOLUME": 50000,
        }
    )
    save_learning(lesson)
    print_lesson(lesson)

    # ------------------------------------------------------------
    # 5. TELEGRAM
    # ------------------------------------------------------------
    print("[Main] Sending Telegram...")

    msg = format_research_report(top5, now_et)
    send_message(TELEGRAM_TOKEN, TELEGRAM_CHAT_ID, msg)

    if lesson.get("recommendations"):
        lesson_msg = format_lesson_for_telegram(lesson)
        send_message(TELEGRAM_TOKEN, TELEGRAM_CHAT_ID, lesson_msg)

    # ------------------------------------------------------------
    # 6. SUMMARY
    # ------------------------------------------------------------
    print("\n" + "=" * 74)
    print("TOP 5")
    print("=" * 74)
    for i, c in enumerate(top5, 1):
        print(f"{i}. {c.get('ticker')} | Intraday={c.get('composite_score', 0):.1f} | Swing={c.get('swing_score', 0):.1f} | Type={c.get('trade_type', 'WATCH')} | Data={c.get('data_status', 'UNKNOWN')}")
    print("=" * 74)
    print("⚠️ NO AUTOMATIC ORDERS – MANUAL EXECUTION ONLY")
    print("=" * 74)


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python main.py fullscan_v34 [--manual]")
        sys.exit(1)

    manual = "--manual" in sys.argv
    run_fullscan_v34(manual)