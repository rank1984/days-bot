"""
Telegram formatter – V2.8 (Scan Breakdown + Review)
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


def format_scan_breakdown(candidates: list, stats: dict, date: str) -> str:
    """
    Displays discovery and validation breakdown + top candidates.
    """
    time_str = datetime.now(ET).strftime("%H:%M ET")
    lines = [
        "🎯 <b>DAYS-BOT V2.8 — PREMARKET SCAN</b>",
        f"📅 {date}  |  🕐 {time_str}",
        "━━━━━━━━━━━━━━━━━━",
        "🔎 <b>DISCOVERY</b>",
        f"Price passed:       {stats.get('price_pass', 0):,}",
        f"Gap passed:         {stats.get('gap_pass', 0):,}",
        f"Volume passed:      {stats.get('vol_pass', 0):,}",
        f"Spread known:       {stats.get('spread_pass', 0):,}",
        f"Fast Filter Pass:   {stats.get('fast_pass', 0):,}",
        "━━━━━━━━━━━━━━━━━━",
        "🔬 <b>VALIDATION</b>",
        f"PM Volume Pass:     {stats.get('pm_vol_pass', 0):,}",
        f"RVOL Pass:          {stats.get('rvol_pass', 0):,}",
        f"PM Dist Pass:       {stats.get('pm_dist_pass', 0):,}",
        f"VWAP Pass:          {stats.get('vwap_pass', 0):,}",
        f"PM Quant Pass:      {stats.get('pm_quant_pass', 0):,}",
        "━━━━━━━━━━━━━━━━━━",
        "📰 <b>CATALYST</b>",
        f"Catalyst Pass:      {stats.get('catalyst_pass', 0):,}",
        f"✅ FINAL CANDIDATES: {stats.get('final_pass', 0):,}",
        "━━━━━━━━━━━━━━━━━━",
        "🏆 <b>TOP CANDIDATES</b>",
    ]

    for i, c in enumerate(candidates[:5], 1):
        ticker = c.get('ticker', '???')
        price = c.get('price', 0)
        gap = c.get('gap_pct', 0)
        rvol = c.get('rvol_time_adj', 0)
        lines.append(f"{i}. <b>{ticker}</b>  💰 ${price:.2f}  Gap: {gap:+.1f}%  RVOL: {rvol:.1f}x")

    lines += [
        "━━━━━━━━━━━━━━━━━━",
        f"🟢 QUALIFIED: {len([c for c in candidates if c.get('state')=='QUALIFIED'])}",
        f"🟡 PREPARE:   {len([c for c in candidates if c.get('state')=='PREPARE'])}",
        f"🔵 WATCH:     {len([c for c in candidates if c.get('state')=='WATCH'])}",
        "━━━━━━━━━━━━━━━━━━",
        "⚠️ <b>MANUAL REVIEW IN BLINK</b>",
        "🚫 BOT DOES NOT EXECUTE",
        "🚫 לא המלצת השקעה"
    ]
    return "\n".join(lines)


def format_quant_report_v27(candidates: list, date: str) -> str:
    """Legacy quant report – kept for compatibility."""
    return format_scan_breakdown(candidates, {}, date)


def format_review_v27(reviews: list, date: str) -> str:
    """Detailed review for READY candidates."""
    time_str = datetime.now(ET).strftime("%H:%M ET")
    lines = [
        "🔥 <b>DAYS-BOT V2.8 — READY FOR REVIEW</b>",
        f"📅 {date}  |  🕐 {time_str}",
        "━━━━━━━━━━━━━━━━━━",
        f"📊 {len(reviews)} candidates passed all filters",
        "━━━━━━━━━━━━━━━━━━",
    ]

    for i, r in enumerate(reviews[:3], 1):
        c = r.get('candidate', {})
        ticker = c.get('ticker', '???')
        price = c.get('price', 0)
        gap = c.get('gap_pct', 0)
        rvol = c.get('rvol_time_adj', 0)
        spread = c.get('spread_pct')
        spread_str = f"{spread:.2f}%" if spread is not None else "UNKNOWN"
        catalyst = c.get('catalyst', '—')
        pm_high = c.get('pm_high', 0)
        pm_dist = c.get('pm_high_dist', 999)
        vwap = c.get('pm_vwap', 0)

        entry = r.get('entry', 0)
        stop = r.get('stop', 0)
        tp1 = r.get('tp1', 0)
        tp2 = r.get('tp2', 0)
        rr1 = r.get('rr1', 0)
        rr2 = r.get('rr2', 0)
        net1 = r.get('net1', {})
        net2 = r.get('net2', {})

        lines.append("")
        lines.append(f"<b>{i}. {ticker}</b>  💰 ${price:.2f}  Gap: {gap:+.1f}%")
        lines.append(f"   📊 RVOL: {rvol:.1f}x  |  Spread: {spread_str}")
        lines.append(f"   📏 PM High: ${pm_high:.2f}  |  PM Dist: {pm_dist:.1f}%")
        lines.append(f"   💵 VWAP: ${vwap:.2f}  |  📰 Catalyst: {catalyst[:40] if catalyst != '—' else '—'}")
        lines.append("")
        lines.append(f"   🎯 ENTRY: ${entry:.2f}")
        lines.append(f"   🛑 STOP:  ${stop:.2f}  (-{((entry-stop)/entry)*100:.1f}%)")
        lines.append(f"   🎯 TP1:   ${tp1:.2f}  (+{((tp1-entry)/entry)*100:.1f}%)  RR: {rr1:.2f}")
        lines.append(f"   🎯 TP2:   ${tp2:.2f}  (+{((tp2-entry)/entry)*100:.1f}%)  RR: {rr2:.2f}")
        lines.append("")
        if net1:
            lines.append(f"   📊 Net TP1: {net1.get('net_pct', 0):.1f}%  |  Net TP2: {net2.get('net_pct', 0):.1f}%")
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
    """Standard watchlist display."""
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

        if state == 'QUALIFIED':
            status_icon = "🟢 QUALIFIED"
        elif state == 'PREPARE':
            status_icon = "🟡 PREPARE"
        elif state == 'BREAKOUT':
            status_icon = "🔴 BREAKOUT"
        elif state == 'WATCH':
            status_icon = "🔵 WATCH"
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
        "🟢 QUALIFIED = SETUP WORTH YOUR MANUAL REVIEW",
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
