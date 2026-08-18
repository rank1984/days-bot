"""
Telegram formatter – HTML mode (safe) + Hebrew support
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
        print(f"[Telegram] Failed. Status: {resp.status_code}, Response: {resp.text}")
        return False
    except Exception as e:
        print(f"[Telegram] Error: {e}")
        return False


def format_trade_plan(plan: Dict[str, Any]) -> str:
    """עיצוב תוכנית מסחר (לא בשימוש כרגע)"""
    lines = []
    ticker = plan.get('ticker', '???')
    confidence = plan.get('confidence', '')
    entry = plan.get('entry', 0.0)
    stop = plan.get('stop', 0.0)
    tp1 = plan.get('tp1', 0.0)
    tp2 = plan.get('tp2', 0.0)
    runner = plan.get('runner', False)
    level = str(plan.get('level', 'N/A')).upper()
    score = plan.get('score', 0)
    rvol = plan.get('rvol', 0.0)

    tp1_pct = ((tp1 / entry) - 1) * 100 if entry > 0 else 0
    tp2_pct = ((tp2 / entry) - 1) * 100 if entry > 0 else 0
    stop_pct = ((1 - (stop / entry)) * 100) if entry > 0 else 5.0

    lines.append(f"🎯 <b>{ticker}</b>  {confidence}")
    lines.append(f"💰 כניסה: ${entry:.2f}")
    lines.append(f"🛑 סטופ:  ${stop:.2f}  (-{stop_pct:.0f}%)")
    lines.append(f"🎯 TP1:   ${tp1:.2f}  (+{tp1_pct:.0f}%)")
    lines.append(f"🎯 TP2:   ${tp2:.2f}  (+{tp2_pct:.0f}%)")
    lines.append(f"🏃 Runner: {'כן' if runner else 'לא'}")
    lines.append(f"📊 Level: {level}  |  Score: {score:.0f}  |  RVOL: {rvol:.1f}x")
    lines.append("━━━━━━━━━━━━━━━━━━")
    return "\n".join(lines)


def format_preopen_list(candidates: List[Dict[str, Any]], date: str, low_quality: bool = False, universe_size: int = 0) -> str:
    """פורמט ישן – נשמר לתאימות"""
    time_str = datetime.now(ET).strftime("%H:%M ET")
    
    if not candidates:
        return format_no_candidates(date, universe_size)
    
    lines = [
        "🎯 <b>DAYS-BOT - מועמדויות לפריצה</b>",
        f"📅 {date}  |  🕐 {time_str}",
        "━━━━━━━━━━━━━━━━━━",
    ]
    
    for i, r in enumerate(candidates[:5], 1):
        ticker = r.get('ticker', '???')
        price = r.get('price', 0)
        gap = r.get('gap_pct', 0)
        vol = r.get('volume', 0)
        score = r.get('score', 0)
        catalyst = r.get('catalyst', '—')
        rvol = r.get('rvol', 0)
        
        if vol >= 1_000_000:
            vol_str = f"{vol/1_000_000:.1f}M"
        elif vol >= 1_000:
            vol_str = f"{vol/1_000:.0f}K"
        else:
            vol_str = f"{vol}"
        
        if gap >= 5:
            gap_icon = "🔥"
        elif gap >= 3:
            gap_icon = "⚡"
        elif gap >= 1:
            gap_icon = "📈"
        else:
            gap_icon = "➡️"
        
        if score >= 70:
            grade = "🚀 EXCELLENT"
        elif score >= 50:
            grade = "✅ GOOD"
        elif score >= 30:
            grade = "👀 WATCH"
        else:
            grade = "⛔ SKIP"
        
        lines.append("")
        lines.append(f"<b>{i}. {ticker}</b>  💰 ${price:.2f}  {gap_icon} {gap:+.1f}%")
        lines.append(f"   📊 נפח: {vol_str}  |  RVOL: {rvol:.1f}x  |  🎯 {score:.0f}/100  {grade}")
        if catalyst and catalyst != '—':
            lines.append(f"   📰 {catalyst[:60]}")
    
    lines += [
        "",
        "━━━━━━━━━━━━━━━━━━",
        "⚡ כניסה: Gap > 1% + נפח > 50K + RVOL > 1.5",
        "🎯 יעד: +20%  |  🛑 סטופ: -5%",
        "🚫 לא המלצת השקעה"
    ]
    
    return "\n".join(lines)


def format_watchlist(watchlist: list, date: str) -> str:
    """פורמט רשימת מעקב (בעברית) – V2.2"""
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
        price = w.get('price', 0)
        gap = w.get('gap_pct', 0)
        score = w.get('score', 0)
        status = w.get('status', 'WATCH')
        hits = w.get('hits', 1)
        catalyst = w.get('catalyst', '')
        event_score = w.get('event_score', 0)
        grade = w.get('grade', '?')
        rvol = w.get('rvol', 0)
        float_shares = w.get('float_shares', 0)
        float_turnover = w.get('float_turnover')
        dilution_risk = w.get('dilution_risk', 'UNKNOWN')
        state = w.get('state', 'WATCH')
        
        if status == 'READY':
            status_icon = "🟢 מוכנה"
        elif status == 'PREPARE':
            status_icon = "🟡 בהכנה"
        else:
            status_icon = "🔵 במעקב"
        
        if float_shares and float_shares > 0:
            float_str = f"{float_shares/1_000_000:.1f}M"
        else:
            float_str = "❓"
        
        if float_turnover is not None and float_turnover > 0:
            turnover_str = f"{float_turnover:.1f}x"
        else:
            turnover_str = "❓"
        
        lines.append("")
        lines.append(f"<b>{i}. {ticker}</b>  💰 ${price:.2f}  Gap: {gap:+.1f}%")
        lines.append(f"   🎯 ציון אירוע: {event_score:.0f}/100  |  דירוג: {grade}")
        lines.append(f"   📊 RVOL: {rvol:.1f}x  |  Float: {float_str}  |  מחזור: {turnover_str}")
        lines.append(f"   {status_icon}  |  סיכון: {dilution_risk}  |  הופעות: {hits}  |  State: {state}")
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


def format_quant_report_v22(candidates: list, date: str) -> str:
    """דוח QUANT V2.2 – מציג State, Grade, Event Score, RVOL method, Float"""
    time_str = datetime.now(ET).strftime("%H:%M ET")
    lines = [
        "🔥 <b>DAYS-BOT V2.2 — QUANT SCAN</b>",
        f"📅 {date}  |  🕐 {time_str}",
        "━━━━━━━━━━━━━━━━━━",
    ]

    # Count states
    states = {}
    for c in candidates:
        st = c.get('state', 'REJECT')
        states[st] = states.get(st, 0) + 1
    line = f"📊 EARLY: {states.get('EARLY',0)} | WATCH: {states.get('WATCH',0)} | PREPARE: {states.get('PREPARE',0)}"
    lines.append(line)
    line = f"📊 READY: {states.get('READY',0)} | EXTENDED: {states.get('EXTENDED',0)} | REJECTED: {states.get('REJECTED',0)}"
    lines.append(line)
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
        float_shares = r.get('float_shares')
        float_turnover = r.get('float_turnover')
        dvol = r.get('dollar_volume', 0)
        catalyst = r.get('catalyst', '—')
        pm_dist = r.get('pm_high_dist', 999)
        spread = r.get('spread_pct', 0)
        prev_gain = r.get('prev_gain', 0)
        prev_rvol = r.get('prev_rvol', 0)
        volume_building = r.get('volume_building', False)

        float_str = f"{float_shares/1_000_000:.1f}M" if float_shares and float_shares > 0 else "UNKNOWN"
        turnover_str = f"{float_turnover:.1f}x" if float_turnover else "UNKNOWN"
        dvol_str = f"${dvol/1_000_000:.1f}M" if dvol >= 1_000_000 else f"${dvol/1_000:.0f}K"

        lines.append("")
        lines.append(f"<b>{i}. {ticker}</b>  💰 ${price:.2f}  Gap: {gap:+.1f}%")
        lines.append(f"   🎯 Event Score: {event_score}  |  Grade: {grade}  |  Risk: {risk}")
        lines.append(f"   📊 RVOL: {rvol:.1f}x ({rvol_method})  |  PM Dist: {pm_dist:.1f}%")
        if prev_gain:
            lines.append(f"   📈 Prev Day: +{prev_gain:.1f}%  |  Prev RVOL: {prev_rvol:.1f}x")
        lines.append(f"   🏷️ Float: {float_str}  |  Turnover: {turnover_str}  |  DVol: {dvol_str}")
        lines.append(f"   📰 Catalyst: {catalyst[:40] if catalyst != '—' else '—'}")
        lines.append(f"   🔵 State: <b>{state}</b>  |  Spread: {spread:.1f}%  |  Building: {'✅' if volume_building else '❌'}")

    lines += [
        "",
        "━━━━━━━━━━━━━━━━━━",
        "⚡ READY = Trigger + RVOL + execution filters",
        "🏆 A/A+ = setup quality only, NOT an entry signal",
        "🚫 NO CHASE = large gaps require fresh trigger",
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
