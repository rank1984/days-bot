"""
Telegram formatter for DAYS-BOT - Clean & Actionable
"""
import requests
from datetime import datetime
import pytz
import json
import traceback
import re

ET = pytz.timezone("America/New_York")


def send_message(token: str, chat_id: str, text: str) -> bool:
    """Send message to Telegram with detailed error handling"""
    print(f"[Telegram] 📤 Attempting to send message...")
    
    if not token:
        print("[Telegram] ❌ TELEGRAM_TOKEN is missing or empty!")
        return False
    
    if not chat_id:
        print("[Telegram] ❌ TELEGRAM_CHAT_ID is missing or empty!")
        return False
    
    if not text or len(text.strip()) == 0:
        print("[Telegram] ❌ Message text is empty!")
        return False
    
    # ניקוי הטקסט מתווים מיוחדים
    text = clean_text_for_telegram(text)
    
    print(f"[Telegram] Message length: {len(text)} chars")
    print(f"[Telegram] Message preview:")
    print("-" * 40)
    print(text[:300] + "..." if len(text) > 300 else text)
    print("-" * 40)
    
    url = f"https://api.telegram.org/bot{token}/sendMessage"
    
    try:
        payload = {
            "chat_id": chat_id,
            "text": text,
            "parse_mode": "Markdown",
            "disable_web_page_preview": True
        }
        
        print(f"[Telegram] Sending to chat_id: {chat_id}")
        
        resp = requests.post(
            url,
            json=payload,
            timeout=30,
            headers={"Content-Type": "application/json"}
        )
        
        print(f"[Telegram] Response status: {resp.status_code}")
        
        if resp.status_code == 200:
            print("[Telegram] ✅ Message sent successfully!")
            return True
        else:
            print(f"[Telegram] ❌ Error {resp.status_code}:")
            print(f"[Telegram] Response: {resp.text}")
            return False
            
    except requests.exceptions.Timeout:
        print("[Telegram] ❌ Timeout")
        return False
    except Exception as e:
        print(f"[Telegram] ❌ Error: {e}")
        print(traceback.format_exc())
        return False


def clean_text_for_telegram(text: str) -> str:
    """Clean text for Telegram - remove unsupported HTML tags"""
    # הסר HTML tags לא תקינים
    text = re.sub(r'<[^>]+>', '', text)
    
    # החלף תווים מיוחדים
    text = text.replace('•', '-')
    text = text.replace('★', '*')
    
    # נקה רווחים מיותרים
    text = re.sub(r'\n{3,}', '\n\n', text)
    
    return text.strip()


def format_preopen_list(candidates: list, date: str, low_quality: bool = False) -> str:
    """Clean, actionable format - without HTML tags"""
    time_str = datetime.now(ET).strftime("%H:%M ET")
    
    print(f"[Formatter] Formatting {len(candidates)} candidates for {date}")
    
    if not candidates:
        return format_no_candidates(date, 0)
    
        # ====== סינון איכות מחמיר יותר ======
    filtered = []
    for c in candidates:
        vol = c.get('pm_volume', c.get('volume', 0))
        gap = c.get('gap_pct', 0)
        float_shares = c.get('float', 0)
        
        # סינון נפח - לפחות 50,000
        if vol < 50_000:
            continue
        
        # סינון gap - 0-2.5%
        if gap < 0 or gap > 2.5:
            continue
        
        # סינון Float - אם יש, רק עד 50M
        if float_shares > 0 and float_shares > 50_000_000:
            continue
        
        filtered.append(c)
    
    print(f"[Formatter] After filtering: {len(filtered)} candidates")
    
    if not filtered:
        return format_no_candidates(date, len(candidates))
    
    sorted_candidates = sorted(filtered, key=lambda x: -x.get('pm_volume', x.get('volume', 0)))
    top = sorted_candidates[:5]
    
    lines = [
        "🎯 DAYS-BOT - מועמדויות לפריצה",
        f"📅 {date}  |  🕐 {time_str}",
        "━━━━━━━━━━━━━━━━━━",
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
        
        # חישוב AI Score
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
        
        lines.append("")
        lines.append(f"{i}. {ticker}  💰 ${price:.2f}  {gap_icon} {gap:+.1f}%")
        lines.append(f"   📊 נפח: {vol_str}  |  Float: {float_str}")
        lines.append(f"   🎯 {ai_score}/100  {quality}")
    
    lines += [
        "",
        "━━━━━━━━━━━━━━━━━━",
        "⚡ כניסה אידיאלית: gap < 1% + נפח > 200K + Float < 30M",
        "🎯 יעד: +20%  |  🛑 סטופ: -5%",
        "🚫 לא המלצת השקעה"
    ]
    
    result = "\n".join(lines)
    print(f"[Formatter] Final message length: {len(result)} chars")
    return result


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
        f"🎯 {ticker}  💰 ${price:.2f}  {gap_icon} {gap:+.1f}%\n"
        f"━━━━━━━━━━━━━━━━━━\n"
        f"📊 נפח: {vol_str}\n"
        f"━━━━━━━━━━━━━━━━━━\n"
        f"⚡ כניסה: ${price:.2f}\n"
        f"🎯 יעד: ${price * 1.20:.2f} (+20%)\n"
        f"🛑 סטופ: ${price * 0.95:.2f} (-5%)\n"
        f"━━━━━━━━━━━━━━━━━━\n"
        f"🚫 לא המלצת השקעה"
    )
