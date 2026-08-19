"""
Telegram formatter – V2.3 STABLE (with Float & Catalyst)
"""
import requests
from datetime import datetime
from typing import Dict, Any, List
import pytz

ET = pytz.timezone("America/New_York")


def send_message(token: str, chat_id: str, text: str) -> bool:
    if not token or not chat_id:
        return False
    url = f"https://api.telegram.org/bot{token}/sendMessage"
    try:
        resp = requests.post(
            url,
            json={
                "chat_id": chat_id,
                "text": text,
                "parse_mode": "HTML",
                "disable_web_page_preview": True
            },
            timeout=30
        )
        if resp.status_code == 200:
            return True
        print(f"[Telegram] Failed: {resp.status_code}")
        return False
    except Exception as e:
        print(f"[Telegram] Error: {e}")
        return False


def format_quant_report_v23(candidates: list, date: str) -> str:
    time_str = datetime.now(ET).strftime("%H:%M ET")
    lines = [
        "🔥 <b>DAYS-BOT V2.3 — QUANT SCAN</b>",
        f"📅 {date}  |  🕐 {time_str}",
        "━━━━━━━━━━━━━━━━━━",
    ]

    # Count states
    states = {}
    for c in candidates:
        st = c.get('state', 'REJECT')
        states[st] = states.get(st, 0) + 1

    lines.append(f"📊 PRE-RUNNER: {states.get('PRE-RUNNER', 0)} | EARLY: {states.get('EARLY', 0)}")
    lines.append(f"📊 READY: {states.get('READY', 0)} | WATCH: {states.get('WATCH', 0)}")
    lines.append(f"📊 EXTENDED: {states.get('EXTENDED', 0)} | REJECTED: {states.get('REJECTED', 0)}")
    lines.append("━━━━━━━━━━━━━━━━━━")

    for i, r in enumerate(candidates[:5], 1):
        ticker = r['ticker']
        price = r['price']
        gap = r['gap_pct']
        rvol = r.get('rvol', 0)
        rvol_method = r.get('rvol_method', 'DAILY_FALLBACK')
        state = r.get('state', 'UNKNOWN')
        event_score = r.get('event_score', 0)
        grade = r.get('grade', '?')
        risk = r.get('dilution_risk', 'UNKNOWN')
        catalyst = r.get('catalyst', '—')
        dvol = r.get('dollar_volume', 0)
        building_state = r.get('building_state', '—')
        prev_day_return = r.get('prev_day_return', 0)
        prev_day_volume = r.get('prev_day_volume', 0)
        float_shares = r.get('float_shares', None)

        float_str = f"{float_shares/1_000_000:.1f}M" if float_shares and float_shares > 0 else "UNKNOWN"
        dvol_str = f"${dvol/1_000_000:.1f}M" if dvol >= 1_000_000 else f"${dvol/1_000:.0f}K"
        prev_vol_str = f"{prev_day_volume/1_000:.0f}K" if prev_day_volume >= 1_000 else str(prev_day_volume)

        lines.append("")
        lines.append(f"<b>{i}. {ticker}</b>  💰 ${price:.2f}  Gap: {gap:+.1f}%")
        lines.append(f"   🎯 Event Score: {event_score}  |  Grade: {grade}  |  Risk: {risk}")
        lines.append(f"   📊 RVOL: {rvol:.1f}x ({rvol_method})")
        if prev_day_return:
            lines.append(f"   📈 Prev Day: {prev_day_return:+.1f}%  |  Vol: {prev_vol_str}")
        lines.append(f"   🏗️ Building: {building_state}")
        lines.append(f"   💵 DVol: {dvol_str}  |  🏷️ Float: {float_str}")
        lines.append(f"   📰 Catalyst: {catalyst[:30] if catalyst != '—' else '—'}")
        lines.append(f"   🔵 State: <b>{state}</b>")

    lines += [
        "",
        "━━━━━━━━━━━━━━━━━━",
        "⚡ READY = Trigger + RVOL + execution filters",
        "🏆 A/A+ = setup quality only, NOT an entry signal",
        "🚫 PRE-RUNNER = building from yesterday, not yet a trade",
        "🚫 לא המלצת השקעה"
    ]
    return "\n".join(lines)


def format_watchlist(watchlist: list, date: str) -> str:
    time_str = datetime.now(ET).strftime("%H:%M ET")
    if not watchlist:
        return f"📋 <b>DAYS-BOT - רשימת מעקב</b>\n📅 {date}  |  🕐 {time_str}\n━━━━━━━━━━━━━━━━━━\n😴 אין מועמדויות פעילות."

    lines = [
        "📋 <b>DAYS-BOT - רשימת מעקב</b>",
        f"📅 {date}  |  🕐 {time_str}",
        f"📊 {len(watchlist)} מועמדויות",
        "━━━━━━━━━━━━━━━━━━",
    ]

    for i, w in enumerate(watchlist[:10], 1):
        ticker = w.get('ticker', '???')
        price = w.get('price', 0)
        gap = w.get('gap_pct', 0)
        state = w.get('state', 'WATCH')
        event_score = w.get('event_score', 0)
        grade = w.get('grade', '?')
        rvol = w.get('rvol', 0)
        catalyst = w.get('catalyst', '—')
        float_shares = w.get('float_shares', None)
        prev_day_return = w.get('prev_day_return', 0)

        if state == 'PRE-RUNNER':
            status_icon = "🟣 PRE-RUNNER"
        elif state == 'READY':
            status_icon = "🟢 READY"
        elif state == 'EARLY':
            status_icon = "🟡 EARLY"
        elif state == 'WATCH':
            status_icon = "🔵 WATCH"
        elif state == 'EXTENDED':
            status_icon = "🔴 EXTENDED"
        else:
            status_icon = "⚪ REJECT"

        float_str = f"{float_shares/1_000_000:.1f}M" if float_shares and float_shares > 0 else "UNKNOWN"

        lines.append("")
        lines.append(f"<b>{i}. {ticker}</b>  💰 ${price:.2f}  Gap: {gap:+.1f}%")
        lines.append(f"   🎯 ציון: {event_score}  |  Grade: {grade}  |  RVOL: {rvol:.1f}x")
        if prev_day_return:
            lines.append(f"   📈 Prev Day: {prev_day_return:+.1f}%")
        lines.append(f"   🏷️ Float: {float_str}  |  📰 Catalyst: {catalyst[:30] if catalyst != '—' else '—'}")
        lines.append(f"   {status_icon}")

    lines += [
        "",
        "━━━━━━━━━━━━━━━━━━",
        "⚡ READY = Trigger + RVOL + אישור",
        "🚀 כניסה רק בפריצה עם נפח",
        "🚫 לא המלצת השקעה"
    ]
    return "\n".join(lines)


def format_no_candidates(date: str, universe_size: int = 0) -> str:
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
