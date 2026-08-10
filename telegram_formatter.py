"""
Telegram formatter - HTML mode (safe)
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
    """עיצוב תוכנית מסחר לטלגרם"""
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
    """פורמט Watchlist (רשימת מעקב)"""
    time_str = datetime.now(ET).strftime("%H:%M ET")
    
    if not watchlist:
        return f"📋 <b>DAYS-BOT WATCHLIST</b>\n📅 {date}  |  🕐 {time_str}\n━━━━━━━━━━━━━━━━━━\n😴 No active candidates."
    
    lines = [
        "📋 <b>DAYS-BOT WATCHLIST</b>",
        f"📅 {date}  |  🕐 {time_str}",
        f"📊 {len(watchlist)} candidates | {sum(1 for w in watchlist if w.get('status') == 'READY')} READY",
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
        
        if status == 'READY':
            status_icon = "🟢 READY"
        elif status == 'PREPARE':
            status_icon = "🟡 PREPARE"
        else:
            status_icon = "🔵 WATCH"
        
        lines.append("")
        lines.append(f"<b>{i}. {ticker}</b>  💰 ${price:.2f}  Gap: {gap:+.1f}%  Score: {score:.0f}")
        lines.append(f"   {status_icon}  |  Hits: {hits}")
        if catalyst:
            lines.append(f"   📰 {catalyst[:40]}")
    
    lines += [
        "",
        "━━━━━━━━━━━━━━━━━━",
        "⚡ READY = Trigger + RVOL confirmed",
        "🚀 Entry only on breakout with volume",
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
