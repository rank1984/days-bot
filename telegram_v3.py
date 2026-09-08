"""
telegram_v3.py – V5.0.1 Telegram Formatter
Early Move display + Daily Lesson
"""
import requests
from datetime import datetime
import pytz

ET = pytz.timezone("America/New_York")


def send_message(token: str, chat_id: str, text: str) -> bool:
    """Send a Telegram message with fallback from HTML to plain text."""
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
        except Exception:
            continue
    return False


def format_research_report(candidates: list, now_et: datetime) -> str:
    """
    Research report with Early Move scores, state, components, and action.
    """
    lines = []
    lines.append("━━━━━━━━━━━━━━━━━━━━")
    lines.append("🚀 DAYS-BOT V5.0.1 – EARLY MOVE SCAN")
    lines.append(f"📅 {now_et.strftime('%d/%m/%Y')} | 🕐 {now_et.strftime('%H:%M')} ET")
    lines.append("━━━━━━━━━━━━━━━━━━━━")

    if not candidates:
        lines.append("😴 לא נמצאו מועמדים למסחר")
        lines.append("⏳ הסריקה הבאה בעוד 15 דקות")
        lines.append("━━━━━━━━━━━━━━━━━━━━")
        lines.append("⚠️ ביצוע ידני בלבד")
        return "\n".join(lines)

    # Sort by composite score (legacy) for display
    top5 = sorted(candidates, key=lambda x: x.get('composite_score', 0), reverse=True)[:5]

    lines.append("")
    lines.append("━━━━━━━━━━━━━━━━━━━━")
    lines.append("🏆 TOP 5 – EARLY MOVE ANALYSIS")
    lines.append("━━━━━━━━━━━━━━━━━━━━")

    for i, c in enumerate(top5, 1):
        ticker = c.get('ticker', 'UNKNOWN')
        price = c.get('price', 0)
        gap = c.get('gap_pct', 0)
        pm_volume = c.get('pm_volume', 0)

        early_score = c.get('early_score', 0)
        early_state = c.get('early_state', 'UNKNOWN')
        components = c.get('early_components', {})
        data_status = c.get('data_status', 'UNKNOWN')

        lines.append(f"{i}️⃣ {ticker}")
        lines.append(f"  Early Move: {early_score:.0f}/100")
        lines.append(f"  State: {early_state}")
        lines.append(f"  Price: ${price:.2f} | Gap: {gap:+.1f}% | Vol: {pm_volume:,}")

        # Behavioral components
        if components:
            comp_str = []
            if components.get('pullback_buying', 0) > 40:
                comp_str.append("✅ Pullback Buying")
            if components.get('pmh_pressure', 0) > 40:
                comp_str.append("✅ PMH Pressure")
            if components.get('volume_acceleration', 0) > 40:
                comp_str.append("✅ Volume Accel")
            if components.get('price_acceleration', 0) > 40:
                comp_str.append("✅ Price Accel")
            if components.get('vwap_control', 0) > 40:
                comp_str.append("✅ Above VWAP")
            if comp_str:
                lines.append("  Behavior: " + " | ".join(comp_str))

        # Data status
        if data_status == "ACTIONABLE":
            lines.append("  Data: ✅ Complete")
        elif data_status == "WATCH":
            missing = c.get('data_completeness', {}).get('missing', [])
            lines.append(f"  Data: 🟡 Missing: {', '.join(missing)}")
        else:
            lines.append("  Data: 🔴 Insufficient")

        # Action suggestion
        if early_state in ["PRESSURE", "BREAKOUT_SETUP"] and early_score > 60:
            lines.append("  🟠 ACTION: WATCH PMH")
        elif early_state == "BREAKOUT" and early_score > 70:
            lines.append("  🟢 ACTION: PREPARE ENTRY")
        elif early_state in ["MOMENTUM", "EXTENSION"]:
            lines.append("  🟡 ACTION: MONITOR (already moving)")
        else:
            lines.append("  🔵 ACTION: WAIT")

        lines.append("")

    # Best early setup
    actionable = [
        c for c in top5
        if c.get('early_state') in ['BREAKOUT_SETUP', 'BREAKOUT', 'PRESSURE']
        and c.get('early_score', 0) > 60
        and c.get('data_status') == 'ACTIONABLE'
    ]

    if actionable:
        lines.append("━━━━━━━━━━━━━━━━━━━━")
        lines.append("✅ BEST EARLY SETUP")
        best = actionable[0]
        lines.append(f"{best['ticker']} – {best.get('early_state', 'UNKNOWN')} ({best.get('early_score', 0):.0f}/100)")
        lines.append(f"  Entry: ${best.get('entry', 0):.2f} | Stop: ${best.get('stop', 0):.2f}")
        lines.append(f"  T1: ${best.get('target_1', 0):.2f} | T2: ${best.get('target_2', 0):.2f}")
        lines.append("  Watch PMH break for confirmation.")
    else:
        lines.append("━━━━━━━━━━━━━━━━━━━━")
        lines.append("⏳ NO ACTIVE EARLY SETUPS")
        if any(c.get('early_score', 0) > 50 for c in top5):
            lines.append("Some candidates show early signs but lack confirmation.")
        else:
            lines.append("No candidate is showing sufficient behavioral pressure.")

    lines.append("")
    lines.append("⏳ Next scan: 09:30 ET")
    lines.append("━━━━━━━━━━━━━━━━━━━━")
    lines.append("⚠️ MANUAL EXECUTION ONLY")
    return "\n".join(lines)


def format_lesson_for_telegram(lesson: dict) -> str:
    """Format daily lesson in Hebrew."""
    lines = []
    lines.append("━━━━━━━━━━━━━━━━━━━━")
    lines.append("📚 DAYS-BOT V5.0.1 – לקח יומי")
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
    if top5:
        lines.append("")
        lines.append("🏆 חמשת המובילים:")
        for i, t in enumerate(top5, 1):
            type_hebrew = {
                "INTRADAY": "יומי",
                "SWING_1_3D": "Swing",
                "BOTH": "שניהם",
                "WATCH": "מעקב",
                "NO_TRADE": "אין מסחר"
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