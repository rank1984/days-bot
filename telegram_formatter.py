"""
Telegram formatter for DAYS-BOT - Clean & Actionable
"""
import requests
from datetime import datetime
import pytz

ET = pytz.timezone("America/New_York")


def send_message(token: str, chat_id: str, text: str) -> bool:
    url = f"https://api.telegram.org/bot{token}/sendMessage"
    try:
        resp = requests.post(
            url,
            json={"chat_id": chat_id, "text": text, "parse_mode": "HTML"},
            timeout=10,
        )
        resp.raise_for_status()
        return True
    except Exception as e:
        print(f"[Telegram] Error: {e}")
        return False


def calculate_ai_score(row: dict) -> dict:
    """Simple AI score based on key metrics"""
    gap = row.get("gap_pct", 0)
    vol = row.get("pm_volume", row.get("volume", 0))
    float_shares = row.get("float", 0)
    
    score = 0
    
    # Gap (0-30) - smaller is better for pre-breakout
    if gap < 0.5:
        score += 30
    elif gap < 1.0:
        score += 25
    elif gap < 2.0:
        score += 20
    elif gap < 3.0:
        score += 15
    else:
        score += 5
    
    # Volume (0-35) - needs enough liquidity
    if vol >= 500_000:
        score += 35
    elif vol >= 250_000:
        score += 28
    elif vol >= 100_000:
        score += 20
    elif vol >= 50_000:
        score += 12
    else:
        score += 5
    
    # Float (0-35) - smaller float = bigger moves
    if 0 < float_shares < 20_000_000:
        score += 35
    elif float_shares < 50_000_000:
        score += 25
    elif float_shares < 100_000_000:
        score += 15
    elif float_shares < 200_000_000:
        score += 8
    else:
        score += 3
    
    # Normalize to 100
    score = min(100, score)
    
    # Quality rating
    if score >= 80:
        quality = "🚀 HIGH"
    elif score >= 65:
        quality = "✅ GOOD"
    elif score >= 50:
        quality = "👀 WATCH"
    else:
        quality = "⛔ SKIP"
    
    return {'ai_score': score, 'quality': quality}


def format_preopen_list(candidates: list, date: str, low_quality: bool = False) -> str:
    """Clean, actionable format"""
    time_str = datetime.now(ET).strftime("%H:%M ET")
    
    # Filter out low quality candidates (skip volume < 50K)
    filtered = []
    for c in candidates:
        vol = c.get('pm_volume', c.get('volume', 0))
        if vol < 50_000:
            continue
        filtered.append(c)
    
    if not filtered:
        return format_no_candidates(date, len(candidates))
    
    # Calculate AI scores and sort
    for c in filtered:
        ai = calculate_ai_score(c)
        c['ai_score'] = ai['ai_score']
        c['ai_quality'] = ai['quality']
    
    sorted_candidates = sorted(filtered, key=lambda x: x.get('ai_score', 0), reverse=True)
    top_5 = sorted_candidates[:5]
    
    lines = [
        f"🎯 <b>DAYS-BOT — מועמדויות לפריצה</b>",
        f"📅 {date}  |  🕐 {time_str}",
        f"━━━━━━━━━━━━━━━━━━",
    ]
    
    for i, r in enumerate(top_5, 1):
        ticker = r['ticker']
        price = r['price']
        gap = r.get('gap_pct', 0)
        vol = r.get('pm_volume', r.get('volume', 0))
        float_shares = r.get('float', 0)
        ai_score = r.get('ai_score', 0)
        ai_quality = r.get('ai_quality', '❓')
        
        # Format volume
        if vol >= 1_000_000:
            vol_str = f"${vol/1_000_000:.1f}M"
        elif vol >= 1_000:
            vol_str = f"${vol/1_000:.0f}K"
        else:
            vol_str = f"${vol:.0f}"
        
        # Format float
        if float_shares >= 1_000_000:
            float_str = f"{float_shares/1_000_000:.1f}M"
        elif float_shares >= 1_000:
            float_str = f"{float_shares/1_000:.0f}K"
        else:
            float_str = "?"
        
        # Gap indicator
        if gap < 1.0:
            gap_icon = "🟢"
        elif gap < 2.0:
            gap_icon = "🟡"
        else:
            gap_icon = "🟠"
        
        lines.append(
            f"\n<b>{i}. {ticker}</b>  💰 ${price:.2f}  {gap_icon} {gap:+.1f}%"
        )
        lines.append(
            f"   📊 נפח: {vol_str}  |  Float: {float_str}"
        )
        lines.append(
            f"   🎯 AI: <b>{ai_score}/100</b>  {ai_quality}"
        )
    
    lines += [
        "\n━━━━━━━━━━━━━━━━━━",
        "⚡ כניסה: gap < 1% + נפח > 200K + Float < 50M",
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
        f"😴 אין מועמדויות היום\n"
        f"━━━━━━━━━━━━━━━━━━\n"
        f"⏰ בדיקה חוזרת מחר ב-14:30"
    )


def format_alert(row: dict) -> str:
    """Single alert format"""
    ai = calculate_ai_score(row)
    ticker = row['ticker']
    price = row['price']
    gap = row.get('gap_pct', 0)
    vol = row.get('pm_volume', row.get('volume', 0))
    float_shares = row.get('float', 0)
    
    if vol >= 1_000_000:
        vol_str = f"${vol/1_000_000:.1f}M"
    elif vol >= 1_000:
        vol_str = f"${vol/1_000:.0f}K"
    else:
        vol_str = f"${vol:.0f}"
    
    if float_shares >= 1_000_000:
        float_str = f"{float_shares/1_000_000:.1f}M"
    else:
        float_str = f"{float_shares/1_000:.0f}K"
    
    gap_icon = "🟢" if gap < 1.0 else "🟡" if gap < 2.0 else "🟠"
    
    return (
        f"🎯 <b>{ticker}</b>  💰 ${price:.2f}  {gap_icon} {gap:+.1f}%\n"
        f"━━━━━━━━━━━━━━━━━━\n"
        f"📊 נפח: {vol_str}  |  Float: {float_str}\n"
        f"🎯 AI: <b>{ai['ai_score']}/100</b>  {ai['quality']}\n"
        f"━━━━━━━━━━━━━━━━━━\n"
        f"⚡ כניסה: {price:.2f}\n"
        f"🎯 יעד: ${price * 1.20:.2f} (+20%)\n"
        f"🛑 סטופ: ${price * 0.95:.2f} (-5%)\n"
        f"━━━━━━━━━━━━━━━━━━\n"
        f"🚫 לא המלצת השקעה"
    )
