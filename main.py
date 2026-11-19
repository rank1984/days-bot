#!/usr/bin/env python3
"""
DAYS-BOT V5.0.10 - Main Entry Point
Part 1: Imports + Config + Helpers + Macro
"""
import sys, os, argparse, uuid, sqlite3
from datetime import datetime, timedelta
import pytz

try:
    from scanner.universe import load_universe
except ImportError:
    def load_universe(): return []

from scanner.swing_discovery import run_swing_discovery

try:
    from database.snapshot_schema import save_snapshot
except ImportError:
    def save_snapshot(c, s, n): return None

try:
    from database.snapshot_schema import init_snapshot_schema as init_db
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
    def send_message(t, c, m): return False
    def format_swing_alert(a): return ""
    def format_swing_summary(c, v, b, s): return ""

try:
    from scanner.swing_engine import calculate_swing_score
except ImportError:
    def calculate_swing_score(c): return 0

ET = pytz.timezone("America/New_York")
DB_PATH = os.environ.get("DB_PATH", "data/alerts.db")
MAX_MACRO_AGE_MINUTES = 600


def _safe_float(val, default=0.0):
    try:
        if val is None: return default
        if isinstance(val, bool): return float(val)
        if isinstance(val, (int, float)): return float(val)
        return float(str(val).strip())
    except (ValueError, TypeError):
        return default


def _safe_score(val):
    if isinstance(val, (int, float)): return float(val)
    if isinstance(val, dict):
        for k in ['score', 'swing_score', 'total', 'composite_score']:
            if k in val and isinstance(val[k], (int, float)):
                return float(val[k])
        return 0.0
    if isinstance(val, str):
        try: return float(val)
        except ValueError: return 0.0
    return 0.0


def _extract_candidates(result):
    if isinstance(result, list): return result
    if isinstance(result, tuple):
        for item in result:
            if isinstance(item, list): return item
    if isinstance(result, dict):
        for key in ['candidates', 'results', 'snapshots', 'data']:
            if key in result and isinstance(result[key], list):
                return result[key]
    return []


def check_macro_from_db():
    """Reads macro state from DB. Returns (is_bullish, status_str, checked_at_str, spy_price, sma20)."""
    print(f"[Macro] Reading market regime from {DB_PATH}...")
    if not os.path.exists(DB_PATH):
        return False, "NO_DB", "", 0.0, 0.0

    try:
        conn = sqlite3.connect(DB_PATH)
        cur = conn.cursor()
        cur.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='macro_state'")
        if not cur.fetchone():
            conn.close()
            return False, "NO_TABLE", "", 0.0, 0.0

        today = datetime.now(ET).strftime("%Y-%m-%d")
        row = cur.execute("""
            SELECT status, checked_at, spy_price, sma20 FROM macro_state
            WHERE scan_date = ?
        """, (today,)).fetchone()
        conn.close()

        if not row:
            return False, "MISSING_TODAY", "", 0.0, 0.0

        status, checked_at_str, spy_price, sma20 = row
        spy_price = float(spy_price or 0)
        sma20 = float(sma20 or 0)

        try:
            checked_at = datetime.fromisoformat(checked_at_str)
            age_minutes = (datetime.now(ET) - checked_at).total_seconds() / 60
            if age_minutes > MAX_MACRO_AGE_MINUTES:
                print(f"[Macro] STALE: {age_minutes:.0f} min > {MAX_MACRO_AGE_MINUTES}")
                return False, "STALE_DATA", checked_at_str, spy_price, sma20
        except Exception:
            return False, "BAD_TIMESTAMP", checked_at_str, spy_price, sma20

        is_bullish = (status == "BULLISH")
        return is_bullish, status, checked_at_str, spy_price, sma20

    except Exception as e:
        print(f"[Macro] ERROR: {e}")
        return False, "ERROR", "", 0.0, 0.0
        
# ==============================================================================
# DIP FILTER (The winning strategy)
# ==============================================================================
def _check_dip_filter(candidate: dict):
    """Returns (passed: bool, reason: str)"""
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
    max_position_value = account_size * 0.20

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

    # 🚨 V5.0.10: Block weekends FIRST
    if now_et.weekday() >= 5:
        day_name = now_et.strftime('%A')
        print(f"[Main] {day_name} ({now_et.strftime('%Y-%m-%d')}) — weekend. Skipping scan.")
        return

    print("=" * 74)
    print("DAYS-BOT - SWING ENGINE V5.0.10")
    print(f"Date: {now_et.strftime('%Y-%m-%d %H:%M:%S')} ET | Mode: {'MANUAL' if manual else 'AUTO'}")
    print(f"Scan ID: {scan_id}")
    print("Filters: DIP (10-50$, Gap<-2%, ATR>3%) + MACRO (Track-Only)")
    print("Telegram: max 3 alerts, score >= 80")
    print("=" * 74)

    # 1. MACRO CHECK (read but not blocking)
    is_bullish, status_str, checked_at, spy_price, sma20 = check_macro_from_db()

    if is_bullish:
        print(f"[Macro] ✅ BULLISH (Track-Only)")
    else:
        print(f"[Macro] ⚠️  {status_str} (Track-Only)")
    if spy_price > 0:
        print(f"[Macro] SPY={spy_price:.2f} | SMA20={sma20:.2f}")
    print("[Macro] Proceeding with scan (Track-Only mode).")

    # 2. INIT DB
    try:
        os.makedirs("data", exist_ok=True)
        print(f"[Main] Initializing DB at {DB_PATH}...")
        init_db()
        print("[Main] DB initialized.")
    except Exception as e:
        print(f"[FATAL] Could not init DB: {e}")
        return

    # 3. UNIVERSE
    print("[Main] Building dynamic universe...")
    try:
        universe = load_universe()
        print(f"[Main] Universe ready: {len(universe)} symbols")
    except Exception as e:
        print(f"[FATAL] Could not build universe: {e}")
        return

    if not universe:
        print("[Main] Empty universe. Exiting.")
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

    # 5. ANALYZE + SAVE
    snapshots_saved = 0
    valid_plans = 0
    alerts_candidates = 0
    dip_filter_blocked = 0
    dip_filter_reasons = {}
    plan_blocked = 0
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
            try:
                score = _safe_score(calculate_swing_score(cand))
            except Exception:
                score = 0.0
        cand['score'] = score
        cand['composite_score'] = score

        # Dip filter
        passed, reason = _check_dip_filter(cand)
        if not passed:
            dip_filter_blocked += 1
            dip_filter_reasons[reason] = dip_filter_reasons.get(reason, 0) + 1
            continue

        # Build plan
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
            print(f"[SwingScan] ✅ {ticker:<6} | Score: {score:>5.1f} | Entry: ${cand['entry']:>7.2f} | Stop: ${cand['stop']:>7.2f} | T1: ${cand['target_1']:>7.2f} | Size: {cand['position_size']} (${cand['position_value']})")
        else:
            plan_blocked += 1
            err = cand.get('plan_error', 'UNKNOWN')
            if "WIDE" in err:
                plan_blocked_reasons["STOP_TOO_WIDE"] += 1
            elif "TIGHT" in err:
                plan_blocked_reasons["STOP_TOO_TIGHT"] += 1
            elif "SCORE" in err:
                plan_blocked_reasons["LOW_SCORE"] += 1
            print(f"[SwingScan] ⚠️  {ticker:<6} | Score: {score:>5.1f} | BLOCKED: {err}")

        # Attach macro metadata for snapshot
        cand['macro_checked_at'] = checked_at
        cand['macro_gate_passed'] = is_bullish
        cand['spy_price_at_scan'] = spy_price
        cand['sma20_at_scan'] = sma20
        cand['regime'] = status_str

        # Save to DB
        try:
            snap_id = save_snapshot(cand, scan_id, now_et)
            if snap_id:
                snapshots_saved += 1
            else:
                print(f"[WARN] Failed to save snapshot for {ticker} (returned None)")
        except Exception as e:
            print(f"[WARN] Exception saving {ticker}: {e}")

    print(f"\n[Main] Snapshots saved: {snapshots_saved}")
    print(f"[Main] Valid plans: {valid_plans}")
    print(f"[Main] Alerts candidates (>=80): {alerts_candidates}")
    print(f"[Main] Dip Filter blocked: {dip_filter_blocked}")
    for reason, count in sorted(dip_filter_reasons.items(), key=lambda x: -x[1]):
        print(f"   - {reason}: {count}")

    # 6. SEND TELEGRAM (Top 3)
    print("\n[Main] Selecting Top 3 Alerts to Telegram...")
    top_pool = [a for a in all_valid_plans if a.get('score', 0) >= 80]
    top_pool.sort(
        key=lambda x: (
            x.get('score', 0),
            _safe_score(x.get('rvol', 0)),
            _safe_score(x.get('atr', 0)),
        ),
        reverse=True,
    )
    top_alerts = top_pool[:3]

    if top_pool:
        print(f"[DEBUG] Found {len(top_pool)} alerts (>=80):")
        for i, a in enumerate(top_pool[:5]):
            print(f"[DEBUG]   #{i+1}: {a.get('ticker')} | score={a.get('score'):.1f} | atr={a.get('atr', 0):.2f}")

    telegram_sent = 0
    telegram_failed = 0

    if TELEGRAM_TOKEN and TELEGRAM_CHAT_ID and top_alerts:
        print(f"[Main] Sending top {len(top_alerts)} alerts...")
        for alert in top_alerts:
            ticker = alert.get('ticker', 'UNKNOWN')
            try:
                msg = format_swing_alert(alert)
            except Exception as e:
                print(f"[Main]   → {ticker} | FORMAT ERROR: {e}")
                telegram_failed += 1
                continue

            if not msg:
                print(f"[Main]   → {ticker} | EMPTY MESSAGE (skipped)")
                continue

            if send_message(TELEGRAM_TOKEN, TELEGRAM_CHAT_ID, msg):
                print(f"[Main]   → {ticker} (score {alert.get('score'):.1f}) - sent")
                telegram_sent += 1
            else:
                print(f"[Main]   → {ticker} (score {alert.get('score'):.1f}) - FAILED")
                telegram_failed += 1

        if telegram_sent > 0:
            try:
                summary_msg = format_swing_summary(
                    candidates_count=len(candidates),
                    valid_alerts=valid_plans,
                    blocked=sum(plan_blocked_reasons.values()),
                    telegram_sent=telegram_sent,
                )
                if summary_msg and send_message(TELEGRAM_TOKEN, TELEGRAM_CHAT_ID, summary_msg):
                    print("[Main]   → Summary sent")
            except Exception as e:
                print(f"[Main] Summary error: {e}")
    elif not top_alerts:
        print("[Main] No alerts with score >= 80. Nothing to send.")
    else:
        print("[Main] Missing Telegram credentials. Skipping alerts.")

    # 7. FINAL SUMMARY
    print("\n" + "=" * 74)
    print("SWING SUMMARY:")
    print(f"  Macro (Track-Only):        {status_str}")
    if spy_price > 0:
        print(f"  SPY / SMA20:               {spy_price:.2f} / {sma20:.2f}")
    print(f"  Candidates analyzed:       {len(candidates)}")
    print(f"  Dip Filter blocked:        {dip_filter_blocked}")
    for reason, count in sorted(dip_filter_reasons.items(), key=lambda x: -x[1]):
        print(f"    - {reason}: {count}")
    print(f"  Snapshots saved:           {snapshots_saved}")
    print(f"  Valid plans:               {valid_plans}")
    print(f"  Alerts candidates (>=80):  {alerts_candidates}")
    if plan_blocked > 0:
        print(f"  Plan blocked:              {plan_blocked}")
        for reason, count in plan_blocked_reasons.items():
            if count > 0:
                print(f"    - {reason}: {count}")
    print(f"  Telegram sent:             {telegram_sent}")
    print(f"  Telegram failed:           {telegram_failed}")
    print("=" * 74)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("command", nargs="?", default="swing_v1")
    parser.add_argument("--manual", action="store_true")
    args = parser.parse_args()

    if args.command == "swing_v1":
        run_swing_v1(manual=args.manual)
    else:
        print(f"Unknown command: {args.command}")
