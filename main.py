"""
DAYS-BOT V5.0.8 – RESEARCH ENGINE (Multi-Strategy)
1. fullscan_v34 - מנוע Pre-Market (Legacy)
2. swing_v1 - מנוע Swing יומי (Daily Bars)

V5.0.8:
- MAX_STOP_PCT = 10% (פוסל סטופים רחבים מדי כמו BSP -18%)
- MAX_TELEGRAM_ALERTS = 10 (רק 10 ההתראות הטובות ביותר נשלחות לטלגרם)
"""
import sys
from pathlib import Path
from datetime import datetime
import pytz

BASE_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(BASE_DIR))

ET = pytz.timezone("America/New_York")

from utils.config import TELEGRAM_TOKEN, TELEGRAM_CHAT_ID
from utils.config import ACCOUNT_SIZE, MAX_RISK_PER_TRADE_V31, MAX_POSITION_VALUE_PCT

from scanner.full_scan_v34 import full_scan_v34
from scanner.swing_engine import calculate_swing_score
from database.db import init_db, save_alert
from database.snapshot_schema import init_snapshot_schema, save_snapshot
from telegram_v3 import send_message


# ---------------------------------------------------------------------------
# CONFIGURATION
# ---------------------------------------------------------------------------

MIN_STOP_PCT = 2.0      # מינימום - למנוע סטופים צמודים מדי (AES, BWIN)
MAX_STOP_PCT = 10.0     # מקסימום - למנוע סטופים רחבים מדי (BSP, BAK)
MIN_SWING_SCORE = 60    # סף מינימום לתוכנית תקפה
MAX_TELEGRAM_ALERTS = 10  # מקסימום התראות טלגרם בריצה אחת
TELEGRAM_SCORE_THRESHOLD = 85  # שלח התראה רק לציונים מעל הסף הזה


# ---------------------------------------------------------------------------
# TELEGRAM ALERTS
# ---------------------------------------------------------------------------

def send_swing_alert(ticker, entry, stop, t1, t2, score, position_size, max_loss):
    """שולח התראת טלגרם פרטנית עבור תוכנית Swing אחת."""
    risk_per_share = entry - stop
    risk_pct = (risk_per_share / entry) * 100

    msg = f"""
🎯 *SWING ALERT: {ticker}*
━━━━━━━━━━━━━━━━━━
📊 Score: {score:.0f}/100
💰 Entry: ${entry:.2f}
🛑 Stop: ${stop:.2f} (-{risk_pct:.1f}%)
🎯 T1: ${t1:.2f} (+{risk_pct*2:.1f}%, R:R 1:2)
🎯 T2: ${t2:.2f} (+{risk_pct*4:.1f}%, R:R 1:4)
━━━━━━━━━━━━━━━━━━
📦 Size: {position_size} shares
💵 Max Loss: ${max_loss:.2f}
⏳ Hold: 1-3 days
"""
    try:
        return send_message(TELEGRAM_TOKEN, TELEGRAM_CHAT_ID, msg)
    except Exception as e:
        print(f"[Main] Telegram error for {ticker}: {type(e).__name__}: {e}")
        return False


def send_swing_summary(scan_date, saved_alerts, candidates_count, blocked_count, telegram_sent):
    """שולח הודעת סיכום כללית."""
    msg = f"""
📊 *DAYS-BOT Swing Summary*
━━━━━━━━━━━━━━━━━━
📅 Date: {scan_date}
🔍 Candidates: {candidates_count}
✅ Valid Alerts: {saved_alerts}
⚠️ Blocked: {blocked_count}
📱 Sent to Telegram: {telegram_sent}
━━━━━━━━━━━━━━━━━━
"""
    try:
        send_message(TELEGRAM_TOKEN, TELEGRAM_CHAT_ID, msg)
    except Exception as e:
        print(f"[Main] Telegram summary error: {type(e).__name__}: {e}")


# ---------------------------------------------------------------------------
# PM DATA SANITIZATION (Legacy)
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
# Swing helpers
# ---------------------------------------------------------------------------

def _safe_swing(candidate, analysis=None):
    try:
        result = calculate_swing_score(candidate, analysis)
        if not isinstance(result, dict):
            return {"swing_score": 0, "swing_type": "INVALID", "qualified": False}
        return result
    except Exception as e:
        print(f"[Main] Swing error {candidate.get('ticker')}: {type(e).__name__}: {e}")
        return {"swing_score": 0, "swing_type": "ERROR", "error": str(e), "qualified": False}


def _build_swing_plan(candidate: dict) -> dict:
    """
    תוכנית Swing עם שני חסמים קריטיים:
    - MIN_STOP_PCT = 2.0% (למנוע סטופים צמודים מדי - עלויות טורפות)
    - MAX_STOP_PCT = 10.0% (למנוע סטופים רחבים מדי - פוזיציה זעירה מדי)
    """
    price = float(candidate.get('price', 0) or 0)
    atr = float(candidate.get('atr', 0) or 0)

    if price <= 0 or atr <= 0:
        return {"plan_valid": False, "plan_error": "INVALID_PRICE_OR_ATR"}

    # Stop = max(1.5 ATR, 2.5% minimum) - אבל לא יותר מ-10%
    atr_stop = price - (1.5 * atr)
    min_pct_stop = price * (1 - MIN_STOP_PCT / 100.0)  # 2% minimum
    stop = min(atr_stop, min_pct_stop)

    if stop <= 0:
        return {"plan_valid": False, "plan_error": "STOP_BELOW_ZERO"}

    stop_distance_pct = (price - stop) / price * 100.0

    # 🚨 חסם 1: סטופ צמוד מדי (עלויות טורפות)
    if stop_distance_pct < MIN_STOP_PCT:
        return {
            "plan_valid": False,
            "plan_error": f"STOP_TOO_TIGHT ({stop_distance_pct:.2f}% < {MIN_STOP_PCT}%)",
        }

    # 🚨 חסם 2: סטופ רחב מדי (פוזיציה זעירה, R:R לא אמיתי)
    if stop_distance_pct > MAX_STOP_PCT:
        return {
            "plan_valid": False,
            "plan_error": f"STOP_TOO_WIDE ({stop_distance_pct:.2f}% > {MAX_STOP_PCT}%)",
        }

    risk_per_share = price - stop
    t1 = price + (2.0 * risk_per_share)
    t2 = price + (4.0 * risk_per_share)

    # גודל פוזיציה
    max_risk_dollars = ACCOUNT_SIZE * MAX_RISK_PER_TRADE_V31
    position_size_risk = int(max_risk_dollars / risk_per_share)
    max_position_value = ACCOUNT_SIZE * MAX_POSITION_VALUE_PCT
    position_size_value = int(max_position_value / price)
    position_size = min(position_size_risk, position_size_value)

    if position_size <= 0:
        return {"plan_valid": False, "plan_error": "POSITION_SIZE_ZERO"}

    actual_max_loss = round(risk_per_share * position_size, 2)

    return {
        "plan_valid": True,
        "plan_error": None,
        "entry": round(price, 4),
        "stop": round(stop, 4),
        "target_1": round(t1, 4),
        "target_2": round(t2, 4),
        "risk_per_share": round(risk_per_share, 4),
        "stop_distance_pct": round(stop_distance_pct, 2),
        "position_size": position_size,
        "max_loss": actual_max_loss,
        "account_size": ACCOUNT_SIZE,
        "risk_pct": MAX_RISK_PER_TRADE_V31,
        "hold_type": "SWING_1_3D",
    }


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
# Legacy Normalization
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
# ENGINE 1: Pre-Market (Legacy)
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
    saved = 0
    for candidate in candidates:
        _sanitize_pm_fields(candidate)
        sid = save_snapshot(candidate, scan_id, now_et)
        if sid is not None:
            saved += 1
    print(f"[Main] V5.0.6 snapshots saved: {saved}")

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
# ENGINE 2: Swing Daily Scan (with smart Telegram alerts)
# ---------------------------------------------------------------------------

def run_swing_v1(manual=False):
    from scanner.swing_discovery import run_swing_discovery
    from scanner.universe import load_universe

    init_db()
    init_snapshot_schema()
    now_et = datetime.now(ET)
    scan_date = now_et.strftime("%Y-%m-%d")
    scan_id = now_et.strftime("%Y-%m-%d_SWING")

    print("\n" + "=" * 74)
    print("DAYS-BOT - SWING ENGINE (Daily Bars) V5.0.8")
    print(f"Date: {scan_date} | Mode: {'MANUAL' if manual else 'LIVE'}")
    print(f"Stop range: {MIN_STOP_PCT}%-{MAX_STOP_PCT}% | Min Score: {MIN_SWING_SCORE}")
    print(f"Telegram: max {MAX_TELEGRAM_ALERTS} alerts, score >= {TELEGRAM_SCORE_THRESHOLD}")
    print("=" * 74)

    universe = load_universe()
    if not universe:
        print("[Main] Universe is empty. Aborting.")
        return

    tickers = universe[:500] if isinstance(universe, list) else list(universe)[:500]

    print(f"[Main] Starting Swing Discovery on {len(tickers)} symbols...")
    candidates, stats = run_swing_discovery(tickers)

    if not candidates:
        print("[Main] No swing candidates found today.")
        return

    print(f"[Main] Analyzing {len(candidates)} swing candidates...")
    candidates.sort(key=lambda x: x.get('avg_volume', 0), reverse=True)

    saved_alerts = 0
    saved_snapshots = 0
    plan_blocked = 0
    blocked_reasons = {"STOP_TOO_TIGHT": 0, "STOP_TOO_WIDE": 0, "OTHER": 0}
    valid_candidates_for_telegram = []

    for c in candidates:
        ticker = c['ticker']

        # 1. ציון Swing
        swing = _safe_swing(c)
        c['swing_score'] = float(swing.get('swing_score', 0) or 0)
        c['composite_score'] = c['swing_score']

        # 2. בניית תוכנית מסחר
        plan = _build_swing_plan(c)
        c.update(plan)

        # 3. שמירת Snapshot (תמיד)
        _sanitize_pm_fields(c)
        sid = save_snapshot(c, scan_id, now_et)
        if sid is not None:
            saved_snapshots += 1

        # 4. שמירת Alert אם התוכנית תקינה וציון מעל הסף
        if c.get('plan_valid') and c.get('swing_score', 0) >= MIN_SWING_SCORE:
            c['data_status'] = "ACTIONABLE"
            c['trade_type'] = "SWING_1_3D"
            try:
                save_alert(**c)
                saved_alerts += 1
                valid_candidates_for_telegram.append(c)
                print(f"[SwingScan] ✅ {ticker} | Score: {c['swing_score']:.0f} | Entry: ${c['entry']:.2f} | Stop: ${c['stop']:.2f} ({c['stop_distance_pct']:.1f}%) | T1: ${c['target_1']:.2f}")
            except Exception as e:
                print(f"[SwingScan] DB error {ticker}: {e}")
        else:
            plan_blocked += 1
            reason = c.get('plan_error') or 'LOW_SCORE'
            if 'STOP_TOO_TIGHT' in reason:
                blocked_reasons["STOP_TOO_TIGHT"] += 1
            elif 'STOP_TOO_WIDE' in reason:
                blocked_reasons["STOP_TOO_WIDE"] += 1
            else:
                blocked_reasons["OTHER"] += 1
            print(f"[SwingScan] ⚠️ {ticker} | Score: {c['swing_score']:.0f} | BLOCKED: {reason}")

    print(f"\n[Main] V5.0.8 snapshots saved: {saved_snapshots}")

    # 🎯 שליחת התראות טלגרם - רק ה-Top N עם ציון מעל הסף
    telegram_sent = 0
    if valid_candidates_for_telegram:
        # מיין לפי ציון (יורד), ואז לפי נפח (יורד)
        valid_candidates_for_telegram.sort(
            key=lambda x: (x.get('swing_score', 0), x.get('avg_volume', 0)),
            reverse=True
        )
        
        # קח רק את אלה שעוברים את סף הטלגרם, ועד MAX_TELEGRAM_ALERTS
        top_for_telegram = [
            c for c in valid_candidates_for_telegram
            if c.get('swing_score', 0) >= TELEGRAM_SCORE_THRESHOLD
        ][:MAX_TELEGRAM_ALERTS]

        print(f"\n[Main] Sending {len(top_for_telegram)} alerts to Telegram (top {MAX_TELEGRAM_ALERTS}, score >= {TELEGRAM_SCORE_THRESHOLD})...")
        
        for c in top_for_telegram:
            sent = send_swing_alert(
                ticker=c['ticker'],
                entry=c['entry'],
                stop=c['stop'],
                t1=c['target_1'],
                t2=c['target_2'],
                score=c['swing_score'],
                position_size=c['position_size'],
                max_loss=c['max_loss'],
            )
            if sent:
                telegram_sent += 1
            print(f"[Main]   → {c['ticker']} (score {c['swing_score']:.0f}) - {'sent' if sent else 'FAILED'}")

    # סיכום
    print("\n" + "=" * 74)
    print(f"SWING SUMMARY:")
    print(f"  Candidates analyzed:    {len(candidates)}")
    print(f"  Snapshots saved:        {saved_snapshots}")
    print(f"  Valid alerts (saved):   {saved_alerts}")
    print(f"  Plan blocked:           {plan_blocked}")
    print(f"    - Stop too tight:     {blocked_reasons['STOP_TOO_TIGHT']}")
    print(f"    - Stop too wide:      {blocked_reasons['STOP_TOO_WIDE']}")
    print(f"    - Other (low score):  {blocked_reasons['OTHER']}")
    print(f"  Telegram sent:          {telegram_sent}")
    print("=" * 74)

    # שליחת סיכום כללי
    if saved_alerts > 0:
        send_swing_summary(scan_date, saved_alerts, len(candidates), plan_blocked, telegram_sent)


# ---------------------------------------------------------------------------
# MAIN
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
