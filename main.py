#!/usr/bin/env python3
"""
DAYS-BOT V5.0.8 - Main Entry Point
Fully defensive imports to prevent any ImportError crash.
"""
import sys
import os
import json
import argparse
from datetime import datetime
import pytz

# ==============================================================================
# DEFENSIVE IMPORTS (Won't crash if a specific function is missing)
# ==============================================================================

# 1. Database imports
try:
    from database.snapshot_schema import save_snapshot
except ImportError:
    def save_snapshot(cand):
        pass # Fallback if missing

try:
    from database.db import init_db
except ImportError:
    try:
        from database.snapshot_schema import init_db
    except ImportError:
        def init_db():
            pass # Fallback if missing

# 2. Config imports
try:
    from utils.config import TELEGRAM_TOKEN, TELEGRAM_CHAT_ID
except ImportError:
    TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN", "")
    TELEGRAM_CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID", "")

# 3. Telegram imports
try:
    from telegram_v3 import send_message, format_swing_alert, format_swing_summary
except ImportError:
    print("[WARN] telegram_v3 not found or incomplete. Alerts will not be sent.")
    def send_message(t, c, m): return False
    def format_swing_alert(a): return ""
    def format_swing_summary(c, v, b, s): return ""

# 4. Discovery imports (Dynamic mapping)
import scanner.swing_discovery as sd

def get_discovery_run():
    """Dynamically finds the run function or class in swing_discovery.py"""
    # Try specific class names first
    for name in ['SwingDiscovery', 'DiscoveryEngine', 'Discovery']:
        if hasattr(sd, name):
            obj = getattr(sd, name)
            if isinstance(obj, type):
                inst = obj()
                if hasattr(inst, 'run'): return inst.run
                if hasattr(inst, 'scan'): return inst.scan
    
    # Try module-level functions
    for name in ['run_discovery', 'run', 'scan', 'discover']:
        if hasattr(sd, name) and callable(getattr(sd, name)):
            return getattr(sd, name)
            
    # Fallback: scan dir for anything callable
    for name in dir(sd):
        obj = getattr(sd, name)
        if isinstance(obj, type) and hasattr(obj, 'run'):
            return obj().run
            
    raise RuntimeError("Could not find a valid entry point in scanner.swing_discovery")

try:
    from scanner.swing_engine import calculate_swing_score
except ImportError:
    def calculate_swing_score(cand):
        return cand.get('swing_score', cand.get('composite_score', 0))

ET = pytz.timezone("America/New_York")

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
    print("==========================================================================")
    print("DAYS-BOT - SWING ENGINE (Daily Bars) V5.0.8")
    print(f"Date: {now_et.strftime('%Y-%m-%d')} | Mode: {'MANUAL' if manual else 'AUTO'}")
    print("Stop range: 2.0%-10.0% | Min Score: 60")
    print("Telegram: max 3 alerts, score >= 95")
    print("==========================================================================")
    
    # 1. Initialize DB
    try:
        init_db()
    except Exception as e:
        print(f"[WARN] init_db failed or skipped: {e}")
    
    # 2. Discovery
    print("[Main] Starting Swing Discovery on 500 symbols...")
    try:
        discovery_run_func = get_discovery_run()
        candidates = discovery_run_func()
    except Exception as e:
        print(f"[FATAL] Discovery failed: {e}")
        return

    if not candidates:
        print("[Main] No candidates found. Exiting.")
        return
        
    print(f"[Main] Analyzing {len(candidates)} swing candidates...")
    
    # 3. Analyze and Save
    snapshots_saved = 0
    valid_alerts = 0
    plan_blocked = 0
    blocked_reasons = {"STOP_TOO_WIDE": 0, "STOP_TOO_TIGHT": 0, "LOW_SCORE": 0}
    
    all_valid_plans = []
    
    for cand in candidates:
        ticker = cand.get('ticker', 'UNKNOWN')
        price = cand.get('price', 0)
        atr = cand.get('atr', 0)
        
        # Calculate Score
        try:
            score = calculate_swing_score(cand)
        except Exception:
            score = cand.get('swing_score', cand.get('composite_score', 0))
            
        cand['score'] = score
        cand['composite_score'] = score
        
        # Build Plan
        plan = _build_swing_plan(ticker, price, atr, score, cand)
        cand.update(plan)
        
        if score < 60:
            cand['plan_valid'] = False
            cand['plan_error'] = "LOW_SCORE"
            
        if cand.get('plan_valid'):
            valid_alerts += 1
            all_valid_plans.append(cand)
            print(f"[SwingScan] ✅ {ticker} | Score: {score} | Entry: ${cand['entry']} | Stop: ${cand['stop']} ({((price-cand['stop'])/price)*100:.1f}%) | T1: ${cand['target_1']}")
        else:
            plan_blocked += 1
            err = cand.get('plan_error', 'UNKNOWN')
            if "WIDE" in err: blocked_reasons["STOP_TOO_WIDE"] += 1
            elif "TIGHT" in err: blocked_reasons["STOP_TOO_TIGHT"] += 1
            elif "SCORE" in err: blocked_reasons["LOW_SCORE"] += 1
            print(f"[SwingScan] ⚠️ {ticker} | Score: {score} | BLOCKED: {err}")
            
        # SAVE EVERYTHING TO DB
        try:
            save_snapshot(cand)
        except Exception as e:
            pass # Silently ignore save errors to keep the loop running
            
        snapshots_saved += 1

    print(f"\n[Main] V5.0.8 snapshots saved: {snapshots_saved}\n")
    
    # 4. Send Telegram Alerts
    print("[Main] Selecting Top 3 Alerts to Telegram (score >= 95)...")
    top_alerts = [a for a in all_valid_plans if a.get('score', 0) >= 95]
    
    # Sort: Score -> RVOL -> ATR
    top_alerts.sort(
        key=lambda x: (
            x.get('score', 0), 
            x.get('rvol', 0) or 0, 
            x.get('atr', 0) or 0
        ), 
        reverse=True
    )
    top_alerts = top_alerts[:3]
    
    telegram_sent = 0
    if TELEGRAM_TOKEN and TELEGRAM_CHAT_ID:
        for alert in top_alerts:
            msg = format_swing_alert(alert)
            if not msg:
                continue
            success = send_message(TELEGRAM_TOKEN, TELEGRAM_CHAT_ID, msg)
            if success:
                print(f"[Main]   → {alert['ticker']} (score {alert['score']}) - sent")
                telegram_sent += 1
                
        # Send Summary
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
    
    # 5. Final Summary
    print("\n==========================================================================")
    print("SWING SUMMARY:")
    print(f"  Candidates analyzed:    {len(candidates)}")
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
