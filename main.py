#!/usr/bin/env python3
"""
DAYS-BOT V5.0.8 - Main Entry Point
Fixed: Loads universe before passing to run_swing_discovery + Top 3 Telegram Alerts
"""
import sys
import os
import argparse
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

# 2. Discovery Engine (Explicitly using the correct function name and signature)
from scanner.swing_discovery import run_swing_discovery

# 3. Database (Defensive)
try:
    from database.snapshot_schema import save_snapshot
except ImportError:
    def save_snapshot(cand):
        print(f"[WARN] save_snapshot not found. Skipping DB save for {cand.get('ticker')}")

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

# Optional: Calculate score if it's not in the candidate dict
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
        candidates = run_swing_discovery(universe)
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
    blocked_reasons = {"STOP_TOO_WIDE": 0, "STOP_TOO_TIGHT": 0, "LOW_SCORE": 0}
    
    all_valid_plans = []
    
    for cand in candidates:
        ticker = cand.get('ticker', 'UNKNOWN')
        price = cand.get('price', 0)
        atr = cand.get('atr', 0)
        
        # Calculate or extract Score
        score = cand.get('score', cand.get('swing_score', cand.get('composite_score', 0)))
        if score == 0:
            score = calculate_swing_score(cand)
            
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
            
        # SAVE EVERYTHING TO DB (Crucial for data collection!)
        try:
            save_snapshot(cand)
        except Exception as e:
            print(f"[WARN] Failed to save snapshot for {ticker}: {e}")
            
        snapshots_saved += 1

    print(f"\n[Main] V5.0.8 snapshots saved: {snapshots_saved}\n")
    
    # 5. Send Telegram Alerts (Top 3)
    print("[Main] Selecting Top 3 Alerts to Telegram (score >= 95)...")
    
    # Filter: Only score >= 95
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
    
    # Slice: Top 3 only
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
    
    # 6. Final Summary
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
