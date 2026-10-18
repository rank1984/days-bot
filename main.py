"""
DAYS-BOT V5.0.7 – RESEARCH ENGINE (Multi-Strategy)
תומך בשני מנועים:
1. fullscan_v34 - מנוע Pre-Market (Gap and Go) - היסטורי
2. swing_v1 - מנוע Swing יומי (Daily Bars) - חדש
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
# PM DATA SANITIZATION (V5.0.6-prep.2) - נשאר לצורך תאימות לאחור
# ---------------------------------------------------------------------------

def _sanitize_pm_fields(candidate):
    changed = False
    raw_bars = candidate.get("pm_bars", 0)
    try:
        pm_bars = int(raw_bars) if raw_bars is not None else 0
    except (TypeError, ValueError):
        pm_bars = 0

    if pm_bars <= 0:
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
            print(f"[Main] Swing returned {type(result).__name__} for {candidate.get('ticker')}")
            return {"swing_score": 0, "swing_type": "INVALID", "qualified": False}
        return result
    except Exception as e:
        print(f"[Main] Swing error {candidate.get('ticker')}: {type(e).__name__}: {e}")
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

# ---------------------------------------------------------------------------
# Legacy Normalization (for fullscan_v34)
# ---------------------------------------------------------------------------

def _normalize_discovery_stats(stats):
    if not isinstance(stats, dict):
        stats = {}
    universe_value = stats.get("universe", stats.get("requested_symbols", 0)) or 500
    reject_float_over_20m = int(stats.get("reject_float_over_20m", 0) or 0)
    float_unknown = int(stats.get("float_unknown", 0) or 0)
    reject_float_legacy = int(stats.get("reject_float", 0) or 0)
    if reject_float_over_20m == 0 and float_unknown == 0 and reject_float_legacy > 0:
        reject_float_over_20m = reject_float_legacy

    return {
        "universe": int(universe_value),
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

# ---------------------------------------------------------------------------
# ENGINE 1: Pre-Market Full Scan (Legacy)
# ---------------------------------------------------------------------------

def run_fullscan_v34(manual=False):
    init_db()
    init_snapshot_schema()
    now_et = datetime.now(ET)
    scan_date = now_et.strftime("%Y-%m-%d")
    scan_id = now_et.strftime("%Y-%m-%d_%H%M")

    now_hhmm = now_et.strftime("%H%M")
    in_pm_window = ("0400" <= now_hhmm < "0930")

    print("\n" + "=" * 74)
    print("DAYS-BOT - RESEARCH ENGINE (Pre-Market)")
    print(f"Date: {scan_date} | Scan ID: {scan_id} | Mode: {'MANUAL' if manual else 'LIVE'}")
    print(f"PM window (04:00-09:30 ET): {'IN' if in_pm_window else 'OUT'} | now={now_hhmm}")
    print("=" * 74)

    from scanner.premarket import scan_premarket
    discovery_result = scan_premarket(scan_date, manual)
    
    if isinstance(discovery_result, tuple) and len(discovery_result) >= 2:
        candidates, discovery_stats = discovery_result
    else:
        candidates, discovery_stats = discovery_result, {}

    discovery_stats = _normalize_discovery_stats(discovery_stats)

    if not candidates:
        print("[Main] No candidates found by discovery.")
        return

    print(f"[Main] Running full analysis on {len(candidates)} candidates...")
    top5 = full_scan_v34(candidates, manual)

    print("[Main] Saving T0 snapshots...")
    for candidate in candidates:
        _sanitize_pm_fields(candidate)
        save_snapshot(candidate, scan_id, now_et)

    if not top5:
        print("[Main] Full analysis returned empty.")
        return

    for candidate in top5:
        analysis = candidate.get('analysis', {})
        swing = _safe_swing(candidate, analysis)
        candidate["swing_score"] = float(swing.get("swing_score", 0) or 0)
        candidate["trade_type"] = _classify_trade_type(candidate)
        try:
            save_alert(**candidate)
        except Exception as e:
            print(f"[Main] DB save error {candidate.get('ticker')}: {e}")

    print(f"[Main] Top 5 processed: {len(top5)}")

# ---------------------------------------------------------------------------
# ENGINE 2: Swing Daily Scan (New)
# ---------------------------------------------------------------------------

def run_swing_v1(manual=False):
    from scanner.swing_discovery import run_swing_discovery
    from scanner.universe import load_universe
    from risk.trade_plan_v34 import build_trade_plan
    from utils.config import ACCOUNT_SIZE, MAX_RISK_PER_TRADE_V31, MAX_POSITION_VALUE_PCT

    init_db()
    init_snapshot_schema()
    now_et = datetime.now(ET)
    scan_date = now_et.strftime("%Y-%m-%d")
    scan_id = now_et.strftime("%Y-%m-%d_SWING")

    print("\n" + "=" * 74)
    print("DAYS-BOT - SWING ENGINE (Daily Bars)")
    print(f"Date: {scan_date} | Mode: {'MANUAL' if manual else 'LIVE'}")
    print("=" * 74)

    universe = load_universe()
    if not universe:
        print("[Main] Universe is empty. Aborting.")
        return
    
    # ניקח את 500 המניות הראשונות
    tickers = universe[:500] if isinstance(universe, list) else list(universe)[:500]
    
    print(f"[Main] Starting Swing Discovery on {len(tickers)} symbols...")
    candidates, stats = run_swing_discovery(tickers)

    if not candidates:
        print("[Main] No swing candidates found today.")
        return

    print(f"[Main] Analyzing {len(candidates)} swing candidates...")
    
    # נמיין לפי נפח מסחר כדי לתת עדיפות לנזילות
    candidates.sort(key=lambda x: x.get('avg_volume', 0), reverse=True)

    saved_alerts = 0
    for c in candidates:
        ticker = c['ticker']
        
        # 1. חישוב ציון Swing
        swing = _safe_swing(c)
        c['swing_score'] = float(swing.get('swing_score', 0) or 0)
        c['composite_score'] = c['swing_score'] # ציון ראשי הוא ה-Swing
        
        # 2. בניית תוכנית מסחר
        plan = build_trade_plan(c, ACCOUNT_SIZE, MAX_RISK_PER_TRADE_V31, MAX_POSITION_VALUE_PCT)
        if plan:
            c.update(plan)
        
        # 3. שמירת Snapshot (תמיד נשמור, גם אם אין תוכנית)
        _sanitize_pm_fields(c) # מנקה שאריות של PM
        save_snapshot(c, scan_id, now_et)

        # 4. שמירת Alert אם התוכנית תקינה
        if c.get('plan_valid') and c.get('swing_score', 0) >= 60:
            c['data_status'] = "ACTIONABLE"
            c['trade_type'] = "SWING_1_3D"
            try:
                save_alert(**c)
                saved_alerts += 1
                print(f"[SwingScan] ✅ {ticker} | Score: {c['swing_score']:.1f} | Entry: ${c.get('entry', 0):.2f} | Stop: ${c.get('stop', 0):.2f}")
            except Exception as e:
                print(f"[SwingScan] DB error {ticker}: {e}")
        else:
            print(f"[SwingScan] ⚠️ {ticker} | Score: {c['swing_score']:.1f} | Plan blocked or score too low")

    print("\n" + "=" * 74)
    print(f"SWING SUMMARY: Found {saved_alerts} valid swing setups out of {len(candidates)} candidates.")
    print("=" * 74)

    if saved_alerts > 0:
        try:
            msg = f"DAYS-BOT Swing Alert: Found {saved_alerts} setups for {scan_date}."
            send_message(TELEGRAM_TOKEN, TELEGRAM_CHAT_ID, msg)
        except Exception:
            pass

# ---------------------------------------------------------------------------
# MAIN ENTRY POINT
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python main.py [fullscan_v34|swing_v1] [--manual]")
        sys.exit(1)
    
    command = sys.argv[1]
    manual = "--manual" in sys.argv
    
    if command == "fullscan_v34":
        run_fullscan_v34(manual)
    elif command == "swing_v1":
        run_swing_v1(manual)
    else:
        print(f"Unknown command: {command}")
        sys.exit(1)
