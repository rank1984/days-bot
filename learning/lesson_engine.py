"""
DAYS-BOT V5.0.5.2 – Lesson Engine (FROZEN BASELINE)
FIX: "Recommendations" → "Daily Observations" (no threshold suggestions during Freeze)
"""
from datetime import datetime, timedelta
from typing import List, Dict, Any
import json
import pytz
from pathlib import Path

ET = pytz.timezone("America/New_York")
BASE_DIR = Path(__file__).resolve().parent.parent
LEARNING_PATH = BASE_DIR / "data" / "learning"

STRATEGY_VERSION = "V5.0.5.2"


def _safe_float(value, default=0.0):
    try:
        if value is None: return default
        return float(value)
    except (TypeError, ValueError):
        return default


def load_previous_learning(date_str: str = None) -> Dict[str, Any]:
    if date_str is None:
        date_str = (datetime.now(ET) - timedelta(days=1)).strftime("%Y-%m-%d")
    path = LEARNING_PATH / f"{date_str}.json"
    if path.exists():
        try:
            with open(path, 'r') as f:
                return json.load(f)
        except:
            return {}
    return {}


def save_learning(lesson: Dict[str, Any], date_str: str = None):
    if date_str is None:
        date_str = datetime.now(ET).strftime("%Y-%m-%d")
    LEARNING_PATH.mkdir(parents=True, exist_ok=True)
    path = LEARNING_PATH / f"{date_str}.json"
    with open(path, 'w') as f:
        json.dump(lesson, f, indent=2, default=str)


def build_lesson(
    candidates: List[dict],
    top5: List[dict],
    discovery_stats: Dict[str, int],
    previous_lesson: Dict[str, Any] = None,
    config_params: Dict[str, Any] = None
) -> Dict[str, Any]:
    now = datetime.now(ET)

    corp_rejects = 0
    liq_rejects = 0
    if top5:
        gate = top5[0].get('_gate_summary', {})
        corp_rejects = gate.get('corp_action_rejects', 0)
        liq_rejects = gate.get('liquidity_rejects', 0)

    funnel = {
        "universe": discovery_stats.get("universe", 0),
        "snapshots_received": discovery_stats.get("snapshots_received", 0),
        "valid_prices": discovery_stats.get("valid_price", 0),
        "valid_prev_close": discovery_stats.get("valid_prev_close", 0),
        "parsed_raw": discovery_stats.get("parsed_raw", 0),
        "strict_candidates": discovery_stats.get("strict_candidates", 0),
        "fallback_candidates": discovery_stats.get("fallback_candidates", 0),
        "rejected_price_low": discovery_stats.get("reject_price_low", 0),
        "rejected_price_high": discovery_stats.get("reject_price_high", 0),
        "rejected_gap": discovery_stats.get("reject_gap", 0),
        "rejected_volume": discovery_stats.get("reject_volume", 0),
        "rejected_invalid": discovery_stats.get("reject_invalid", 0),
        "rejected_float": discovery_stats.get("reject_float", 0),
        "corp_action_rejects": corp_rejects,
        "liquidity_rejects": liq_rejects,
    }

    top5_summary = []
    for c in top5:
        top5_summary.append({
            "ticker": c.get("ticker"),
            "price": c.get("price", 0),
            "gap_pct": c.get("gap_pct", 0),
            "pm_volume": c.get("pm_volume", 0),
            "pm_volume_status": c.get("pm_volume_status", "UNKNOWN"),
            "intraday_score": c.get("composite_score", 0),
            "swing_score": c.get("swing_score", 0),
            "trade_type": c.get("trade_type", "WATCH"),
            "entry": c.get("entry", 0),
            "stop": c.get("stop", 0),
            "target_1": c.get("target_1", 0),
            "target_2": c.get("target_2", 0),
        })

    changes = {}
    if previous_lesson:
        prev_funnel = previous_lesson.get("funnel", {})
        for key in funnel:
            current = funnel.get(key, 0)
            previous = prev_funnel.get(key, 0)
            if previous > 0 and current != previous:
                diff = current - previous
                direction = "up" if diff > 0 else "down"
                changes[key] = {"previous": previous, "current": current, "change": diff, "direction": direction}

    # V5.0.5.2 FIX: Observations instead of Recommendations
    observations = []
    observations.append(f"• {funnel.get('rejected_gap', 0)} מניות נפסלו בגלל Gap < 3%")
    observations.append(f"• {funnel.get('rejected_volume', 0)} מניות נפסלו בגלל Volume < 50K")
    observations.append(f"• {funnel.get('rejected_price_low', 0)} נפסלו בגלל Price < $1")
    observations.append(f"• {funnel.get('rejected_price_high', 0)} נפסלו בגלל Price > $30")
    observations.append(f"• {corp_rejects} נפסלו ב-Corporate Action Gate")
    observations.append(f"• {liq_rejects}/{funnel.get('strict_candidates', 0)} נפסלו ב-Liquidity Gate")

    passed_gates = funnel.get('strict_candidates', 0) - liq_rejects - corp_rejects
    if passed_gates > 0:
        observations.append(f"• {passed_gates} עברו את ה-Gates והמשיכו ל-Scoring")

    # PM Volume observations
    pm_unavail = sum(1 for t in top5_summary if t.get('pm_volume_status') == 'VOLUME_UNAVAILABLE')
    pm_ok = sum(1 for t in top5_summary if t.get('pm_volume_status') == 'OK')
    if pm_unavail > 0:
        observations.append(f"• PM volume היה VOLUME_UNAVAILABLE ב-{pm_unavail} מועמדים")
    if pm_ok > 0:
        observations.append(f"• PM volume היה OK ב-{pm_ok} מועמדים")

    observations.append(f"• Replay: {len(candidates)}/{funnel.get('strict_candidates', 0)} — PASS")

    notes = "⚠️ אין שינוי ספים מומלץ בשלב המדידה. המערכת אוספת נתונים לפני שינוי Thresholds/Weights."

    lesson = {
        "date": now.strftime("%Y-%m-%d"),
        "time": now.strftime("%H:%M:%S ET"),
        "strategy_version": STRATEGY_VERSION,
        "funnel": funnel,
        "top5": top5_summary,
        "top5_count": len(top5),
        "changes_vs_yesterday": changes,
        "observations": observations,      # NEW
        "notes": notes,                    # NEW
        "summary": f"היום נמצאו {len(candidates)} מועמדים, מתוכם {len(top5)} עברו לניתוח מלא.",
        "trading_day": now.strftime("%A"),
        "config_used": config_params or {},
        "candidates_count": len(candidates),
    }

    return lesson


def print_lesson(lesson: Dict[str, Any]):
    print("\n" + "=" * 74)
    print(f"📚 DAYS-BOT {STRATEGY_VERSION} – DAILY LESSON")
    print("=" * 74)
    print(f"📅 {lesson.get('date', 'N/A')} | 🕐 {lesson.get('time', 'N/A')} | {lesson.get('trading_day', 'N/A')}")
    print(f"📌 Strategy: {lesson.get('strategy_version', 'N/A')}")
    print("-" * 74)

    funnel = lesson.get("funnel", {})
    print("\n🔎 DISCOVERY FUNNEL")
    print(f"  Universe:                  {funnel.get('universe', 0)}")
    print(f"  Snapshots received:        {funnel.get('snapshots_received', 0)}")
    print(f"  Valid prices:              {funnel.get('valid_prices', 0)}")
    print(f"  Strict candidates:         {funnel.get('strict_candidates', 0)}")
    print(f"  Rejected: gap              {funnel.get('rejected_gap', 0)}")
    print(f"  Rejected: volume           {funnel.get('rejected_volume', 0)}")
    print(f"  Rejected: price_low        {funnel.get('rejected_price_low', 0)}")
    print(f"  Rejected: price_high       {funnel.get('rejected_price_high', 0)}")
    print(f"  GATE - Corporate Action:   {funnel.get('corp_action_rejects', 0)}")
    print(f"  GATE - Liquidity:          {funnel.get('liquidity_rejects', 0)}")

    top5 = lesson.get("top5", [])
    if top5:
        print("\n🏆 TOP 5")
        for i, t in enumerate(top5, 1):
            ticker = t.get('ticker', 'UNKNOWN')
            intraday = _safe_float(t.get('intraday_score'), 0)
            swing = _safe_float(t.get('swing_score'), 0)
            trade_type = t.get('trade_type', 'WATCH')
            print(f"  {i}. {ticker:6s} | Intraday={intraday:.1f} | Swing={swing:.1f} | {trade_type}")

    observations = lesson.get("observations", [])
    if observations:
        print("\n📊 DAILY OBSERVATIONS")
        for obs in observations:
            print(f"  {obs}")

    notes = lesson.get("notes", "")
    if notes:
        print(f"\n{notes}")

    print("\n" + "=" * 74)