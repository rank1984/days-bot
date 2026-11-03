#!/usr/bin/env python3
"""
DAYS-BOT V5.0.9 - Main Entry Point (Final)
- Macro freshness check (max 60 min old)
- Position value limit (max 20% of account)
- Safe float conversion
- Separate counters: valid_plans vs alerts_candidates
"""
import sys
import os
import argparse
import uuid
import sqlite3
from datetime import datetime, timedelta
import pytz

# ==============================================================================
# IMPORTS
# ==============================================================================

try:
    from scanner.universe import load_universe
except ImportError:
    try:
        from scanner.universe import get_universe as load_universe
    except ImportError:
        print("[WARN] load_universe not found. Will pass empty list.")
        def load_universe(): return []

from scanner.swing_discovery import run_swing_discovery

try:
    from database.snapshot_schema import save_snapshot
except ImportError:
    def save_snapshot(cand, scan_id, now_et):
        print(f"[WARN] save_snapshot not found. Skipping DB save for {cand.get('ticker')}")

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

try:
    from scanner.swing_engine import calculate_swing_score
except ImportError:
    def calculate_swing_score(cand):
        return 0

ET = pytz.timezone("America/New_York")
DB_PATH = os.environ.get("DB_PATH", "data/alerts.db")
MAX_MACRO_AGE_MINUTES = 600

# ==============================================================================
# HELPERS
# ==============================================================================
def _safe_float(val, default=0.0):
    try:
        if val is None: return default
        if isinstance(val, bool): return float(val)
        if isinstance(val, (int, float)): return float(val)
        return float(str(val).strip())
    except (ValueError, TypeError):
        return default

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

def _extract_candidates(result):
    if isinstance(result, list): return result
    if isinstance(result, tuple):
        for item in result:
            if isinstance(item, list): return item
    if isinstance(result, dict):
        for key in ['candidates', 'results', 'snapshots', 'data']:
            if key in result and isinstance(result[key], list): return result[key]
    return []

# ==============================================================================
# MACRO FILTER (with freshness check)
# ==============================================================================
def check_macro_from_db():
    """
    קורא את מצב המאקרו מה-DB.
    Fail-Closed: אם הרשומה לא מהיום, לא טרייה, או לא BULLISH - לא סוחרים.
    """
    print(f"[Macro] Reading market regime from {DB_PATH}...")
    if not os.path.exists(DB_PATH):
        print("[Macro] ERROR: DB not found. Defaulting to SAFE.")
        return False, "NO_DB", ""

    try:
        conn = sqlite3.connect(DB_PATH)
        cur = conn.cursor()

        cur.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='macro_state'")
        if not cur.fetchone():
            print("[Macro] ERROR: macro_state table not found. Defaulting to SAFE.")
            conn.close()
            return False, "NO_TABLE", ""

        today = datetime.now(ET).strftime("%Y-%m-%d")
        row = cur.execute("""
            SELECT status, checked_at FROM macro_state
            WHERE scan_date = ?
        """, (today,)).fetchone()
        conn.close()

        if not row:
            print(f"[Macro] ERROR: No macro data for {today}. Defaulting to SAFE.")
            return False, "MISSING_TODAY", ""

        status, checked_at_str = row
        
        # --- בדיקת טריות ---
        try:
            checked_at = datetime.fromisoformat(checked_at_str)
            age_minutes = (datetime.now(ET) - checked_at).total_seconds() / 60
            
            if age_minutes > MAX_MACRO_AGE_MINUTES:
                print(f"[Macro] ERROR: Macro data is {age_minutes:.0f} min old (max {MAX_MACRO_AGE_MINUTES}). Defaulting to SAFE.")
                return False, "STALE_DATA", checked_at_str
            
            if age_minutes < 0:
                print(f"[Macro] WARNING: checked_at is in the future ({age_minutes:.0f} min). Treating as STALE.")
                return False, "FUTURE_DATA", checked_at_str
        except Exception as e:
            print(f"[Macro] ERROR parsing checked_at: {e}. Defaulting to SAFE.")
            return False, "BAD_TIMESTAMP", checked_at_str

        is_bullish = (status == "BULLISH")
        print(f"[Macro] Status: {status} | Age: {age_minutes:.0f} min | Checked at: {checked_at_str}")
        return is_bullish, status, checked_at_str

    except Exception as e:
        print(f"[Macro] ERROR: {e}. Defaulting to SAFE.")
        return False, "ERROR", ""

# ==============================================================================
# DIP FILTER (with detailed counters)
# ==============================================================================
def _check_dip_filter(candidate: dict) -> tuple:
    """
    מחזיר (passed: bool, reason: str)
    """
    price = _safe_float(candidate.get('price') or candidate.get('entry'))
    gap = _safe_float(candidate.get('gap_pct'))
    atr = _safe_float(candidate.get('atr'))

    if price <= 0:
        return False, "no_price"
    if not (10 <= price <= 50):
        return False, "price_out_of_range"
    if gap >= -2.0:
        return False, "gap_too_small"
    if price > 0 and (atr / price) <= 0.03:
        return False, "atr_too_low"
    return True, "ok"

# ==============================================================================
# TRADE PLAN BUILDER (with position value limit)
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

    # --- Position sizing with value limit ---
    account_size = 5000.0
    risk_pct = 0.005 
    max_loss = account_size * risk_pct
    max_position_value = account_size * 0.20  # 20% of account

    size_by_risk = int(max_loss / risk_per_share) if risk_per_share > 0 else 0
    size_by_value = int(max_position_value / price) if price > 0 else 0
    position_size = min(size_by_risk, size_by_value)

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
        "position_value": round(position_size * price, 2),
        "hold_type": "SWING_1_3D"
    }

# ==============================================================================
# MAIN ENGINE
# ==============================================================================
def run_swing_v1(manual=False):
    now_et = datetime.now(ET)
    scan_id = str(uuid.uuid4())

    print("==========================================================================")
    print("DAYS-BOT - SWING ENGINE (Daily Bars) V5.0.9 FINAL")
    print(f"Date: {now_et.strftime('%Y-%m-%d %H:%M:%S')} ET | Mode: {'MANUAL' if manual else 'AUTO'}")
    print(f"Scan ID: {scan_id}")
    print("Filters: DIP (10-50$, Gap<-2%, ATR>3%) + MACRO (DB, max 60 min old)")
    print("Telegram: max 3 alerts, score >= 80")
    print("==========================================================================")

    # 1. MACRO CHECK
    is_bullish, status_str, checked_at = check_macro_from_db()
    
    if not is_bullish:
        print(f"\n⚠️ MACRO FILTER: Market is {status_str}. Skipping scan.")
        print("==========================================================================")
        return

    print(f"[Macro] ✅ Market is BULLISH. Proceeding with scan.")

    # 2. INIT DB
    try:
        os.makedirs("data", exist_ok=True)
        print(f"[Main] Initializing DB at {DB_PATH}...")
        init_db()
        print("[Main] DB initialized successfully.")
    except Exception as e:
        print(f"[FATAL] Could not init DB: {e}")
        return

    # 3. UNIVERSE
    print("[Main] Building clean dynamic universe...")
    try:
        universe = load_universe()
        print(f"[Main] Universe ready: {len(universe)} symbols")
    except Exception as e:
        print(f"[FATAL] Could not build universe: {e}")
        return

    # 4. DISCOVERY
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

    # 5. ANALYZE
    snapshots_saved = 0
    valid_plans = 0           # plan is valid (entry/stop/targets ok)
    alerts_candidates = 0     # score >= 80 (would go to telegram)
    dip_filter_blocked = 0
    dip_filter_reasons = {}
    plan_blocked_reasons = {"STOP_TOO_WIDE": 0, "STOP_TOO_TIGHT": 0, "LOW_SCORE": 0}

    all_valid_plans = []

    for cand in candidates:
        if not isinstance(cand, dict):
            continue

        ticker = cand.get('ticker', 'UNKNOWN')
        price = _safe_float(cand.get('price'))
        atr = _safe_float(cand.get('atr'))

        # Score
        raw_score = cand.get('score') or cand.get('swing_score') or cand.get('composite_score')
        score = _safe_score(raw_score)
        if score == 0.0:
            score = _safe_score(calculate_swing_score(cand))
        cand['score'] = score
        cand['composite_score'] = score

        # DIP FILTER (with reason tracking)
        passed, reason = _check_dip_filter(cand)
        if not passed:
            dip_filter_blocked += 1
            dip_filter_reasons[reason] = dip_filter_reasons.get(reason, 0) + 1
            continue

        # Build Plan
        plan = _build_swing_plan(ticker, price, atr, score, cand)
        cand.update(plan)

        if score < 60:
            cand['plan_valid'] = False
            cand['plan_error'] = "LOW_SCORE"

        if cand.get('plan_valid'):
            valid_plans += 1
            all_valid_plans.append(cand)
            if score >= 80:
                alerts_candidates += 1
            print(f"[SwingScan] ✅ {ticker} | Score: {score} | Entry: ${cand['entry']} | Stop: ${cand['stop']} | T1: ${cand['target_1']} | Size: {cand['position_size']} (${cand['position_value']})")
        else:
            err = cand.get('plan_error', 'UNKNOWN')
            if "WIDE" in err: plan_blocked_reasons["STOP_TOO_WIDE"] += 1
            elif "TIGHT" in err: plan_blocked_reasons["STOP_TOO_TIGHT"] += 1
            elif "SCORE" in err: plan_blocked_reasons["LOW_SCORE"] += 1
            print(f"[SwingScan] ⚠️ {ticker} | Score: {score} | BLOCKED: {err}")

        # Save to DB
        try:
            snap_id = save_snapshot(cand, scan_id, now_et)
            if snap_id:
                snapshots_saved += 1
        except Exception as e:
            print(f"[WARN] Exception saving {ticker}: {e}")

    print(f"\n[Main] Snapshots saved: {snapshots_saved}")
    print(f"[Main] Valid plans: {valid_plans}")
    print(f"[Main] Alerts candidates (score >= 80): {alerts_candidates}")
    print(f"[Main] Dip Filter blocked: {dip_filter_blocked}")
    if dip_filter_reasons:
        for r, c in sorted(dip_filter_reasons.items(), key=lambda x: -x[1]):
            print(f"   - {r}: {c}")

    # 6. SEND TELEGRAM
    print("\n[Main] Selecting Top 3 Alerts to Telegram...")
    top_alerts = [a for a in all_valid_plans if a.get('score', 0) >= 80]
    top_alerts.sort(key=lambda x: (x.get('score', 0), _safe_score(x.get('rvol', 0)), _safe_score(x.get('atr', 0))), reverse=True)
    top_alerts = top_alerts[:3]

    telegram_sent = 0
    telegram_failed = 0
    if TELEGRAM_TOKEN and TELEGRAM_CHAT_ID:
        for alert in top_alerts:
            msg = format_swing_alert(alert)
            if not msg:
                continue
            success = send_message(TELEGRAM_TOKEN, TELEGRAM_CHAT_ID, msg)
            if success:
                print(f"[Main]   → {alert['ticker']} (score {alert['score']}) - sent")
                telegram_sent += 1
            else:
                print(f"[Main]   → {alert['ticker']} (score {alert['score']}) - FAILED")
                telegram_failed += 1

        if telegram_sent > 0:
            summary_msg = format_swing_summary(
                candidates_count=len(candidates),
                valid_alerts=valid_plans,
                blocked=sum(plan_blocked_reasons.values()),
                telegram_sent=telegram_sent
            )
            if summary_msg:
                send_message(TELEGRAM_TOKEN, TELEGRAM_CHAT_ID, summary_msg)
                print("[Main]   → Summary sent")
    else:
        print("[Main] No Telegram credentials found. Skipping alerts.")

    # 7. FINAL SUMMARY
    print("\n==========================================================================")
    print("SWING SUMMARY:")
    print(f"  Macro Status:              BULLISH ✅ (Age OK)")
    print(f"  Candidates analyzed:       {len(candidates)}")
    print(f"  Dip Filter blocked:        {dip_filter_blocked}")
    for r, c in sorted(dip_filter_reasons.items(), key=lambda x: -x[1]):
        print(f"    - {r}: {c}")
    print(f"  Snapshots saved:           {snapshots_saved}")
    print(f"  Valid plans:               {valid_plans}")
    print(f"  Alerts candidates (>=80):  {alerts_candidates}")
    print(f"  Plan blocked:")
    for r, c in plan_blocked_reasons.items():
        if c > 0: print(f"    - {r}: {c}")
    print(f"  Telegram sent:             {telegram_sent}")
    print(f"  Telegram failed:           {telegram_failed}")
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