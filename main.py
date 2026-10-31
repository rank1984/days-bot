#!/usr/bin/env python3
"""
DAYS-BOT V5.0.8 - Main Entry Point
Fixed: DB Initialization (init_snapshot_schema) + save_snapshot arguments + Top 3 Telegram Alerts
Added: Dip Filter (Price 10-50, Gap < -2%, ATR > 3%)
"""
import sys
import os
import argparse
import uuid
from datetime import datetime
import pytz

# ==============================================================================
# IMPORTS
# ==============================================================================

# 1. Universe Loader
try:
    from scanner.universe import load_universe
except ImportError:
    try:
        from scanner.universe import get_universe as load_universe
    except ImportError:
        print("[WARN] load_universe not found. Will pass empty list.")
        def load_universe(): return []

# 2. Discovery Engine
from scanner.swing_discovery import run_swing_discovery

# 3. Database (Defensive)
try:
    from database.snapshot_schema import save_snapshot
except ImportError:
    def save_snapshot(cand, scan_id, now_et):
        print(f"[WARN] save_snapshot not found. Skipping DB save for {cand.get('ticker')}")

# --- התיקון הקריטי: טעינת init_snapshot_schema ---
try:
    from database.snapshot_schema import init_snapshot_schema as init_db
except ImportError:
    try:
        from database.db import init_db
    except ImportError:
        try:
            from database.snapshot_schema import init_db
        except ImportError:
            def init_db(): pass

# 4. Config & Telegram
try:
    from utils.config import TELEGRAM_TOKEN, TELEGRAM_CHAT_ID
except ImportError:
    TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN", "")
    TELEGRAM_CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID", "")

try:
    from telegram_v3 import send_message, format_swing_alert, format_swing_summary
except ImportError:
    print("[WARN] telegram_v3 not found. Alerts will not be sent.")
    def send_message(t, c, m): return False
    def format_swing_alert(a): return ""
    def format_swing_summary(c, v, b, s): return ""

# Optional: Calculate score
try:
    from scanner.swing_engine import calculate_swing_score
except ImportError:
    def calculate_swing_score(cand):
        return 0

ET = pytz.timezone("America/New_York")

# ==============================================================================
# HELPERS (Safe extraction for Dict/List/Int)
# ==============================================================================
def _extract_candidates(result):
    if isinstance(result, list):
        return result
    if isinstance(result, tuple):
        for item in result:
            if isinstance(item, list):
                return item
    if isinstance(result, dict):
        for key in ['candidates', 'results', 'snapshots', 'data']:
            if key in result and isinstance(result[key], list):
                return result[key]
    return []

def _safe_score(val):
    if isinstance(val, (int, float)):
        return float(val)
    if isinstance(val, dict):
        for k in ['score', 'swing_score', 'total', 'composite_score']:
            if k in val and isinstance(val[k], (int, float)):
                return float(val[k])
        return 0.0
    if isinstance(val, str):
        try:
            return float(val)
        except ValueError:
            return 0.0
    return 0.0

# ==============================================================================
# NEW: DIP FILTER (The Winning Strategy)
# ==============================================================================
def _passes_dip_filter(candidate: dict) -> bool:
    """
    פילטר ה-Dip המנצח: 
    קונה רק מניות Mid-Cap (10-50$) שקרסו בפתיחה (Gap < -2%) עם תנודתיות גבוהה (ATR > 3%).
    """
    try:
        price = float(candidate.get('price') or candidate.get('entry') or 0)
        gap = float(candidate.get('gap_pct') or 0)
        atr = float(candidate.get('atr') or 0)

        # תנאי 1: מחיר בין 10 ל-50 דולר
        if not (10 <= price <= 50):
            return False

        # תנאי 2: גאפ שלילי חד (מתחת ל-2%)
        if gap >= -2.0:
            return False

        # תנאי 3: ATR גבוה מ-3% (תנודתיות)
        if price > 0 and (atr / price) > 0.03:
            return True

        return False
    except Exception:
        return False

# ==============================================================================
# TRADE PLAN BUILDER
# ==============================================================================
def _build_swing_plan(ticker, price, atr, score, candidate_data):
    MIN_STOP_PCT = 2.0
    MAX_STOP_PCT = 10.0

    if not atr or atr <= 0:
        atr = price * 0.03 

    stop = min(price - (1.5 * atr), price * (1 - (MIN_STOP_PCT / 100.0)))
    stop_distance_pct = ((price - stop) / price) * 100

    if stop_distance_pct > MAX_STOP_PCT:
        return {"plan_valid": False, "plan_error": f"STOP_TOO_WIDE ({stop_distance_pct:.2f}% > {MAX_STOP_PCT}%)"}
    if stop_distance_pct < MIN_STOP_PCT:
        return {"plan_valid": False, "plan_error": f"STOP_TOO_TIGHT ({stop_distance_pct:.2f}% < {MIN_STOP_PCT}%)"}

    risk_per_share = price - stop
    target_1 = price + (risk_per_share * 2)
    target_2 = price + (risk_per_share * 4)

    account_size = 5000.0
    risk_pct = 0.005 
    max_loss = account_size * risk_pct
    position_size = int(max_loss / risk_per_share) if risk_per_share > 0 else 0

    return {
        "plan_valid": True,
        "plan_error": None,
        "entry": round(price, 2),
        "stop": round(stop, 2),
        "target_1": round(target_1, 2),
        "target_2": round(target_2, 2),
        "risk_per_share": round(risk_per_share, 2),
        "position_size": position_size,
        "max_loss": round(max_loss, 2),
        "hold_type": "SWING_1_3D"
    }

# ==============================================================================
# MAIN ENGINE
# ==============================================================================
def run_swing_v1(manual=False):
    now_et = datetime.now(ET)
    scan_id = str(uuid.uuid4())

    print("==========================================================================")
    print("DAYS-BOT - SWING ENGINE (Daily Bars) V5.0.8")
    print(f"Date: {now_et.strftime('%Y-%m-%d')} | Mode: {'MANUAL' if manual else 'AUTO'}")
    print(f"Scan ID: {scan_id}")
    print("Stop range: 2.0%-10.0% | Min Score: 60")
    print("Filter: DIP ONLY (Price 10-50, Gap < -2%, ATR > 3%)")
    print("==========================================================================")

    # 1. Initialize DB - Force creation if missing
    try:
        os.makedirs("data", exist_ok=True)
        print(f"[Main] Initializing DB at data/alerts.db...")
        init_db()
        print("[Main] DB initialized successfully.")
    except Exception as e:
        print(f"[FATAL] Could not init DB: {e}")
        return

    # 2. Build Universe
    print("[Main] Building clean dynamic universe...")
    try:
        universe = load_universe()
        print(f"[Main] Universe ready: {len(universe)} symbols")
    except Exception as e:
        print(f"[FATAL] Could not build universe: {e}")
        return

    # 3. Discovery
    print(f"[Main] Starting Swing Discovery on {len(universe)} symbols...")
    try:
        raw_result = run_swing_discovery(universe)
        candidates = _extract_candidates(raw_result)
    except Exception as e:
        print(f"[FATAL] Discovery failed: {e}")
        return

    if not candidates:
        print("[Main] No candidates found. Exiting.")
        return

    print(f"[Main] Analyzing {len(candidates)} swing candidates...")

    # 4. Analyze and Save
    snapshots_saved = 0
    valid_alerts = 0
    plan_blocked = 0
    dip_filter_blocked = 0
    blocked_reasons = {"STOP_TOO_WIDE": 0, "STOP_TOO_TIGHT": 0, "LOW_SCORE": 0}

    all_valid_plans = []

    for cand in candidates:
        if not isinstance(cand, dict):
            continue

        ticker = cand.get('ticker', 'UNKNOWN')
        price = float(cand.get('price', 0) or 0)
        atr = float(cand.get('atr', 0) or 0)

        # Safely calculate score
        raw_score = cand.get('score') or cand.get('swing_score') or cand.get('composite_score')
        score = _safe_score(raw_score)
        if score == 0.0:
            raw_calc = calculate_swing_score(cand)
            score = _safe_score(raw_calc)

        cand['score'] = score
        cand['composite_score'] = score

        # =====================================================================
        # APPLY DIP FILTER HERE (Before Plan Building & DB Save)
        # =====================================================================
        if not _passes_dip_filter(cand):
            dip_filter_blocked += 1
            continue # Skip this candidate completely
        # =====================================================================

        # Build Plan
        plan = _build_swing_plan(ticker, price, atr, score, cand)
        cand.update(plan)

        if score < 60:
            cand['plan_valid'] = False
            cand['plan_error'] = "LOW_SCORE"

        if cand.get('plan_valid'):
            valid_alerts += 1
            all_valid_plans.append(cand)
            print(f"[SwingScan] ✅ {ticker} | Score: {score} | Entry: ${cand['entry']} | Stop: ${cand['stop']} | T1: ${cand['target_1']}")
        else:
            plan_blocked += 1
            err = cand.get('plan_error', 'UNKNOWN')
            if "WIDE" in err: blocked_reasons["STOP_TOO_WIDE"] += 1
            elif "TIGHT" in err: blocked_reasons["STOP_TOO_TIGHT"] += 1
            elif "SCORE" in err: blocked_reasons["LOW_SCORE"] += 1
            print(f"[SwingScan] ⚠️ {ticker} | Score: {score} | BLOCKED: {err}")

        # SAVE TO DB (Fixed)
        try:
            snap_id = save_snapshot(cand, scan_id, now_et)
            if snap_id:
                snapshots_saved += 1
            else:
                print(f"[WARN] Failed to save snapshot for {ticker} (returned None)")
        except Exception as e:
            print(f"[WARN] Exception while saving snapshot for {ticker}: {e}")

    print(f"\n[Main] V5.0.8 snapshots saved: {snapshots_saved}")
    print(f"[Main] Candidates filtered out by Dip Filter: {dip_filter_blocked}\n")

    # 5. Send Telegram Alerts (Top 3)
    print("[Main] Selecting Top 3 Alerts to Telegram (score >= 95)...")

    top_alerts = [a for a in all_valid_plans if a.get('score', 0) >= 95]

    top_alerts.sort(
        key=lambda x: (
            x.get('score', 0), 
            _safe_score(x.get('rvol', 0)), 
            _safe_score(x.get('atr', 0))
        ), 
        reverse=True
    )

    top_alerts = top_alerts[:3]

    telegram_sent = 0
    if TELEGRAM_TOKEN and TELEGRAM_CHAT_ID:
        for alert in top_alerts:
            msg = format_swing_alert(alert)
            if not msg: continue
            success = send_message(TELEGRAM_TOKEN, TELEGRAM_CHAT_ID, msg)
            if success:
                print(f"[Main]   → {alert['ticker']} (score {alert['score']}) - sent")
                telegram_sent += 1

        if telegram_sent > 0:
            summary_msg = format_swing_summary(
                candidates_count=len(candidates),
                valid_alerts=valid_alerts,
                blocked=plan_blocked,
                telegram_sent=telegram_sent
            )
            if summary_msg:
                send_message(TELEGRAM_TOKEN, TELEGRAM_CHAT_ID, summary_msg)
                print("[Main]   → Summary sent")
    else:
        print("[Main] No Telegram credentials found. Skipping alerts.")

    # 6. Final Summary
    print("\n==========================================================================")
    print("SWING SUMMARY:")
    print(f"  Candidates analyzed:    {len(candidates)}")
    print(f"  Dip Filter blocked:     {dip_filter_blocked}")
    print(f"  Snapshots saved:        {snapshots_saved}")
    print(f"  Valid alerts (saved):   {valid_alerts}")
    print(f"  Plan blocked:           {plan_blocked}")
    print(f"    - Stop too tight:     {blocked_reasons['STOP_TOO_TIGHT']}")
    print(f"    - Stop too wide:      {blocked_reasons['STOP_TOO_WIDE']}")
    print(f"    - Other (low score):  {blocked_reasons['LOW_SCORE']}")
    print(f"  Telegram sent:          {telegram_sent}")
    print("==========================================================================")

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("command", nargs="?", default="swing_v1")
    parser.add_argument("--manual", action="store_true")
    args = parser.parse_args()

    if args.command == "swing_v1":
        run_swing_v1(manual=args.manual)
    else:
        print(f"Unknown command: {args.command}")