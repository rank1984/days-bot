"""
DAYS-BOT V4.3 – Lesson Engine
Tracks daily learning: funnel changes, top5 performance, recommendations.
"""
from datetime import datetime, timedelta
from typing import List, Dict, Any
import json
import pytz
from pathlib import Path

ET = pytz.timezone("America/New_York")
BASE_DIR = Path(__file__).resolve().parent.parent
LEARNING_PATH = BASE_DIR / "data" / "learning"


def load_previous_learning(date_str: str = None) -> Dict[str, Any]:
    """Load yesterday's learning data"""
    if date_str is None:
        date_str = (datetime.now(ET) - timedelta(days=1)).strftime("%Y-%m-%d")
    path = LEARNING_PATH / f"{date_str}.json"
    if path.exists():
        with open(path, 'r') as f:
            return json.load(f)
    return {}


def save_learning(lesson: Dict[str, Any], date_str: str = None):
    """Save today's lesson"""
    if date_str is None:
        date_str = datetime.now(ET).strftime("%Y-%m-%d")
    LEARNING_PATH.mkdir(parents=True, exist_ok=True)
    path = LEARNING_PATH / f"{date_str}.json"
    with open(path, 'w') as f:
        json.dump(lesson, f, indent=2)


def build_lesson(
    candidates: List[dict],
    top5: List[dict],
    discovery_stats: Dict[str, int],
    previous_lesson: Dict[str, Any] = None
) -> Dict[str, Any]:
    """
    Build structured learning lesson from today's run
    """
    now = datetime.now(ET)

    # 1. Funnel analysis
    funnel = {
        "universe": discovery_stats.get("universe", 0),
        "snapshots_received": discovery_stats.get("returned_snapshots", 0),
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
    }

    # 2. Top5 summary (today)
    top5_summary = []
    for c in top5:
        top5_summary.append({
            "ticker": c.get("ticker"),
            "price": c.get("price"),
            "gap_pct": c.get("gap_pct"),
            "pm_volume": c.get("pm_volume"),
            "intraday_score": c.get("composite_score", 0),
            "swing_score": c.get("swing_score", 0),
            "trade_type": c.get("trade_type", "WATCH")
        })

    # 3. Find what changed vs previous day
    changes = {}
    if previous_lesson:
        prev_funnel = previous_lesson.get("funnel", {})
        for key in funnel:
            current = funnel.get(key, 0)
            previous = prev_funnel.get(key, 0)
            if previous > 0 and current != previous:
                diff = current - previous
                direction = "up" if diff > 0 else "down"
                changes[key] = {
                    "previous": previous,
                    "current": current,
                    "change": diff,
                    "direction": direction
                }

    # 4. Recommendations (based on today's data)
    recommendations = []

    # If many rejected by gap -> lower threshold?
    if funnel.get("rejected_gap", 0) > 300:
        recommendations.append("הורד את DISCOVERY_MIN_GAP מ-3.0 ל-2.0 (הרבה מועמדים נפסלו בגלל גאפ)")
    if funnel.get("rejected_volume", 0) > 300:
        recommendations.append("הורד את DISCOVERY_MIN_VOLUME מ-50,000 ל-25,000 (הרבה מועמדים נפסלו בגלל נפח)")
    if funnel.get("strict_candidates", 0) < 10:
        recommendations.append("שקול להרחיב את ה-Universe (למעל 500) או להקל על DISCOVERY_MIN_PRICE")
    if funnel.get("snapshots_received", 0) < funnel.get("universe", 0) * 0.8:
        recommendations.append("Alpaca החזיר פחות מ-80% מה-Universe – בדוק Rate Limit או Feed")

    # 5. Lesson summary
    lesson = {
        "date": now.strftime("%Y-%m-%d"),
        "time": now.strftime("%H:%M:%S ET"),
        "funnel": funnel,
        "top5": top5_summary,
        "top5_count": len(top5),
        "changes_vs_yesterday": changes,
        "recommendations": recommendations,
        "summary": f"היום נמצאו {len(candidates)} מועמדים, מתוכם {len(top5)} עברו לניתוח מלא.",
        "trading_day": now.strftime("%A")
    }

    return lesson


def print_lesson(lesson: Dict[str, Any]):
    """Print lesson to console in readable format"""
    print("\n" + "="*74)
    print("📚 DAYS-BOT V4.3 – DAILY LESSON")
    print("="*74)
    print(f"📅 {lesson['date']} | 🕐 {lesson['time']} | {lesson['trading_day']}")
    print("-"*74)

    # Funnel
    funnel = lesson.get("funnel", {})
    print("\n🔎 DISCOVERY FUNNEL")
    print(f"  Universe:               {funnel.get('universe', 0)}")
    print(f"  Snapshots received:     {funnel.get('snapshots_received', 0)}")
    print(f"  Valid prices:           {funnel.get('valid_prices', 0)}")
    print(f"  Strict candidates:      {funnel.get('strict_candidates', 0)}")
    print(f"  Rejected: gap           {funnel.get('rejected_gap', 0)}")
    print(f"  Rejected: volume        {funnel.get('rejected_volume', 0)}")
    print(f"  Rejected: price_low     {funnel.get('rejected_price_low', 0)}")
    print(f"  Rejected: price_high    {funnel.get('rejected_price_high', 0)}")

    # Top5
    top5 = lesson.get("top5", [])
    print("\n🏆 TOP 5")
    for i, t in enumerate(top5, 1):
        print(f"  {i}. {t['ticker']:6s} | Intraday={t['intraday_score']:.1f} | Swing={t['swing_score']:.1f} | {t['trade_type']}")

    # Changes
    changes = lesson.get("changes_vs_yesterday", {})
    if changes:
        print("\n📈 CHANGES VS YESTERDAY")
        for key, val in changes.items():
            print(f"  {key}: {val['previous']} → {val['current']} ({val['direction']})")

    # Recommendations
    recommendations = lesson.get("recommendations", [])
    if recommendations:
        print("\n💡 RECOMMENDATIONS")
        for rec in recommendations:
            print(f"  • {rec}")

    print("\n" + "="*74)
