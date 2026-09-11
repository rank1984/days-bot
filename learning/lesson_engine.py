"""
DAYS-BOT V5.0.5.2 – Lesson Engine
ADDED: corp_action_rejects + liquidity_rejects in funnel
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

    # Extract gate counters from candidates if available
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
        # NEW: Gate rejections
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

    recommendations = []

    if funnel.get("rejected_gap", 0) > 300:
        recommendations.append("הורד את DISCOVERY_MIN_GAP מ-3.0 ל-2.0 (הרבה מועמדים נפסלו בגלל גאפ)")
    elif funnel.get("rejected_gap", 0) > 200:
        recommendations.append("שקול להוריד את DISCOVERY_MIN_GAP ל-2.5")

    if funnel.get("rejected_volume", 0) > 300:
        recommendations.append("הורד את DISCOVERY_MIN_VOLUME מ-50,000 ל-25,000")
    elif funnel.get("rejected_volume", 0) > 200:
        recommendations.append("שקול להוריד את DISCOVERY_MIN_VOLUME ל-35,000")

    if funnel.get("rejected_price_low", 0) > 80:
        recommendations.append("הורד את DISCOVERY_MIN_PRICE מ-1.00 ל-0.80")
    if funnel.get("rejected_price_high", 0) > 150:
        recommendations.append("העלה את DISCOVERY_MAX_PRICE מ-30.00 ל-40.00")

    if funnel.get("strict_candidates", 0) < 10 and funnel.get("parsed_raw", 0) > 50:
        recommendations.append("מעט מדי Strict Candidates – בדוק את המסננים")

    snapshots = funnel.get("snapshots_received", 0)
    universe = funnel.get("universe", 1)
    if snapshots < universe * 0.7:
        recommendations.append(f"Alpaca החזיר {snapshots}/{universe} – בדוק Rate Limit או Feed")

    lesson = {
        "date": now.strftime("%Y-%m-%d"),
        "time": now.strftime("%H:%M:%S ET"),
        "strategy_version": STRATEGY_VERSION,
        "funnel": funnel,
        "top5": top5_summary,
        "top5_count": len(top5),
        "changes_vs_yesterday": changes,
        "recommendations": recommendations,
        "summary": f"היום נמצאו {len(candidates)} מועמדים, מתוכם {len(top5)} עברו לניתוח מלא.",
        "trading_day": now.strftime("%A"),
        "config_used": config_params or {},
        "candidates_count": len(candidates),
    }

    if not recommendations and funnel.get("strict_candidates", 0) >= 15:
        lesson["recommendations"].append("✅ מצב טוב! המשך עם הפרמטרים הנוכחיים.")
    elif not recommendations:
        lesson["recommendations"].append("⚠️ אין מספיק נתונים להמלצה – תמשיך לעקוב.")

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

    recommendations = lesson.get("recommendations", [])
    if recommendations:
        print("\n💡 RECOMMENDATIONS")
        for rec in recommendations:
            print(f"  • {rec}")

    print("\n" + "=" * 74)