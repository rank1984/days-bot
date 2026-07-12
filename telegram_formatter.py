"""
Telegram formatter for DAYS-BOT - Clean & Actionable
"""
import requests
from datetime import datetime
import pytz
import json

ET = pytz.timezone("America/New_York")


def send_message(token: str, chat_id: str, text: str) -> bool:
    """Send message to Telegram with better error handling"""
    if not token or not chat_id:
        print("[Telegram] ❌ Missing token or chat_id")
        return False
    
    if not text or len(text.strip()) == 0:
        print("[Telegram] ❌ Empty message")
        return False
    
    url = f"https://api.telegram.org/bot{token}/sendMessage"
    
    # הדפס את ההודעה לקונסול לבדיקה
    print(f"[Telegram] Sending message ({len(text)} chars):")
    print("-" * 40)
    print(text[:500] + "..." if len(text) > 500 else text)
    print("-" * 40)
    
    try:
        payload = {
            "chat_id": chat_id,
            "text": text,
            "parse_mode": "HTML",
            "disable_web_page_preview": True
        }
        
        resp = requests.post(
            url,
            json=payload,
            timeout=30,
            headers={"Content-Type": "application/json"}
        )
        
        if resp.status_code != 200:
            print(f"[Telegram] ❌ Error {resp.status_code}: {resp.text}")
            return False
            
        print("[Telegram] ✅ Message sent successfully")
        return True
        
    except requests.exceptions.Timeout:
        print("[Telegram] ❌ Timeout")
        return False
    except Exception as e:
        print(f"[Telegram] ❌ Error: {e}")
        return False


def format_preopen_list(candidates: list, date: str, low_quality: bool = False) -> str:
    """Clean, actionable format - only high quality candidates"""
    time_str = datetime.now(ET).strftime("%H:%M ET")
    
    if not candidates:
        return format_no_candidates(date, 0)
    
    # ====== סינון איכות ======
    filtered = []
    for c in candidates:
        vol = c.get('pm_volume', c.get('volume', 0))
        gap = c.get('gap_pct', 0)
        float_shares = c.get('float', 0)
        
        # סינון נפח - לפחות 10,000
        if vol < 10_000:
            continue
        
        # סינון gap - 0-3%
        if gap < 0 or gap > 3.0:
            continue
        
        # סינון Float - אם יש, רק עד 150M
        if float_shares > 0 and float_shares > 150_000_000:
            continue
        
        filtered.append(c)
    
    if not filtered:
        return format_no_candidates(date, len(candidates))
    
    # מיון לפי נפח (גבוה קודם)
    sorted_candidates = sorted(filtered, key=lambda x: -x.get('pm_volume', x.get('volume', 0)))
    
    # קח עד 5 מועמדויות
    top = sorted_candidates[:5]
    
    lines = [
        f"🎯 <b>DAYS-BOT — מועמדויות לפריצה</b>",
        f"📅 {date}  |  🕐 {time_str}",
        f"━━━━━━━━━━━━━━━━━━",
    ]
    
    for i, r in enumerate(top, 1):
        ticker = r['ticker']
        price = r['price']
        gap = r.get('gap_pct', 0)
        vol = r.get('pm_volume', r.get('volume', 0))
        float_shares = r.get('float', 0)
        
        # פורמט נפח
        if vol >= 1_000_000:
            vol_str = f"{vol/1_000_000:.1f}M"
        elif vol >= 1_000:
            vol_str = f"{vol/1_000:.0f}K"
        else:
            vol_str = f"{vol}"
        
        # פורמט Float
        if float_shares >= 1_000_000:
            float_str = f"{float_shares/1_000_000:.1f}M"
        elif float_shares >= 1_000:
            float_str = f"{float_shares/1_000:.0f}K"
        else:
            float_str = "?"
        
        # אייקון לפי gap
        if gap < 0.5:
            gap_icon = "🟢"
        elif gap < 1.0:
            gap_icon = "🟡"
        else:
            gap_icon = "🟠"
        
        # חישוב AI Score פשוט
        ai_score = 50
        if vol > 200_000:
            ai_score += 20
        if gap < 0.5:
            ai_score += 15
        if 0 < float_shares < 30_000_000:
            ai_score += 15
        
        if ai_score >= 80:
            quality = "🚀 EXCELLENT"
        elif ai_score >= 65:
            quality = "✅ GOOD"
        else:
            quality = "👀 WATCH"
        
        lines.append(
            f"\n<b>{i}. {ticker}</b>  💰 ${price:.2f}  {gap_icon} {gap:+.1f}%"
        )
        lines.append(
            f"   📊 נפח: {vol_str}  |  Float: {float_str}"
        )
        lines.append(
            f"   🎯 <b>{ai_score}/100</b>  {quality}"
        )
    
    lines += [
        "\n━━━━━━━━━━━━━━━━━━",
        "⚡ כניסה אידיאלית: gap < 1% + נפח > 200K + Float < 30M",
        "🎯 יעד: +20%  |  🛑 סטופ: -5%",
        "🚫 לא המלצת השקעה"
    ]
    
    return "\n".join(lines)


def format_no_candidates(date: str, universe_size: int = 0) -> str:
    time_str = datetime.now(ET).strftime("%H:%M ET")
    return (
        f"🎯 <b>DAYS-BOT — מועמדויות לפריצה</b>\n"
        f"📅 {date}  |  🕐 {time_str}\n"
        f"━━━━━━━━━━━━━━━━━━\n"
        f"🔍 נסרקו: {universe_size} מניות\n"
        f"😴 אין מועמדויות איכותיות היום\n"
        f"━━━━━━━━━━━━━━━━━━\n"
        f"⏰ בדיקה חוזרת מחר ב-14:30"
    )


def format_alert(row: dict) -> str:
    """Single alert format"""
    ticker = row['ticker']
    price = row['price']
    gap = row.get('gap_pct', 0)
    vol = row.get('pm_volume', row.get('volume', 0))
    
    if vol >= 1_000_000:
        vol_str = f"{vol/1_000_000:.1f}M"
    elif vol >= 1_000:
        vol_str = f"{vol/1_000:.0f}K"
    else:
        vol_str = f"{vol}"
    
    gap_icon = "🟢" if gap < 0.5 else "🟡" if gap < 1.0 else "🟠"
    
    return (
        f"🎯 <b>{ticker}</b>  💰 ${price:.2f}  {gap_icon} {gap:+.1f}%\n"
        f"━━━━━━━━━━━━━━━━━━\n"
        f"📊 נפח: {vol_str}\n"
        f"━━━━━━━━━━━━━━━━━━\n"
        f"⚡ כניסה: ${price:.2f}\n"
        f"🎯 יעד: ${price * 1.20:.2f} (+20%)\n"
        f"🛑 סטופ: ${price * 0.95:.2f} (-5%)\n"
        f"━━━━━━━━━━━━━━━━━━\n"
        f"🚫 לא המלצת השקעה"
    )
