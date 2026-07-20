"""
Telegram formatter - updated with enhanced momentum metrics & stable MarkdownV2 parsing
"""
import requests
from datetime import datetime
import pytz

ET = pytz.timezone("America/New_York")


def escape_markdown_v2(text: str) -> str:
    """בורח תווים מיוחדים של MarkdownV2 כדי למנוע שגיאות שליחה בטלגרם"""
    escape_chars = r'_*[]()~`>#+-=|{}.!'
    return ''.join(f'\\{c}' if c in escape_chars else c for c in str(text))


def send_message(token: str, chat_id: str, text: str) -> bool:
    """Send message to Telegram using MarkdownV2"""
    if not token or not chat_id:
        return False
    
    url = f"https://api.telegram.org/bot{token}/sendMessage"
    try:
        resp = requests.post(
            url,
            json={
                "chat_id": chat_id,
                "text": text,
                "parse_mode": "MarkdownV2",
                "disable_web_page_preview": True
            },
            timeout=30
        )
        if resp.status_code != 200:
            print(f"[Telegram] Failed to send. Status: {resp.status_code}, Response: {resp.text}")
        return resp.status_code == 200
    except Exception as e:
        print(f"[Telegram] Error: {e}")
        return False


def format_preopen_list(candidates: list, date: str, universe_size: int = 0) -> str:
    """Format candidates for Telegram with exact match to our scanner outputs"""
    time_str = datetime.now(ET).strftime("%H:%M ET")
    
    if not candidates:
        return format_no_candidates(date, universe_size)
    
    # כותרת ההודעה
    lines = [
        "🎯 *DAYS\\-BOT \\- מועמדויות לפריצה*",
        f"📅 {escape_markdown_v2(date)}  \\|  🕐 {escape_markdown_v2(time_str)}",
        "━━━━━━━━━━━━━━━━━━",
    ]
    
    # הצגת 5 המועמדות המובילות
    for i, r in enumerate(candidates[:5], 1):
        ticker = escape_markdown_v2(r['ticker'])
        price = r['price']
        gap = r.get('gap_pct', 0.0)
        vol = r.get('pm_volume', 0.0)
        dvol = r.get('dollar_volume', 0.0)
        rvol = r.get('rvol', 1.0)  # שימוש במפתח המעודכן מהסורק
        score = r.get('score', 0.0)
        catalyst = r.get('catalyst', '—')
        
        # פורמט נפח מניות (ווליום)
        if vol >= 1_000_000:
            vol_str = f"{vol/1_000_000:.1f}M"
        else:
            vol_str = f"{vol/1_000:.0f}K"
        vol_str = escape_markdown_v2(vol_str)
            
        # פורמט שווי דולרי (נזילות)
        if dvol >= 1_000_000:
            dvol_str = f"\\${dvol/1_000_000:.1f}M"
        else:
            dvol_str = f"\\${dvol/1_000:.0f}K"
        
        # איקון מותאם לפי עוצמת הגאפ
        if gap < 5.0:
            gap_icon = "🟢"
        elif gap < 12.0:
            gap_icon = "🟡"
        else:
            gap_icon = "🟠"
            
        # חיתוך כותרת החדשות אם היא ארוכה מדי
        if len(catalyst) > 40:
            catalyst_summary = catalyst[:40] + "..."
        else:
            catalyst_summary = catalyst
        catalyst_summary = escape_markdown_v2(catalyst_summary)
        
        # סימן פלוס או מינוס לגאפ
        gap_sign = "\\+" if gap >= 0 else ""
        
        lines.append("")
        lines.append(f"{i}\\. *{ticker}*  💰 \\${price:.2f}  {gap_icon} Gap: {gap_sign}{gap:.1f}%")
        lines.append(f"   📊 RVOL: {rvol:.1f}x  \\|  💵 {dvol_str}  \\|  נפח: {vol_str}")
        lines.append(f"   📰 קטליזטור: {catalyst_summary}")
        lines.append(f"   🎯 *Score: {score:.0f}/100*")
    
    # חתימת ההודעה עם תנאי הסינון החדשים והאגרסיביים
    lines += [
        "",
        "━━━━━━━━━━━━━━━━━━",
        "⚡ *סינון קשוח:* Gap 3\\-25% \\| RVOL \\> 2x \\| DVol \\> \\$1M",
        "🎯 *יעד:* \\+20%  \\|  🛑 *סטופ:* \\-5%",
        "🚫 _אין באמור המלצה לפעולה בשוק_"
    ]
    
    return "\n".join(lines)


def format_no_candidates(date: str, universe_size: int = 0) -> str:
    """הודעה ייעודית למצב שבו אף מניה לא עברה את הפילטרים המחמירים"""
    time_str = datetime.now(ET).strftime("%H:%M ET")
    
    lines = [
        "🎯 *DAYS\\-BOT \\- מועמדויות לפריצה*",
        f"📅 {escape_markdown_v2(date)}  \\|  🕐 {escape_markdown_v2(time_str)}",
        "━━━━━━━━━━━━━━━━━━",
        f"🔍 נסרקו: {universe_size} מניות בלוח ה\\-Universe",
        "😴 *אין מועמדויות איכותיות שעברו את הסינון היום*",
        "━━━━━━━━━━━━━━━━━━",
        "⏰ בדיקת מומנטום מחודשת ביום המסחר הבא\\."
    ]
    return "\n".join(lines)
