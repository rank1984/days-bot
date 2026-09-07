"""
DAYS-BOT V4.4 – Telegram Formatter (with Dynamic Scores)
"""
import requests
from datetime import datetime
import pytz

ET = pytz.timezone("America/New_York")


def send_message(token: str, chat_id: str, text: str) -> bool:
    if not token or not chat_id:
        return False
    url = f"https://api.telegram.org/bot{token}/sendMessage"
    for parse_mode in ["HTML", None]:
        try:
            payload = {
                "chat_id": chat_id,
                "text": text,
                "disable_web_page_preview": True,
            }
            if parse_mode:
                payload["parse_mode"] = parse_mode
            resp = requests.post(url, json=payload, timeout=30)
            if resp.status_code == 200:
                return True
        except:
            continue
    return False


def format_research_report(candidates: list, now_et: datetime) -> str:
    lines = []
    lines.append("━━━━━━━━━━━━━━━━━━━━")
    lines.append("🚀 DAYS-BOT V4.4 – דוח מחקר יומי")
    lines.append(f"📅 {now_et.strftime('%d/%m/%Y')} | 🕐 {now_et.strftime('%H:%M')} ET")
    lines.append("━━━━━━━━━━━━━━━━━━━━")

    if not candidates:
        lines.append("😴 לא נמצאו מועמדים למסחר")
        lines.append("⏳ הסריקה הבאה בעוד 15 דקות")
        lines.append("━━━━━━━━━━━━━━━━━━━━")
        lines.append("⚠️ ביצוע ידני בלבד")
        return "\n".join(lines)

    top5 = sorted(candidates, key=lambda x: x.get('composite_score', 0), reverse=True)[:5]

    lines.append("")
    lines.append("━━━━━━━━━━━━━━━━━━━━")
    lines.append("🏆 TOP 5")
    lines.append("━━━━━━━━━━━━━━━━━━━━")

    for i, c in enumerate(top5, 1):
        trade_type = c.get('trade_type', 'WATCH')
        icon = "🟢" if "INTRADAY" in trade_type else "🟣" if "SWING" in trade_type else "🟡"

        # Get scores (try dynamic first, fallback to old)
        day_score = c.get('day_trade_score', c.get('composite_score', 0))
        swing_score = c.get('swing_score', 0)
        early_score = c.get('early_score', 0)
        early_state = c.get('early_state', 'UNKNOWN')

        type_hebrew = {
            "INTRADAY": "מסחר יומי",
            "SWING_1_3D": "החזקה 1–3 ימים",
            "BOTH": "שניהם",
            "WATCH": "מעקב",
            "NO_TRADE": "אין מסחר"
        }.get(trade_type, trade_type)

        lines.append(f"{i}️⃣ {c['ticker']}")
        lines.append(f"  סטטוס: {early_state} (Early: {early_score:.0f}/100)")
        lines.append(f"  Day Trade: {day_score:.0f}/100 | Swing: {swing_score:.0f}/100")
        lines.append(f"  סוג: {icon} {type_hebrew}")
        lines.append(f"  מחיר: ${c.get('price', 0):.2f} | גאפ: {c.get('gap_pct', 0):+.1f}%")
        lines.append(f"  נפח PM: {c.get('pm_volume', 0):,}")

        # Data completeness
        completeness = c.get('data_completeness', {})
        status = completeness.get('status', 'NO_TRADE')
        missing = completeness.get('missing', [])
        if status == 'ACTIONABLE':
            lines.append("  סטטוס נתונים: ✅ כל הנתונים תקינים")
        elif status == 'WATCH':
            lines.append(f"  סטטוס נתונים: 🟡 חסרים: {', '.join(missing)} – מעקב")
        else:
            lines.append("  סטטוס נתונים: 🔴 חסרים נתונים קריטיים")

        # Spread
        spread = c.get('spread_pct')
        if spread is None:
            spread_str = "לא זמין"
        else:
            spread_str = f"{spread:.2f}% ⚠️" if spread > 2.0 else f"{spread:.2f}%"
        lines.append(f"  מרווח (Spread): {spread_str}")

        # Catalyst
        cat_type = c.get('catalyst_type', 'UNAVAILABLE')
        cat_score = c.get('catalyst_score', 0)
        if cat_type != "UNAVAILABLE":
            type_names = {
                "FDA_APPROVAL": "אישור FDA",
                "EARNINGS": "דוחות",
                "CONTRACT": "חוזה",
                "PARTNERSHIP": "שותפות",
                "M&A": "מיזוג",
                "STRONG": "חזק",
                "WEAK": "חלש",
                "GENERAL": "כללי",
                "NO_NEWS": "אין חדשות"
            }
            name = type_names.get(cat_type, cat_type)
            lines.append(f"  זרז: {name} (ציון: {cat_score}/10)")
        else:
            lines.append(f"  זרז: לא זמין")

        # Float & Short
        float_val = c.get('float')
        short = c.get('short_interest')
        if float_val:
            lines.append(f"  Float: {float_val:,.0f}")
        if short:
            lines.append(f"  Short Interest: {short*100:.1f}%")

        # SEC
        sec_level = c.get('sec_risk_level', 'LOW')
        sec_map = {"LOW": "נמוך", "MEDIUM": "בינוני", "HIGH": "גבוה ⚠️", "CRITICAL": "קריטי 🚨"}
        lines.append(f"  סיכון SEC: {sec_map.get(sec_level, sec_level)}")

        # Trade Plan
        if c.get('plan_valid', False):
            lines.append(f"  כניסה: ${c.get('entry', 0):.2f} | סטופ: ${c.get('stop', 0):.2f}")
            lines.append(f"  יעד 1: ${c.get('target_1', 0):.2f} | יעד 2: ${c.get('target_2', 0):.2f}")
            lines.append(f"  מניות: {c.get('position_size', 0)} | הפסד מקס': ${c.get('max_loss', 0):.2f}")
        else:
            lines.append(f"  ⚠️ {c.get('plan_error', 'אין תוכנית מסחר')}")

        lines.append("")

    # Best Day Trade
    day_best = next((c for c in top5 if c.get('trade_type') in ['INTRADAY', 'BOTH'] and c.get('data_status') == 'ACTIONABLE'), None)
    if day_best:
        lines.append("━━━━━━━━━━━━━━━━━━━━")
        lines.append("🟢 המועמדת המובילה למסחר יומי")
        lines.append("━━━━━━━━━━━━━━━━━━━━")
        lines.append(f"{day_best['ticker']}")
        lines.append(f"Day Trade Score: {day_best.get('day_trade_score', 0):.0f}/100")
        lines.append(f"State: {day_best.get('early_state', 'UNKNOWN')}")
        lines.append(f"Entry: ${day_best.get('entry', 0):.2f}")
        lines.append(f"Stop: ${day_best.get('stop', 0):.2f}")
        lines.append(f"T1: ${day_best.get('target_1', 0):.2f}")
        lines.append(f"T2: ${day_best.get('target_2', 0):.2f}")
        lines.append("")

    # Best Swing
    swing_best = next((c for c in top5 if c.get('trade_type') in ['SWING_1_3D', 'BOTH'] and c.get('data_status') == 'ACTIONABLE'), None)
    if swing_best:
        lines.append("━━━━━━━━━━━━━━━━━━━━")
        lines.append("🟣 המועמדת המובילה להחזקה 1–3 ימים")
        lines.append("━━━━━━━━━━━━━━━━━━━━")
        lines.append(f"{swing_best['ticker']}")
        lines.append(f"Swing Score: {swing_best.get('swing_score', 0):.0f}/100")
        lines.append(f"State: {swing_best.get('early_state', 'UNKNOWN')}")
        lines.append(f"Entry: ${swing_best.get('entry', 0):.2f}")
        lines.append(f"Stop: ${swing_best.get('stop', 0):.2f}")
        lines.append(f"T1: ${swing_best.get('target_1', 0):.2f}")
        lines.append(f"T2: ${swing_best.get('target_2', 0):.2f}")
        lines.append("")

    # Decision
    actionable = [c for c in top5 if c.get('data_status') == 'ACTIONABLE' and c.get('trade_type') in ['INTRADAY', 'SWING_1_3D', 'BOTH']]
    if actionable:
        lines.append("━━━━━━━━━━━━━━━━━━━━")
        lines.append("✅ החלטה: נמצאו מועמדויות למסחר")
        best = actionable[0]
        lines.append(f"📌 המועמדת המובילה: {best['ticker']} (Day {best.get('day_trade_score', 0):.0f} | Swing {best.get('swing_score', 0):.0f})")
    else:
        lines.append("━━━━━━━━━━━━━━━━━━━━")
        lines.append("🚫 החלטה: אין מסחר היום")
        lines.append("אף מועמד לא עבר את רף האיכות.")

    lines.append("")
    lines.append("⏳ הסריקה הבאה: 09:30 ET")
    lines.append("━━━━━━━━━━━━━━━━━━━━")
    lines.append("⚠️ ביצוע ידני בלבד")
    return "\n".join(lines)


def format_lesson_for_telegram(lesson: dict) -> str:
    lines = []
    lines.append("━━━━━━━━━━━━━━━━━━━━")
    lines.append("📚 DAYS-BOT V4.4 – לקח יומי")
    lines.append(f"📅 {lesson['date']} | {lesson['trading_day']}")
    lines.append("━━━━━━━━━━━━━━━━━━━━")

    funnel = lesson.get("funnel", {})
    lines.append("")
    lines.append("🔎 משפך הגילוי:")
    lines.append(f"  יקום (Universe):        {funnel.get('universe', 0)}")
    lines.append(f"  סנאפשוטים:              {funnel.get('snapshots_received', 0)}")
    lines.append(f"  מועמדים קפדניים:        {funnel.get('strict_candidates', 0)}")
    lines.append(f"  נפסלו: גאפ              {funnel.get('rejected_gap', 0)}")
    lines.append(f"  נפסלו: נפח              {funnel.get('rejected_volume', 0)}")
    top5 = lesson.get("top5", [])
    lines.append("")
    lines.append("🏆 חמשת המובילים:")
    for i, t in enumerate(top5, 1):
        type_hebrew = {
            "INTRADAY": "יומי",
            "SWING_1_3D": "Swing",
            "BOTH": "שניהם",
            "WATCH": "מעקב"
        }.get(t.get('trade_type', 'WATCH'), t.get('trade_type', 'WATCH'))
        lines.append(f"  {i}. {t['ticker']:6s} | Day={t.get('day_trade_score', t.get('intraday_score', 0)):.0f} | Swing={t.get('swing_score', 0):.0f} | {type_hebrew}")

    recommendations = lesson.get("recommendations", [])
    if recommendations:
        lines.append("")
        lines.append("💡 המלצות לשיפור:")
        for rec in recommendations[:3]:
            lines.append(f"  • {rec}")

    lines.append("")
    lines.append("━━━━━━━━━━━━━━━━━━━━")
    lines.append("🤖 DAYS-BOT – למידה יומית")
    return "\n".join(lines)
