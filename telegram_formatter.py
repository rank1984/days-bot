"""
Telegram Formatter Module for DAYS-BOT V2.2 (HTML mode + Hebrew Support)
"""
import requests
from datetime import datetime
from typing import Dict, Any, List
import pytz

ET = pytz.timezone("America/New_York")


def send_message(token: str, chat_id: str, text: str) -> bool:
    """שליחת הודעה לטלגרם בפורמט HTML"""
    if not token or not chat_id:
        print("[Telegram] ⚠️ Token or Chat ID missing.")
        return False

    url = f"https://api.telegram.org/bot{token}/sendMessage"
    payload = {
        "chat_id": chat_id,
        "text": text,
        "parse_mode": "HTML",
        "disable_web_page_preview": True
    }
    try:
        resp = requests.post(url, json=payload, timeout=30)
        if resp.status_code == 200:
            return True
        print(f"[Telegram] Failed. Status: {resp.status_code}, Response: {resp.text}")
        return False
    except Exception as e:
        print(f"[Telegram] Error sending message: {e}")
        return False


def format_quant_report_v22(candidates: List[Dict[str, Any]], date: str) -> str:
    """פורמט דוח קוואנט V2.2 מעודכן"""
    time_str = datetime.now(ET).strftime("%H:%M ET")
    lines = [
        "🔥 <b>DAYS-BOT V2.2 — QUANT SCAN</b>",
        f"📅 {date}  |  🕐 {time_str}",
        "━━━━━━━━━━━━━━━━━━",
    ]

    states = {}
    for c in candidates:
        st = c.get('state', 'REJECT')
        states[st] = states.get(st, 0) + 1

    lines.append(f"📊 EARLY: {states.get('EARLY', 0)} | WATCH: {states.get('WATCH', 0)} | PREPARE: {states.get('PREPARE', 0)}")
    lines.append(f"📊 READY: {states.get('READY', 0)} | EXTENDED: {states.get('EXTENDED', 0)} | REJECTED: {states.get('REJECT', 0)}")
    lines.append("━━━━━━━━━━━━━━━━━━")

    for i, r in enumerate(candidates[:5], 1):
        ticker = r.get('ticker', '???')
        price = r.get('price', 0.0)
        gap = r.get('gap_pct', 0.0)
        rvol = r.get('rvol', 0.0)
        rvol_method = r.get('rvol_method', 'DAILY_FALLBACK')
        state = r.get('state', 'UNKNOWN')
        event_score = r.get('event_score', 0)
        grade = r.get('grade', r.get('setup_grade', '?'))
        risk = r.get('dilution_risk', 'UNKNOWN')
        float_shares = r.get('float_shares') or r.get('float')
        float_turnover = r.get('float_turnover')
        dvol = r.get('dollar_volume', 0.0)
        catalyst = r.get('catalyst', '—')
        pm_dist = r.get('pm_high_dist', 999.0)
        spread = r.get('spread_pct', 0.0)

        float_str = f"{float_shares / 1_000_000:.1f}M" if float_shares else "UNKNOWN"
        turnover_str = f"{float_turnover:.1f}x" if float_turnover else "UNKNOWN"
        dvol_str = f"${dvol / 1_000_000:.1f}M" if dvol >= 1_000_000 else f"${dvol / 1_000:.0f}K"

        lines.append("")
        lines.append(f"<b>{i}. {ticker}</b>  💰 ${price:.2f}  Gap: {gap:+.1f}%")
        lines.append(f"   🎯 Event Score: {event_score}  |  Grade: {grade}  |  Risk: {risk}")
        lines.append(f"   📊 RVOL: {rvol:.1f}x ({rvol_method})  |  PM Dist: {pm_dist:.1f}%")
        lines.append(f"   🏷️ Float: {float_str}  |  Turnover: {turnover_str}  |  DVol: {dvol_str}")
        lines.append(f"   📰 Catalyst: {catalyst[:40] if catalyst != '—' else '—'}")
        lines.append(f"   🔵 State: <b>{state}</b>  |  Spread: {spread:.1f}%")

    lines += [
        "",
        "━━━━━━━━━━━━━━━━━━",
        "⚡ READY = Trigger + RVOL + execution filters",
        "🏆 A/A+ = setup quality only, NOT an entry signal",
        "🚫 NO CHASE = large gaps require fresh trigger",
        "🚫 לא המלצת השקעה"
    ]
    return "\n".join(lines)


def format_watchlist(watchlist: list, date: str) -> str:
    """פורמט תצוגה מותאם ל-Watchlist בעברית"""
    time_str = datetime.now(ET).strftime("%H:%M ET")
    if not watchlist:
        return f"📋 <b>DAYS-BOT - רשימת מעקב</b>\n📅 {date}  |  🕐 {time_str}\n━━━━━━━━━━━━━━━━━━\n😴 אין מועמדויות פעילות."

    lines = [
        "📋 <b>DAYS-BOT - רשימת מעקב</b>",
        f"📅 {date}  |  🕐 {time_str}",
        f"📊 {len(watchlist)} מועמדויות | {sum(1 for w in watchlist if w.get('status') == 'READY')} מוכנות",
        "━━━━━━━━━━━━━━━━━━",
    ]

    for i, w in enumerate(watchlist[:10], 1):
        ticker = w.get('ticker', '???')
        price = w.get('price', 0.0)
        gap = w.get('gap_pct', 0.0)
        status = w.get('status', 'WATCH')
        score = w.get('event_score', w.get('score', 0))
        grade = w.get('grade', w.get('setup_grade', '?'))
        rvol = w.get('rvol', 0.0)
        float_shares = w.get('float_shares') or w.get('float') or 0
        float_turnover = w.get('float_turnover')
        dilution_risk = w.get('dilution_risk', 'UNKNOWN')
        catalyst = w.get('catalyst', '')

        if status == 'READY':
            status_icon = "🟢 מוכנה"
        elif status == 'PREPARE':
            status_icon = "🟡 בהכנה"
        else:
            status_icon = "🔵 במעקב"

        float_str = f"{float_shares / 1_000_000:.1f}M" if float_shares > 0 else "❓"
        turnover_str = f"{float_turnover:.1f}x" if float_turnover else "❓"

        lines.append("")
        lines.append(f"<b>{i}. {ticker}</b>  💰 ${price:.2f}  Gap: {gap:+.1f}%")
        lines.append(f"   🎯 ציון אירוע: {score:.0f}/100  |  דירוג: {grade}")
        lines.append(f"   📊 RVOL: {rvol:.1f}x  |  Float: {float_str}  |  מחזור: {turnover_str}")
        lines.append(f"   {status_icon}  |  סיכון: {dilution_risk}")
        if catalyst:
            lines.append(f"   📰 {catalyst[:50]}")

    lines += [
        "",
        "━━━━━━━━━━━━━━━━━━",
        "⚡ מוכנה = Trigger + RVOL מאושר",
        "🚀 כניסה רק בפריצה עם נפח",
        "🚫 לא המלצת השקעה"
    ]
    return "\n".join(lines)


def format_no_candidates(date: str, universe_size: int = 0) -> str:
    """הודעה כאשר אין מועמדויות"""
    time_str = datetime.now(ET).strftime("%H:%M ET")
    return (
        f"🎯 <b>DAYS-BOT - מועמדויות לפריצה</b>\n"
        f"📅 {date}  |  🕐 {time_str}\n"
        f"━━━━━━━━━━━━━━━━━━\n"
        f"🔍 נסרקו: {universe_size} מניות\n"
        f"😴 אין מועמדויות איכותיות היום\n"
        f"━━━━━━━━━━━━━━━━━━\n"
        f"⏰ בדיקה חוזרת מחר ב-14:30"
    )
