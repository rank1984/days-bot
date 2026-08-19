"""
Telegram formatter – V2.7 (Quant Report + Review)
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


def format_quant_report_v27(candidates: list, date: str) -> str:
    time_str = datetime.now(ET).strftime("%H:%M ET")
    lines = [
        "🔥 <b>DAYS-BOT V2.7 — QUANT SCAN</b>",
        f"📅 {date}  |  🕐 {time_str}",
        "━━━━━━━━━━━━━━━━━━",
    ]

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
        rvol = r.get('rvol', r.get('rvol_time_adj', 0))
        rvol_method = r.get('rvol_method', 'FALLBACK')
        state = r.get('state', 'UNKNOWN')
        event_score = r.get('event_score', 0)
        final_score = r.get('final_score', 0)
        grade = r.get('grade', '?')
        risk = r.get('risk', 0)
        catalyst = r.get('catalyst', '—')
        dvol = r.get('dollar_volume', 0)
        pm_high = r.get('pm_high', 0)
        pm_high_dist = r.get('pm_high_dist', 999)
        vwap = r.get('pm_vwap', 0)
        spread = r.get('spread_pct')
        spread_str = f"{spread:.2f}%" if spread is not None else "UNKNOWN"
        building_state = r.get('building_state', '—')
        prev_day_return = r.get('prev_day_return', 0)

        dvol_str = f"${dvol/1_000_000:.1f}M" if dvol >= 1_000_000 else f"${dvol/1_000:.0f}K"

        lines.append("")
        lines.append(f"<b>{i}. {ticker}</b>  💰 ${price:.2f}  Gap: {gap:+.1f}%")
        lines.append(f"   🎯 Event: {event_score}  |  Final: {final_score}  |  Grade: {grade}")
        lines.append(f"   📊 RVOL: {rvol:.1f}x ({rvol_method})  |  Risk: {risk:.0f}")
        lines.append(f"   📈 Prev Day: {prev_day_return:+.1f}%  |  🏗️ {building_state}")
        lines.append(f"   📏 PM High: ${pm_high:.2f}  |  PM Dist: {pm_high_dist:.1f}%")
        lines.append(f"   💵 VWAP: ${vwap:.2f}  |  DVol: {dvol_str}  |  Spread: {spread_str}")
        lines.append(f"   📰 Catalyst: {catalyst[:40] if catalyst != '—' else '—'}")
        lines.append(f"   🔵 State: <b>{state}</b>")

    lines += [
        "",
        "━━━━━━━━━━━━━━━━━━",
        "🟢 READY = SETUP WORTH YOUR MANUAL REVIEW",
        "⚠️ BOT DOES NOT EXECUTE – MANUAL CONFIRMATION REQUIRED",
        "🚫 NO CHASE – large gaps require fresh trigger",
        "🚫 לא המלצת השקעה"
    ]
    return "\n".join(lines)


def format_review_v27(reviews: list, date: str) -> str:
    time_str = datetime.now(ET).strftime("%H:%M ET")
    lines = [
        "🔥 <b>DAYS-BOT V2.7 — READY FOR REVIEW</b>",
        f"📅 {date}  |  🕐 {time_str}",
        "━━━━━━━━━━━━━━━━━━",
        f"📊 {len(reviews)} candidates passed all filters",
        "━━━━━━━━━━━━━━━━━━",
    ]

    for i, r in enumerate(reviews[:3], 1):  # max 3
        c = r['candidate']
        ticker = c['ticker']
        price = c['price']
        gap = c['gap_pct']
        rvol = c.get('rvol', c.get('rvol_time_adj', 0))
        spread = c.get('spread_pct')
        spread_str = f"{spread:.2f}%" if spread is not None else "UNKNOWN"
        catalyst = c.get('catalyst', '—')
        pm_high = c.get('pm_high', 0)
        pm_dist = c.get('pm_high_dist', 999)
        vwap = c.get('pm_vwap', 0)
        event_score = c.get('event_score', 0)
        final_score = c.get('final_score', 0)

        entry = r['entry']
        stop = r['stop']
        tp1 = r['tp1']
        tp2 = r['tp2']
        rr1 = r['rr1']
        rr2 = r['rr2']
        net1 = r['net1']
        net2 = r['net2']

        lines.append("")
        lines.append(f"<b>{i}. {ticker}</b>  💰 ${price:.2f}  Gap: {gap:+.1f}%")
        lines.append(f"   🎯 Final Score: {final_score:.0f}  |  Event: {event_score:.0f}")
        lines.append(f"   📊 RVOL: {rvol:.1f}x  |  Spread: {spread_str}")
        lines.append(f"   📏 PM High: ${pm_high:.2f}  |  PM Dist: {pm_dist:.1f}%")
        lines.append(f"   💵 VWAP: ${vwap:.2f}  |  📰 Catalyst: {catalyst[:40] if catalyst != '—' else '—'}")
        lines.append("")
        lines.append(f"   🎯 ENTRY: ${entry:.2f}")
        lines.append(f"   🛑 STOP:  ${stop:.2f}  (-{((entry-stop)/entry)*100:.1f}%)")
        lines.append(f"   🎯 TP1:   ${tp1:.2f}  (+{((tp1-entry)/entry)*100:.1f}%)  RR: {rr1:.2f}")
        lines.append(f"   🎯 TP2:   ${tp2:.2f}  (+{((tp2-entry)/entry)*100:.1f}%)  RR: {rr2:.2f}")
        lines.append("")
        lines.append(f"   📊 Net TP1: {net1['net_pct']:.1f}%  |  Net TP2: {net2['net_pct']:.1f}%")
        lines.append("   ───────────────────")
        lines.append(f"   ✅ All hard filters passed")
        lines.append(f"   ⚠️ <b>MANUAL EXECUTION REQUIRED</b>")

    lines += [
        "",
        "━━━━━━━━━━━━━━━━━━",
        "⚠️ BOT DOES NOT EXECUTE – YOU MUST BUY/SELL MANUALLY",
        "🚫 NO CHASE – verify price, volume, spread in BLINK",
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
        final_score = w.get('final_score', 0)
        grade = w.get('grade', '?')
        rvol = w.get('rvol', 0)
        catalyst = w.get('catalyst', '—')
        pm_high_dist = w.get('pm_high_dist', 999)
        spread = w.get('spread_pct')
        spread_str = f"{spread:.2f}%" if spread is not None else "UNKNOWN"

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

        lines.append("")
        lines.append(f"<b>{i}. {ticker}</b>  💰 ${price:.2f}  Gap: {gap:+.1f}%")
        lines.append(f"   🎯 ציון: {final_score:.0f}  |  Grade: {grade}  |  RVOL: {rvol:.1f}x")
        lines.append(f"   📏 PM Dist: {pm_high_dist:.1f}%  |  Spread: {spread_str}")
        lines.append(f"   📰 Catalyst: {catalyst[:30] if catalyst != '—' else '—'}")
        lines.append(f"   {status_icon}")

    lines += [
        "",
        "━━━━━━━━━━━━━━━━━━",
        "🟢 READY = SETUP WORTH YOUR MANUAL REVIEW",
        "⚠️ MANUAL CONFIRMATION REQUIRED",
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
