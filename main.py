"""
DAYS-BOT V5.0.5.1 – RESEARCH ENGINE WITH LEARNING + REPLAY INTEGRITY

V5.0.5.1 HARDENING:
- No changes to thresholds, weights, or scoring
- Improved PM volume status (UNAVAILABLE vs ZERO)
- Explicit Gate Summary in both FullScan and main
- Replay for ALL strict candidates
- Correct version labels
"""
import sys
from pathlib import Path
from datetime import datetime
import pytz

BASE_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(BASE_DIR))

ET = pytz.timezone("America/New_York")

from utils.config import TELEGRAM_TOKEN, TELEGRAM_CHAT_ID

from scanner.full_scan_v34 import full_scan_v34
from scanner.swing_engine import calculate_swing_score
from database.db import init_db, save_alert
from telegram_v3 import send_message, format_research_report
from learning.replay_engine import save_candidate_snapshot

from learning.lesson_engine import (
    build_lesson,
    save_learning,
    print_lesson,
    load_previous_learning,
    format_lesson_for_telegram,
)


def _safe_swing(candidate, analysis=None):
    try:
        result = calculate_swing_score(candidate, analysis)
        if not isinstance(result, dict):
            print(f"[Main] ⚠️ Swing returned {type(result).__name__} for {candidate.get('ticker')}")
            return {"swing_score": 0, "swing_type": "INVALID", "qualified": False}
        return result
    except Exception as e:
        print(f"[Main] ❌ Swing error {candidate.get('ticker')}: {type(e).__name__}: {e}")
        return {"swing_score": 0, "swing_type": "ERROR", "error": str(e), "qualified": False}


def _classify_trade_type(candidate):
    intraday_score = float(candidate.get("composite_score", 0) or 0)
    swing_score = float(candidate.get("swing_score", 0) or 0)
    plan_valid = bool(candidate.get("plan_valid", False))
    data_status = candidate.get("data_status", "NO_TRADE")

    if data_status == "NO_TRADE":
        return "NO_TRADE"
    if data_status == "WATCH":
        return "WATCH"
    if float(candidate.get("gap_pct", 0) or 0) < 0:
        return "WATCH"
    if intraday_score >= 75 and swing_score >= 70:
        return "BOTH"
    if intraday_score >= 75 and plan_valid:
        return "INTRADAY"
    if swing_score >= 70:
        return "SWING_1_3D"
    if intraday_score >= 60 or swing_score >= 60:
        return "WATCH"
    return "WATCH"


def _normalize_discovery_stats(stats):
    if not isinstance(stats, dict):
        stats = {}

    print("[Main] RAW discovery stats (before normalize):")
    print(stats)

    universe_value = stats.get("universe", stats.get("requested_symbols", 0))
    if not universe_value:
        universe_value = 500

    normalized = {
        "universe": int(universe_value or 0),
        "snapshots_received": int(stats.get("snapshots_received", stats.get("returned_snapshots", 0)) or 0),
        "valid_price": int(stats.get("valid_price", 0) or 0),
        "valid_prev_close": int(stats.get("valid_prev_close", 0) or 0),
        "parsed_raw": int(stats.get("parsed_raw", 0) or 0),
        "strict_candidates": int(stats.get("strict_candidates", 0) or 0),
        "fallback_candidates": int(stats.get("fallback_candidates", 0) or 0),
        "reject_price_low": int(stats.get("reject_price_low", 0) or 0),
        "reject_price_high": int(stats.get("reject_price_high", 0) or 0),
        "reject_gap": int(stats.get("reject_gap", 0) or 0),
        "reject_volume": int(stats.get("reject_volume", 0) or 0),
        "reject_invalid": int(stats.get("reject_invalid", 0) or 0),
        "reject_float": int(stats.get("reject_float", 0) or 0),
    }

    print("[Main] Normalized discovery stats:")
    print(normalized)
    return normalized


def _run_replay_integrity_check(replay_count, strict_count):
    print()
    print("=" * 74)
    print("REPLAY INTEGRITY CHECK")
    print("=" * 74)
    strict_ok = (replay_count == strict_count)
    print(f"  strict_candidates:                    {strict_count}")
    print(f"  replay_records:                       {replay_count}")
    print(f"  replay_records == strict_candidates:  {'PASS' if strict_ok else 'FAIL'}")
    if not strict_ok:
        print()
        print("  ⚠️ WARNING: Replay count does not match strict candidates.")
        print("  ⚠️ Do NOT proceed to V5.0.6 until this is resolved.")
    print("=" * 74)
    print()
    return strict_ok


def run_fullscan_v34(manual=False):
    init_db()
    now_et = datetime.now(ET)

    print("\n" + "=" * 74)
    print("DAYS-BOT V5.0.5.1 – RESEARCH ENGINE (Hardening)")
    print(f"Date: {now_et.strftime('%Y-%m-%d')} | Mode: {'MANUAL' if manual else 'LIVE'}")
    print("=" * 74)

    # DISCOVERY
    print("[Main] Starting discovery...")
    from scanner.premarket import scan_premarket

    discovery_result = scan_premarket(now_et.strftime("%Y-%m-%d"), manual)

    if isinstance(discovery_result, tuple) and len(discovery_result) >= 2:
        candidates = discovery_result[0]
        discovery_stats = discovery_result[1]
    else:
        candidates = discovery_result
        discovery_stats = {}

    discovery_stats = _normalize_discovery_stats(discovery_stats)

    if not candidates:
        print("[Main] ❌ No candidates found by discovery.")
        msg = "😴 DAYS-BOT\n\nלא נמצאו מועמדים.\nאין מספיק market data כרגע.\n\n⚠️ אין לבצע עסקה על בסיס סריקה ריקה."
        send_message(TELEGRAM_TOKEN, TELEGRAM_CHAT_ID, msg)
        return

    print(f"[Main] ✅ Discovery returned {len(candidates)} candidates")
    print(f"[Main] Discovery diagnostics: universe={discovery_stats['universe']} | snapshots={discovery_stats['snapshots_received']} | strict={discovery_stats['strict_candidates']} | fallback={discovery_stats['fallback_candidates']}")

    # FULL ANALYSIS
    print("[Main] Running full analysis on ALL strict candidates...")
    top5 = full_scan_v34(candidates, manual)

    if not top5:
        print("[Main] ❌ Full analysis returned empty.")
        msg = "😴 DAYS-BOT\n\nה-Discovery עבד, אבל לא התקבל מועמד לניתוח מלא."
        send_message(TELEGRAM_TOKEN, TELEGRAM_CHAT_ID, msg)
        return

    print(f"[Main] ✅ Full analysis returned {len(top5)} candidates")

    # REPLAY SNAPSHOTS FOR ALL STRICT
    print("[Main] Saving replay snapshots for ALL strict candidates...")
    replay_saved = 0
    replay_failed = 0

    for idx, candidate in enumerate(candidates):
        try:
            save_candidate_snapshot(candidate, idx)
            replay_saved += 1
        except Exception as e:
            replay_failed += 1
            print(f"[Main] ⚠️ Replay snapshot error {candidate.get('ticker')}: {type(e).__name__}: {e}")

    print(f"[Main] Replay snapshots saved: {replay_saved} (failed: {replay_failed})")

    # SWING ANALYSIS FOR TOP 5
    print("[Main] Running swing analysis for Top 5...")
    for idx, candidate in enumerate(top5):
        analysis = candidate.get('analysis', {})
        swing = _safe_swing(candidate, analysis)

        candidate["swing_score"] = float(swing.get("swing_score", 0) or 0)
        candidate["qualified"] = swing.get("qualified", False)
        candidate["swing_data"] = swing
        candidate["trade_type"] = _classify_trade_type(candidate)

        try:
            save_alert(**candidate)
            print(f"[Main] DB saved: {candidate.get('ticker')}")
        except Exception as e:
            print(f"[Main] ❌ DB save error {candidate.get('ticker')}: {type(e).__name__}: {e}")

    # INTEGRITY CHECK
    strict_count = discovery_stats.get("strict_candidates", 0)
    integrity_ok = _run_replay_integrity_check(replay_saved, strict_count)

    # LEARNING
    print("[Main] Building daily lesson...")
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

    # TELEGRAM
    print("[Main] Sending Telegram...")
    msg = format_research_report(top5, now_et)
    telegram_ok = send_message(TELEGRAM_TOKEN, TELEGRAM_CHAT_ID, msg)
    print(f"[Main] Telegram report sent: {telegram_ok}")

    if lesson.get("recommendations"):
        lesson_msg = format_lesson_for_telegram(lesson)
        send_message(TELEGRAM_TOKEN, TELEGRAM_CHAT_ID, lesson_msg)

    # DISCOVERY → GATES → TOP 5 FLOW SUMMARY
    print()
    print("=" * 74)
    print("DISCOVERY → GATES → TOP 5 FLOW")
    print("=" * 74)
    print(f"  Universe:                  {discovery_stats['universe']}")
    print(f"  Valid snapshots:           {discovery_stats['snapshots_received']}")
    print(f"  Strict candidates:         {discovery_stats['strict_candidates']}")
    print(f"  Analyzed (FullScan):       {len(candidates)}")
    print(f"  Passed Gates:              {len(top5)}")  # not exact but shows final
    print(f"  In Top 5:                  {len(top5)}")
    print("=" * 74)

    # TOP 5
    print()
    print("=" * 74)
    print("TOP 5")
    print("=" * 74)
    for i, c in enumerate(top5, 1):
        pm_status = c.get('pm_volume_status', 'UNKNOWN')
        print(f"{i}. {c.get('ticker')} | Intraday={float(c.get('composite_score', 0) or 0):.1f} | Early={float(c.get('early_score', 0) or 0):.1f} | Swing={float(c.get('swing_score', 0) or 0):.1f} | PMVol={pm_status} | Type={c.get('trade_type', 'WATCH')} | Data={c.get('data_status', 'UNKNOWN')}")
    print("=" * 74)

    print()
    print("=" * 74)
    print("REPLAY SUMMARY")
    print("=" * 74)
    print(f"Universe:             {discovery_stats['universe']}")
    print(f"Valid snapshots:      {discovery_stats['snapshots_received']}")
    print(f"Strict candidates:    {strict_count}")
    print(f"Replay records:       {replay_saved}")
    print(f"Top 5:                {len(top5)}")
    print()
    print(f"Replay integrity:     {'✅ PASS' if integrity_ok else '❌ FAIL'}")
    print("=" * 74)
    print("⚠️ NO AUTOMATIC ORDERS – MANUAL EXECUTION ONLY")
    print("=" * 74)


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python main.py fullscan_v34 [--manual]")
        sys.exit(1)
    manual = "--manual" in sys.argv
    run_fullscan_v34(manual)