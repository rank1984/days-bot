"""
DAYS-BOT V5.0.6-prep.2 – RESEARCH ENGINE WITH SNAPSHOT SCHEMA

Intraday + Swing 1–3D
Manual execution only.
No automatic orders.

V5.0.6-prep.2 changes (over prep.1):
- FIXED (root cause of 28 PM violations): save_snapshot was being
  called with partial PM data (pm_volume/pm_high populated, pm_bars=0).
  New _sanitize_pm_fields() enforces PM evidence atomicity:
    * pm_bars > 0  → keep all PM scalars; ensure pm_source is set
    * pm_bars = 0  → NULL out pm_volume, pm_high, pm_low, pm_vwap,
                     pm_source; set status to NO_DATA / NO_PM_BARS
  This prevents the DB from ever containing partial PM state.

V5.0.6-prep.1 changes:
- FIXED: Save T0 snapshots BEFORE early return on empty Top 5
- Snapshots are the primary Evidence. They MUST be captured
  even when Liquidity/Data-Quality gates reject all candidates.
- scan_id format: YYYY-MM-DD_HHMM (ET)
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
from database.snapshot_schema import init_snapshot_schema, save_snapshot
from telegram_v3 import send_message, format_research_report
from telegram_v3 import format_lesson_for_telegram

from learning.replay_engine import save_candidate_snapshot

from learning.lesson_engine import (
    build_lesson,
    save_learning,
    print_lesson,
    load_previous_learning,
)


# ---------------------------------------------------------------------------
# PM DATA SANITIZATION (V5.0.6-prep.2)
# ---------------------------------------------------------------------------

def _sanitize_pm_fields(candidate):
    """
    Enforce PM evidence atomicity before DB write.

    Rule: PM evidence is all-or-nothing.
      - If we have bars (pm_bars > 0), we derive volume/high/low/vwap
        from those bars, and pm_source must be set.
      - If we have no bars (pm_bars == 0 or missing), we must NOT
        persist partial PM scalars. Set them all to NULL.

    Returns True if any field was changed (for logging).
    """
    changed = False

    raw_bars = candidate.get("pm_bars", 0)
    try:
        pm_bars = int(raw_bars) if raw_bars is not None else 0
    except (TypeError, ValueError):
        pm_bars = 0

    if pm_bars <= 0:
        # No PM bars → no PM evidence. Clear everything.
        if candidate.get("pm_bars") not in (0, None):
            changed = True
        candidate["pm_bars"] = 0

        for field in ("pm_volume", "pm_high", "pm_low", "pm_vwap", "pm_source"):
            if candidate.get(field) is not None:
                changed = True
                candidate[field] = None

        if candidate.get("pm_volume_status") not in (None, "NO_DATA"):
            changed = True
        candidate["pm_volume_status"] = "NO_DATA"

        if candidate.get("pm_data_quality") not in (None, "NO_PM_BARS"):
            changed = True
        candidate["pm_data_quality"] = "NO_PM_BARS"

        if candidate.get("pm_bars_json") not in (None, "", "[]"):
            changed = True
            candidate["pm_bars_json"] = None
    else:
        # Bars exist → ensure source is populated
        if not candidate.get("pm_source"):
            candidate["pm_source"] = "alpaca"
            changed = True
        if not candidate.get("pm_volume_status"):
            candidate["pm_volume_status"] = "OK"
            changed = True

    return changed


# ---------------------------------------------------------------------------
# Swing / trade-type helpers
# ---------------------------------------------------------------------------

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

    reject_float_over_20m = int(stats.get("reject_float_over_20m", 0) or 0)
    float_unknown = int(stats.get("float_unknown", 0) or 0)
    reject_float_legacy = int(stats.get("reject_float", 0) or 0)

    if reject_float_over_20m == 0 and float_unknown == 0 and reject_float_legacy > 0:
        reject_float_over_20m = reject_float_legacy

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
        "reject_float_over_20m": reject_float_over_20m,
        "float_unknown": float_unknown,
        "reject_float": reject_float_over_20m + float_unknown,
        "strict_passed_pre_float": int(stats.get("strict_passed_pre_float", 0) or 0),
        "float_fetches": int(stats.get("float_fetches", 0) or 0),
        "float_yfinance_ok": int(stats.get("float_yfinance_ok", 0) or 0),
        "float_yfinance_none": int(stats.get("float_yfinance_none", 0) or 0),
        "float_fmp_ok": int(stats.get("float_fmp_ok", 0) or 0),
        "float_yfinance_avg_ms": int(stats.get("float_yfinance_avg_ms", 0) or 0),
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
    print("=" * 74)
    print()
    return strict_ok


def run_fullscan_v34(manual=False):
    init_db()
    init_snapshot_schema()
    now_et = datetime.now(ET)
    scan_date = now_et.strftime("%Y-%m-%d")
    scan_id = now_et.strftime("%Y-%m-%d_%H%M")

    # --- PM window detection (matches workflow logic) ---
    now_hhmm = now_et.strftime("%H%M")
    in_pm_window = ("0400" <= now_hhmm < "0930")

    print("\n" + "=" * 74)
    print("DAYS-BOT V5.0.6-prep.2 – RESEARCH ENGINE (Snapshot Schema)")
    print(f"Date: {scan_date} | Scan ID: {scan_id} | Mode: {'MANUAL' if manual else 'LIVE'}")
    print(f"PM window (04:00–09:30 ET): {'IN' if in_pm_window else 'OUT'} | now={now_hhmm}")
    print("=" * 74)

    # ============================================================
    # DISCOVERY
    # ============================================================
    print("[Main] Starting discovery...")
    from scanner.premarket import scan_premarket

    discovery_result = scan_premarket(scan_date, manual)

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
    print(
        f"[Main] Discovery diagnostics: universe={discovery_stats['universe']} | "
        f"snapshots={discovery_stats['snapshots_received']} | "
        f"strict={discovery_stats['strict_candidates']} | "
        f"fallback={discovery_stats['fallback_candidates']} | "
        f"float_over_20m={discovery_stats['reject_float_over_20m']} | "
        f"float_unknown={discovery_stats['float_unknown']}"
    )

    # ============================================================
    # FULL ANALYSIS
    # ============================================================
    print("[Main] Running full analysis on ALL strict candidates...")
    top5 = full_scan_v34(candidates, manual)

    # ============================================================
    # V5.0.6-prep.2 — SAVE T0 SNAPSHOTS (WITH PM SANITIZATION)
    #
    # Snapshots are the primary Evidence. They MUST be captured
    # even when Top 5 is empty (all candidates rejected by
    # Liquidity / Data-Quality gates).
    #
    # Each candidate passes through _sanitize_pm_fields() first so
    # that partial PM data (volume/high without bars) can never
    # reach the DB.
    # ============================================================
    print("[Main] Saving V5.0.6 T0 snapshots for ALL strict candidates...")
    snapshot_saved = 0
    snapshot_failed = 0
    pm_sanitized = 0
    pm_with_bars = 0

    for candidate in candidates:
        try:
            raw_bars = candidate.get("pm_bars", 0) or 0
            try:
                raw_bars = int(raw_bars)
            except (TypeError, ValueError):
                raw_bars = 0

            was_changed = _sanitize_pm_fields(candidate)

            if raw_bars <= 0:
                pm_sanitized += 1
            else:
                pm_with_bars += 1

            if was_changed:
                print(
                    f"[Main] 🧹 PM sanitized: {candidate.get('ticker')} "
                    f"(pm_bars={raw_bars})"
                )

            sid = save_snapshot(candidate, scan_id, now_et)
            if sid is not None:
                snapshot_saved += 1
            else:
                snapshot_failed += 1
        except Exception as e:
            snapshot_failed += 1
            print(f"[Main] ⚠️ Snapshot error {candidate.get('ticker')}: {type(e).__name__}: {e}")

    print(
        f"[Main] V5.0.6 snapshots saved: {snapshot_saved} "
        f"(failed/skipped: {snapshot_failed}) | "
        f"PM with bars: {pm_with_bars} | PM sanitized to NULL: {pm_sanitized}"
    )

    # ============================================================
    # EARLY RETURN — AFTER snapshots are saved
    # ============================================================
    if not top5:
        print("[Main] ❌ Full analysis returned empty.")
        msg = "😴 DAYS-BOT\n\nה-Discovery עבד, אבל לא התקבל מועמד לניתוח מלא."
        send_message(TELEGRAM_TOKEN, TELEGRAM_CHAT_ID, msg)
        return

    print(f"[Main] ✅ Full analysis returned {len(top5)} candidates")

    # ============================================================
    # REPLAY SNAPSHOTS
    # ============================================================
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

    # ============================================================
    # SWING ANALYSIS FOR TOP 5
    # ============================================================
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

    # ============================================================
    # REPLAY INTEGRITY CHECK
    # ============================================================
    strict_count = discovery_stats.get("strict_candidates", 0)
    integrity_ok = _run_replay_integrity_check(replay_saved, strict_count)

    # ============================================================
    # LEARNING
    # ============================================================
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

    # ============================================================
    # TELEGRAM
    # ============================================================
    print("[Main] Sending Telegram...")
    msg = format_research_report(top5, now_et)
    telegram_ok = send_message(TELEGRAM_TOKEN, TELEGRAM_CHAT_ID, msg)
    print(f"[Main] Telegram report sent: {telegram_ok}")

    if lesson.get("observations") or lesson.get("notes"):
        lesson_msg = format_lesson_for_telegram(lesson)
        send_message(TELEGRAM_TOKEN, TELEGRAM_CHAT_ID, lesson_msg)

    # ============================================================
    # FLOW SUMMARY
    # ============================================================
    print()
    print("=" * 74)
    print("DISCOVERY → GATES → TOP 5 FLOW")
    print("=" * 74)
    print(f"  Universe:                  {discovery_stats['universe']}")
    print(f"  Valid snapshots:           {discovery_stats['snapshots_received']}")
    print(f"  Strict candidates:         {discovery_stats['strict_candidates']}")
    print(f"  Analyzed (FullScan):       {len(candidates)}")
    print(f"  In Top 5:                  {len(top5)}")
    print(f"  V5.0.6 Snapshots saved:    {snapshot_saved}")
    print(f"  PM with bars / sanitized:  {pm_with_bars} / {pm_sanitized}")
    print("=" * 74)

    # ============================================================
    # TOP 5 SUMMARY
    # ============================================================
    print()
    print("=" * 74)
    print("TOP 5")
    print("=" * 74)
    for i, c in enumerate(top5, 1):
        pm_status = c.get('pm_volume_status', 'UNKNOWN')
        print(
            f"{i}. {c.get('ticker')} | "
            f"Intraday={float(c.get('composite_score', 0) or 0):.1f} | "
            f"Early={float(c.get('early_score', 0) or 0):.1f} | "
            f"Swing={float(c.get('swing_score', 0) or 0):.1f} | "
            f"PMVol={pm_status} | "
            f"Type={c.get('trade_type', 'WATCH')} | "
            f"Data={c.get('data_status', 'UNKNOWN')}"
        )
    print("=" * 74)

    # ============================================================
    # REPLAY SUMMARY
    # ============================================================
    print()
    print("=" * 74)
    print("REPLAY SUMMARY")
    print("=" * 74)
    print(f"Universe:             {discovery_stats['universe']}")
    print(f"Valid snapshots:      {discovery_stats['snapshots_received']}")
    print(f"Strict candidates:    {strict_count}")
    print(f"Replay records:       {replay_saved}")
    print(f"V5.0.6 snapshots:     {snapshot_saved}")
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