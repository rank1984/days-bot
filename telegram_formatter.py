"""
Telegram formatter - HTML mode (no Markdown issues)
"""
import requests
from datetime import datetime
import pytz
import re

ET = pytz.timezone("America/New_York")


def send_message(token: str, chat_id: str, text: str) -> bool:
    """Send message using HTML parse mode"""
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


def format_preopen_list(candidates: list, date: str, low_quality: bool = False) -> str:
    """Format candidates using HTML (safe)"""
    time_str = datetime.now(ET).strftime("%H:%M ET")
    
    if not candidates:
        return format_no_candidates(date, 0)
    
    lines = [
        "🎯 <b>DAYS-BOT - מועמדויות לפריצה</b>",
        f"📅 {date}  |  🕐 {time_str}",
        "━━━━━━━━━━━━━━━━━━",
    ]
    
    for i, r in enumerate(candidates[:5], 1):
        ticker = r['ticker']
        price = r['price']
        gap = r.get('gap_pct', 0)
        vol = r.get('volume', 0)
        score = r.get('score', 0)
        catalyst = r.get('catalyst', '—')
        
        # פורמט נפח
        if vol >= 1_000_000:
            vol_str = f"{vol/1_000_000:.1f}M"
        elif vol >= 1_000:
            vol_str = f"{vol/1_000:.0f}K"
        else:
            vol_str = f"{vol}"
        
        # אייקון Gap
        if gap >= 5:
            gap_icon = "🔥"
        elif gap >= 3:
            gap_icon = "⚡"
        elif gap >= 1:
            gap_icon = "📈"
        else:
            gap_icon = "➡️"
        
        # ציון
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
        lines.append(f"   📊 נפח: {vol_str}  |  🎯 Score: {score:.0f}/100  {grade}")
        if catalyst and catalyst != '—':
            lines.append(f"   📰 {catalyst[:60]}")
    
    lines += [
        "",
        "━━━━━━━━━━━━━━━━━━",
        "⚡ כניסה: Gap > 3% + נפח > 100K",
        "🎯 יעד: +20%  |  🛑 סטופ: -5%",
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
