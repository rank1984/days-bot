"""
Telegram formatter for DAYS-BOT
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


def _float_label(f: int) -> str:
    if f <= 0:           return "❓"
    if f < 20_000_000:   return f"🟢 {f/1_000_000:.1f}M"
    if f < 50_000_000:   return f"🟡 {f/1_000_000:.1f}M"
    if f < 100_000_000:  return f"🟠 {f/1_000_000:.0f}M"
    return                      f"🔴 {f/1_000_000:.0f}M"


def _dvol(dv: float) -> str:
    if dv >= 1_000_000: return f"${dv/1_000_000:.1f}M"
    if dv >= 1_000:     return f"${dv/1_000:.0f}K"
    return f"${dv:.0f}"


def calculate_ai_score(row: dict) -> dict:
    """
    מחשב ציון AI חכם לכל מועמדות
    """
    # שליפת נתונים
    gap_pct = row.get("gap_pct", 0)
    pm_rvol = row.get("pm_rvol", row.get("vol_ratio", 0))
    freshness = row.get("freshness", 0)
    momentum_score = row.get("momentum_score", 0)
    combined = row.get("combined", 0)
    pm_high_dist = row.get("pm_high_dist", 999)
    vol_accel = row.get("vol_accel", 1.0)
    catalyst = row.get("catalyst", "")
    float_size = row.get("float", 0)
    price = row.get("price", 0)
    vwap_dist = row.get("vwap_dist", 0)
    
    # ========== חישוב AI SCORE (0-100) ==========
    
    # 1. מומנטום (25 נקודות)
    momentum_ai = 0
    if momentum_score > 80: momentum_ai = 25
    elif momentum_score > 60: momentum_ai = 20
    elif momentum_score > 40: momentum_ai = 15
    elif momentum_score > 20: momentum_ai = 10
    else: momentum_ai = 5
    
    # 2. נפח יחסי (20 נקודות)
    vol_ai = min(20, (pm_rvol / 5) * 20) if pm_rvol > 0 else 0
    
    # 3. טריות (15 נקודות)
    if pm_high_dist <= 2:
        freshness_ai = 15
    elif pm_high_dist <= 5:
        freshness_ai = 12
    elif pm_high_dist <= 10:
        freshness_ai = 8
    elif pm_high_dist <= 20:
        freshness_ai = 5
    else:
        freshness_ai = 2
    
    # 4. קטליזטור (15 נקודות)
    catalyst_weight = 0
    catalyst_keywords = {
        'fda': 15, 'approval': 14, 'approved': 13,
        'breakthrough': 12, 'acquisition': 11, 'merger': 10,
        'contract': 9, 'partnership': 8, 'earnings': 8,
        'revenue': 7, 'product': 7, 'launch': 7,
        'positive': 6, 'clearance': 6, 'trial': 5,
        'designation': 5, 'grant': 4, 'award': 4,
    }
    catalyst_lower = catalyst.lower()
    for keyword, weight in catalyst_keywords.items():
        if keyword in catalyst_lower:
            catalyst_weight = max(catalyst_weight, weight)
            break
    catalyst_ai = min(15, catalyst_weight)
    
    # 5. Float וגודל (10 נקודות)
    if float_size < 20_000_000:
        float_ai = 10
    elif float_size < 50_000_000:
        float_ai = 7
    elif float_size < 100_000_000:
        float_ai = 4
    else:
        float_ai = 2
    
    # 6. תאוצת נפח (10 נקודות)
    if vol_accel >= 3.0:
        accel_ai = 10
    elif vol_accel >= 2.0:
        accel_ai = 7
    elif vol_accel >= 1.5:
        accel_ai = 4
    else:
        accel_ai = 2
    
    # 7. בונוס: VWAP חיובי (5 נקודות)
    vwap_ai = 5 if vwap_dist > 0 else 0
    
    # ========== חישוב סופי ==========
    total_ai_score = (
        momentum_ai +
        vol_ai +
        freshness_ai +
        catalyst_ai +
        float_ai +
        accel_ai +
        vwap_ai
    )
    
    total_ai_score = min(100, total_ai_score)
    
    # דירוג איכות
    if total_ai_score >= 85:
        quality = "🏆 EXCELLENT"
    elif total_ai_score >= 70:
        quality = "🌟 GOOD"
    elif total_ai_score >= 55:
        quality = "👍 AVERAGE"
    elif total_ai_score >= 40:
        quality = "⚠️ WATCH"
    else:
        quality = "⛔ SKIP"
    
    reasons = []
    if momentum_ai >= 20: reasons.append("Strong momentum")
    if vol_ai >= 15: reasons.append("High volume surge")
    if freshness_ai >= 12: reasons.append("Near PM high")
    if catalyst_ai >= 10: reasons.append("Strong catalyst")
    if float_ai >= 7: reasons.append("Small float")
    if accel_ai >= 7: reasons.append("Volume accelerating")
    if vwap_ai > 0: reasons.append("Above VWAP")
    
    if not reasons:
        reasons = ["Wait for catalyst or volume increase"]
    
    return {
        'ai_score': total_ai_score,
        'quality': quality,
        'reasons': reasons[:3],
        'breakdown': {
            'momentum': momentum_ai,
            'volume': vol_ai,
            'freshness': freshness_ai,
            'catalyst': catalyst_ai,
            'float': float_ai,
            'acceleration': accel_ai,
            'vwap': vwap_ai,
        }
    }


def format_preopen_list(candidates: list, date: str, low_quality: bool = False) -> str:
    time_str = datetime.now(ET).strftime("%H:%M ET")
    
    # חישוב דירוג AI לכל מועמד ומיון
    for row in candidates:
        ai = calculate_ai_score(row)
        row['ai_score'] = ai['ai_score']
        row['ai_quality'] = ai['quality']
        row['ai_reasons'] = ai['reasons']
        row['ai_breakdown'] = ai['breakdown']
    
    # מיון לפי ציון AI
    sorted_candidates = sorted(candidates, key=lambda x: x.get('ai_score', 0), reverse=True)
    
    # לקיחת 5 המובילים
    top_5 = sorted_candidates[:5]
    
    lines = [
        f"🎯 <b>DAYS-BOT Elite — לפני פתיחה</b>",
        f"📅 {date}  |  🕐 {time_str}",
        f"━━━━━━━━━━━━━━━━━━",
    ]

    if low_quality:
        lines.append("⚠️ <b>ציון נמוך — בדוק בזהירות</b>\n")

    for i, r in enumerate(top_5, 1):
        ai_score = r.get('ai_score', 0)
        ai_quality = r.get('ai_quality', '❓')
        ai_reasons = r.get('ai_reasons', [])
        
        fresh = r.get("freshness", 0)
        mom_s = r.get("momentum_score", 0)
        combined = r.get("combined", 0)
        pm_rvol = r.get("pm_rvol", 0)
        pm_vol = r.get("pm_volume", 0)
        dvol = r.get("dollar_volume", 0)

        pm_dist = r.get("pm_high_dist", 0)
        if pm_dist <= 2:    dist_e = "🔺"
        elif pm_dist <= 10: dist_e = "⚡"
        else:               dist_e = "⚠️"

        age = r.get("pm_high_age", 999)
        if age <= 5:    age_e = "🟢"
        elif age <= 15: age_e = "🟡"
        elif age < 999: age_e = "🔴"
        else:           age_e = "❓"

        mom5 = r.get("momentum_5m", 0)
        mom_e = "📈" if mom5 >= 0 else "📉"

        vd = r.get("vwap_dist", 0)
        vd_e = "🟢" if vd >= 0 else "🔴"

        accel = r.get("vol_accel", 1.0)
        if accel >= 2.0:    ac_e = "🚀"
        elif accel >= 1.5:  ac_e = "⚡"
        else:               ac_e = "➡️"

        catalyst = r.get("catalyst", "—")
        
        ai_bar = "█" * int(ai_score / 10) + "░" * (10 - int(ai_score / 10))
        
        lines.append(
            f"\n<b>#{i}. {r['ticker']}</b>  "
            f"${r['price']:.2f}  +{r['gap_pct']:.1f}%"
        )
        lines.append(f"   📰 {catalyst}")
        lines.append(
            f"   🏷️ {_float_label(int(r.get('float',0)))}  "
            f"| 📦 {pm_vol:,}  | 💵 {_dvol(dvol)}"
        )
        lines.append(
            f"   {dist_e} PM High: {pm_dist:.1f}%  "
            f"| {age_e} Age: {age}min"
        )
        lines.append(
            f"   {mom_e} 5min: {mom5:+.1f}%  "
            f"| {vd_e} VWAP: {vd:+.1f}%  "
            f"| {ac_e} Accel: {accel:.1f}x"
        )
        lines.append(
            f"   🌊 Fresh: <b>{fresh:.0f}</b>  "
            f"| ⚡ Mom: <b>{mom_s:.0f}</b>  "
            f"| 🎯 Combined: <b>{combined:.0f}</b>"
        )
        
        lines.append(f"   🤖 <b>AI Score: {ai_score:.0f}/100</b>  {ai_quality}")
        lines.append(f"   📊 [{ai_bar}]")
        if ai_reasons:
            lines.append(f"   💡 {', '.join(ai_reasons)}")

    lines += [
        "\n━━━━━━━━━━━━━━━━━━",
        "⚠️ בדוק כל מניה לפני כניסה",
        "🚫 לא המלצת השקעה",
        f"📊 מוצגות 5 המובילות לפי AI Score"
    ]
    return "\n".join(lines)


def format_no_candidates(date: str, universe_size: int = 0) -> str:
    time_str = datetime.now(ET).strftime("%H:%M ET")
    return (
        f"🤖 <b>DAYS-BOT — לפני פתיחה</b>\n"
        f"📅 {date}  |  🕐 {time_str}\n"
        f"━━━━━━━━━━━━━━━━━━\n"
        f"🔍 נסרקו: {universe_size} מניות\n"
        f"😴 אין מועמדות היום\n"
        f"━━━━━━━━━━━━━━━━━━\n"
        f"⏰ מחר ב-14:30"
    )


def format_alert(row: dict) -> str:
    ai = calculate_ai_score(row)
    ai_score = ai['ai_score']
    ai_quality = ai['quality']
    ai_reasons = ai['reasons']
    
    pm_high = row.get("pm_high", 0)
    pm_dist = row.get("pm_high_dist", 0)
    pm_rvol = row.get("pm_rvol", row.get("vol_ratio", 0))
    catalyst = row.get("catalyst", "—")
    fresh = row.get("freshness", 0)
    mom_s = row.get("momentum_score", 0)
    combined = row.get("combined", 0)

    pm_line = (
        f"📊 <b>PM High:</b> ${pm_high:.2f}  "
        f"{'🔺 פריצה!' if abs(pm_dist) < 2 else f'{pm_dist:+.1f}%'}\n"
    ) if pm_high > 0 else ""

    return (
        f"🎯 <b>DAYS-BOT — {row['ticker']}</b>\n"
        f"━━━━━━━━━━━━━━━━━━\n"
        f"💰 ${row['price']:.2f}  📈 +{row['gap_pct']:.1f}%\n"
        f"{pm_line}"
        f"📰 {catalyst}\n"
        f"🏷️ {_float_label(int(row.get('float',0)))}  "
        f"| ⚡ RVOL: {pm_rvol:.1f}x\n"
        f"📦 {row.get('pm_volume',0):,}  "
        f"| 💵 {_dvol(row.get('dollar_volume',0))}\n"
        f"🌊 Fresh: <b>{fresh:.0f}</b>  "
        f"| ⚡ Mom: <b>{mom_s:.0f}</b>  "
        f"| 🎯 <b>{combined:.0f}</b>\n"
        f"🤖 <b>AI Score: {ai_score:.0f}/100</b>  {ai_quality}\n"
        f"💡 {', '.join(ai_reasons[:2])}\n"
        f"━━━━━━━━━━━━━━━━━━\n"
        f"🚫 לא המלצת השקעה"
    )
