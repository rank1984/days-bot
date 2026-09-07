"""
telegram_v3.py – V4.3 Telegram Formatter (Improved Hebrew)
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


def _rvol_display(rvol, status):
    if rvol is not None:
        return f"{rvol:.2f}x"
    if status == "TIME_ADJUSTED":
        return f"{rvol:.2f}x (מותאם)"
    return "לא זמין (חסרים נתונים היסטוריים)"


def _spread_display(spread):
    if spread is None or spread == "UNAVAILABLE":
        return "לא זמין"
    if spread > 2.0:
        return f"{spread:.2f}% ⚠️ (סיכון גבוה)"
    return f"{spread:.2f}%"


def _sec_display(level):
    mapping = {
        "LOW": "נמוך",
        "MEDIUM": "בינוני",
        "HIGH": "גבוה ⚠️",
        "CRITICAL": "קריטי 🚨",
    }
    return mapping.get(level, level)


def _catalyst_display(catalyst_type, score):
    if catalyst_type == "UNAVAILABLE" or not catalyst_type:
        return "לא זמין"
    type_names = {
        "FDA_APPROVAL": "אישור FDA",
        "EARNINGS": "דוחות",
        "CONTRACT": "חוזה",
        "PARTNERSHIP": "שותפות",
        "M&A": "מיזוג/רכישה",
        "STRONG": "חזק",
        "WEAK": "חלש",
        "GENERAL": "כללי",
        "NO_NEWS": "אין חדשות"
    }
    name = type_names.get(catalyst_type, catalyst_type)
    return f"{name} (ציון: {score}/10)"


def _data_status_display(status, missing):
    if status == "ACTIONABLE":
        return "✅ כל הנתונים תקינים – מועמדת למסחר"
    elif status == "WATCH":
        missing_str = ", ".join(missing)
        return f"🟡 חסרים נתונים: {missing_str} – מעקב בלבד"
    else:
        return "🔴 חסרים נתונים קריטיים – אין מסחר"


def format_research_report(candidates: list, now_et: datetime) -> str:
    lines = []
    lines.append("━━━━━━━━━━━━━━━━━━━━")
    lines.append("🚀 DAYS-BOT V4.3 – דוח מחקר יומי")
    lines.append(f"📅 {now_et.strftime('%d/%m/%Y')} | 🕐 {now_et.strftime('%H:%M')} ET")
    lines.append("━━━━━━━━━━━━━━━━━━━━")

    if not candidates:
        lines.append("😴 לא נמצאו מועמדים למסחר")
        lines.append("⏳ הסריקה הבאה בעוד 15 דקות")
        lines.append("━━━━━━━━━━━━━━━━━━━━")
        lines.append("⚠️ ביצוע ידני בלבד")
        return "\n".join(lines)

    candidates_sorted = sorted(candidates, key=lambda x: x.get('composite_score', 0), reverse=True)
    top5 = candidates_sorted[:5]

    lines.append("")
    lines.append("━━━━━━━━━━━━━━━━━━━━")
    lines.append("🏆 חמשת המועמדים המובילים")
    lines.append("━━━━━━━━━━━━━━━━━━━━")

    for i, c in enumerate(top5, 1):
        trade_type = c.get('trade_type', 'WATCH')
        icon = "🟢" if "INTRADAY" in trade_type else "🟣" if "SWING" in trade_type else "🟡"
        intraday_score = c.get('composite_score', 0)
        swing_score = c.get('swing_score', 0)

        type_hebrew = {
            "INTRADAY": "מסחר יומי",
            "SWING_1_3D": "החזקה 1–3 ימים",
            "BOTH": "שניהם",
            "WATCH": "מעקב",
            "NO_TRADE": "אין מסחר"
        }.get(trade_type, trade_type)

        lines.append(f"{i}️⃣ {c['ticker']}")
        lines.append(f"  ציון יומי: {intraday_score:.0f}/100 | ציון Swing: {swing_score:.0f}/100")
        lines.append(f"  סוג: {icon} {type_hebrew}")

        lines.append(f"  מחיר: ${c.get('price', 0):.2f} | גאפ: {c.get('gap_pct', 0):+.1f}%")
        lines.append(f"  נפח טרום-מסחר: {c.get('pm_volume', 0):,}")

        # Data Status
        completeness = c.get('data_completeness', {})
        status = completeness.get('status', 'NO_TRADE')
        missing = completeness.get('missing', [])
        lines.append(f"  סטטוס נתונים: {_data_status_display(status, missing)}")

        pm_quality = c.get('pm_data_quality', 'UNKNOWN')
        if pm_quality == "SNAPSHOT_DATA":
            pm_quality = "✅ נתוני רגע"
        elif pm_quality == "GOOD_DATA":
            pm_quality = "✅ טובים"
        elif pm_quality == "LOW_DATA":
            pm_quality = "⚠️ חלקיים"
        else:
            pm_quality = "❌ לא זמינים"
        lines.append(f"  איכות נתונים: {pm_quality}")

        rvol = c.get('rvol')
        rvol_status = c.get('rvol_status', 'UNAVAILABLE')
        lines.append(f"  RVOL: {_rvol_display(rvol, rvol_status)}")

        spread = c.get('spread_pct')
        lines.append(f"  מרווח (Spread): {_spread_display(spread)}")

        catalyst_type = c.get('catalyst_type', 'UNAVAILABLE')
        catalyst_score = c.get('catalyst_score', 0)
        lines.append(f"  זרז (Catalyst): {_catalyst_display(catalyst_type, catalyst_score)}")

        float_val = c.get('float')
        short = c.get('short_interest')
        if float_val:
            lines.append(f"  Float: {float_val:,.0f}")
        if short:
            lines.append(f"  Short Interest: {short*100:.1f}%")

        sec_level = c.get('sec_risk_level', 'LOW')
        lines.append(f"  סיכון SEC: {_sec_display(sec_level)}")

        if c.get('plan_valid', False):
            lines.append(f"  כניסה: ${c.get('entry', 0):.2f} | סטופ: ${c.get('stop', 0):.2f}")
            lines.append(f"  יעד 1: ${c.get('target_1', 0):.2f} | יעד 2: ${c.get('target_2', 0):.2f}")
            lines.append(f"  מניות: {c.get('position_size', 0)} | הפסד מקס': ${c.get('max_loss', 0):.2f}")
        else:
            plan_error = c.get('plan_error', 'אין תוכנית מסחר תקפה')
            lines.append(f"  ⚠️ {plan_error}")

        if c.get('sec_risk_level') == 'HIGH':
            lines.append("  🚨 סיכון SEC גבוה – אין לבצע עסקה")

        lines.append("")

    # Best Swing
    swing_best = next((c for c in top5 if c.get('trade_type') in ['SWING_1_3D', 'BOTH'] and c.get('data_status') == 'ACTIONABLE'), None)
    if swing_best:
        lines.append("━━━━━━━━━━━━━━━━━━━━")
        lines.append("🟣 המועמדת המובילה להחזקה 1–3 ימים")
        lines.append("━━━━━━━━━━━━━━━━━━━━")
        lines.append(f"{swing_best['ticker']}")
        lines.append(f"ציון Swing: {swing_best.get('swing_score', 0):.0f}/100")
        lines.append(f"כניסה: ${swing_best.get('entry', 0):.2f}")
        lines.append(f"סטופ:  ${swing_best.get('stop', 0):.2f}")
        lines.append(f"יעד 1: ${swing_best.get('target_1', 0):.2f}")
        lines.append(f"יעד 2: ${swing_best.get('target_2', 0):.2f}")
        lines.append("")
        if swing_best.get('sec_risk_level') == 'HIGH':
            lines.append("🚨 סיכון SEC גבוה – אין לבצע עסקה")
        lines.append("")

    # Watchlist
    watch_candidates = [c for c in top5 if c.get('trade_type') == 'WATCH' or c.get('data_status') == 'WATCH']
    if watch_candidates:
        lines.append("━━━━━━━━━━━━━━━━━━━━")
        lines.append("🟡 רשימת מעקב")
        lines.append("━━━━━━━━━━━━━━━━━━━━")
        for c in watch_candidates[:3]:
            lines.append(f"• {c['ticker']} – {c.get('composite_score', 0):.0f}/100 (מעקב בלבד)")
        lines.append("")

    # Final Decision
    actionable = [c for c in top5 if c.get('data_status') == 'ACTIONABLE' and c.get('trade_type') in ['INTRADAY', 'SWING_1_3D', 'BOTH']]
    if actionable:
        lines.append("━━━━━━━━━━━━━━━━━━━━")
        lines.append("✅ החלטה: נמצאו מועמדויות למסחר")
        lines.append("")
        best = actionable[0]
        lines.append(f"📌 המועמדת המובילה: {best['ticker']} (Swing {best.get('swing_score', 0):.0f})")
        if len(actionable) > 1:
            lines.append(f"📌 מועמדת נוספת: {actionable[1]['ticker']} (Swing {actionable[1].get('swing_score', 0):.0f})")
        lines.append("")
        lines.append("💡 בצע בדיקה ידנית לפני כניסה לעסקה.")
    else:
        lines.append("━━━━━━━━━━━━━━━━━━━━")
        lines.append("🚫 החלטה: אין מסחר היום")
        lines.append("אף מועמד לא עבר את רף האיכות או שחסרים נתונים קריטיים.")
        lines.append("חמשת המועמדים המובילים הם החזקים ביותר שנמצאו.")

    lines.append("")
    lines.append("⏳ הסריקה הבאה: 09:30 ET")
    lines.append("━━━━━━━━━━━━━━━━━━━━")
    lines.append("⚠️ ביצוע ידני בלבד – הבוט אינו מבצע פקודות")
    return "\n".join(lines)


def format_lesson_for_telegram(lesson: dict) -> str:
    lines = []
    lines.append("━━━━━━━━━━━━━━━━━━━━")
    lines.append("📚 DAYS-BOT V4.3 – לקח יומי")
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
    lines.append(f"  נפסלו: מחיר נמוך        {funnel.get('rejected_price_low', 0)}")
    lines.append(f"  נפסלו: מחיר גבוה        {funnel.get('rejected_price_high', 0)}")

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
        lines.append(f"  {i}. {t['ticker']:6s} | יומי={t['intraday_score']:.0f} | Swing={t['swing_score']:.0f} | {type_hebrew}")

    changes = lesson.get("changes_vs_yesterday", {})
    if changes:
        lines.append("")
        lines.append("📈 שינויים מאתמול:")
        for key, val in list(changes.items())[:4]:
            arrow = "🔼" if val['direction'] == "up" else "🔽"
            lines.append(f"  {key}: {val['previous']} → {val['current']} {arrow}")

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