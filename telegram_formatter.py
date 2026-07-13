"""
Telegram formatter - updated with new fields
"""
import requests
from datetime import datetime
import pytz

ET = pytz.timezone("America/New_York")


def send_message(token: str, chat_id: str, text: str) -> bool:
    """Send message to Telegram"""
    if not token or not chat_id:
        return False
    
    url = f"https://api.telegram.org/bot{token}/sendMessage"
    try:
        resp = requests.post(
            url,
            json={
                "chat_id": chat_id,
                "text": text,
                "parse_mode": "Markdown",
                "disable_web_page_preview": True
            },
            timeout=30
        )
        return resp.status_code == 200
    except Exception as e:
        print(f"[Telegram] Error: {e}")
        return False


def format_preopen_list(candidates: list, date: str, low_quality: bool = False) -> str:
    """Format candidates for Telegram"""
    time_str = datetime.now(ET).strftime("%H:%M ET")
    
    if not candidates:
        return format_no_candidates(date, 0)
    
    lines = [
        "🎯 DAYS-BOT - מועמדויות לפריצה",
        f"📅 {date}  |  🕐 {time_str}",
        "━━━━━━━━━━━━━━━━━━",
    ]
    
    for i, r in enumerate(candidates[:5], 1):
        ticker = r['ticker']
        price = r['price']
        gap = r.get('gap_pct', 0)
        vol = r.get('pm_volume', 0)
        dvol = r.get('dollar_volume', 0)
        rvol = r.get('relative_volume', 1.0)
        score = r.get('score', 0)
        grade = r.get('grade', '❓')
        catalyst = r.get('catalyst', '—')
        
        # Format numbers
        if vol >= 1_000_000:
            vol_str = f"{vol/1_000_000:.1f}M"
        else:
            vol_str = f"{vol/1_000:.0f}K"
        
        if dvol >= 1_000_000:
            dvol_str = f"${dvol/1_000_000:.1f}M"
        else:
            dvol_str = f"${dvol/1_000:.0f}K"
        
        # Gap icon
        if gap < 5:
            gap_icon = "🟢"
        elif gap < 10:
            gap_icon = "🟡"
        else:
            gap_icon = "🟠"
        
        lines.append("")
        lines.append(f"{i}. *{ticker}*  💰 ${price:.2f}  {gap_icon} {gap:+.1f}%")
        lines.append(f"   📊 נפח: {vol_str}  |  RVOL: {rvol:.1f}x  |  💵 {dvol_str}")
        lines.append(f"   📰 {catalyst[:40] + '...' if len(catalyst) > 40 else catalyst}")
        lines.append(f"   🎯 *{score:.0f}/100*  {grade}")
    
    lines += [
        "",
        "━━━━━━━━━━━━━━━━━━",
        "⚡ כניסה: gap 3-25% + נפח > 200K + RVOL > 2x",
        "🎯 יעד: +20%  |  🛑 סטופ: -5%",
        "🚫 לא המלצת השקעה"
    ]
    
    return "\n".join(lines)


def format_no_candidates(date: str, universe_size: int = 0) -> str:
    time_str = datetime.now(ET).strftime("%H:%M ET")
    return (
        f"🎯 DAYS-BOT - מועמדויות לפריצה\n"
        f"📅 {date}  |  🕐 {time_str}\n"
        f"━━━━━━━━━━━━━━━━━━\n"
        f"🔍 נסרקו: {universe_size} מניות\n"
        f"😴 אין מועמדויות איכותיות היום\n"
        f"━━━━━━━━━━━━━━━━━━\n"
        f"⏰ בדיקה חוזרת מחר ב-14:30"
    )
