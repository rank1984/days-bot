"""
Telegram Formatter for DAYS-BOT
"""
from datetime import datetime
import pytz

ET = pytz.timezone('US/Eastern')

def format_watchlist(watchlist: list, date: str) -> str:
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
        status = w.get('status', 'WATCH')
        hits = w.get('hits', 1)
        catalyst = w.get('catalyst', '')
        event_score = w.get('event_score', 0)
        grade = w.get('setup_grade', '?')
        rvol = w.get('rvol', 0)
        float_shares = w.get('float_shares', 0)
        float_turnover = w.get('float_turnover')
        dilution_risk = w.get('dilution_risk', 'UNKNOWN')
            
        # Status
        if status == 'READY':
            status_icon = "🟢 מוכנה"
        elif status == 'PREPARE':
            status_icon = "🟡 בהכנה"
        else:
            status_icon = "🔵 במעקב"
            
        # Format Float
        if float_shares > 0:
            float_str = f"{float_shares/1_000_000:.1f}M"
        else:
            float_str = "❓"
            
        # Format Turnover
        if float_turnover is not None and float_turnover > 0:
            turnover_str = f"{float_turnover:.1f}x"
        else:
            turnover_str = "❓"
            
        lines.append("")
        lines.append(f"<b>{i}. {ticker}</b>  💰 ${price:.2f}  Gap: {gap:+.1f}%")
        lines.append(f"   🎯 ציון אירוע: {event_score:.0f}/100  |  דירוג: {grade}")
        lines.append(f"   📊 RVOL: {rvol:.1f}x  |  Float: {float_str}  |  מחזור: {turnover_str}")
        lines.append(f"   {status_icon}  |  סיכון: {dilution_risk}  |  הופעות: {hits}")
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


def format_quant_report(candidates: list, date: str) -> str:
    time_str = datetime.now(ET).strftime("%H:%M ET")
    lines = [
        "🔥 <b>AI SMALL-CAP QUANT</b>",
        f"📅 {date}  |  🕐 {time_str}",
        "━━━━━━━━━━━━━━━━━━",
    ]
    
    tradeable = [c for c in candidates if c.get('event_score', 0) >= 30]
    rejected = [c for c in candidates if c.get('event_score', 0) < 30]
    
    lines.append(f"📊 נסרקו: {len(candidates)} מועמדויות")
    lines.append(f"✅ עברו סינון: {len(tradeable)}")
    lines.append(f"❌ נפסלו: {len(rejected)}")
    lines.append("━━━━━━━━━━━━━━━━━━")
    
    for i, r in enumerate(tradeable[:3], 1):
        ticker = r['ticker']
        price = r['price']
        gap = r['gap_pct']
        rvol = r.get('rvol', 0)
        event_score = r.get('event_score', 0)
        grade = r.get('setup_grade', '?')
        risk = r.get('dilution_risk', 'UNKNOWN')
        float_shares = r.get('float_shares', 0)
        float_turnover = r.get('float_turnover')
        dvol = r.get('dollar_volume', 0)
        catalyst = r.get('catalyst', '—')
        
        float_str = f"{float_shares/1_000_000:.1f}M" if float_shares > 0 else "❓"
        turnover_str = f"{float_turnover:.1f}x" if float_turnover else "❓"
        dvol_str = f"${dvol/1_000_000:.1f}M" if dvol >= 1_000_000 else f"${dvol/1_000:.0f}K"
        
        lines.append("")
        lines.append(f"🥇 <b>{ticker}</b> — {event_score:.0f}/100")
        lines.append(f"   דירוג: {grade}  |  סיכון: {risk}")
        lines.append(f"   Gap: {gap:+.1f}%  |  RVOL: {rvol:.1f}x")
        lines.append(f"   Float: {float_str}  |  מחזור: {turnover_str}")
        lines.append(f"   DVol: {dvol_str}  |  Catalyst: {catalyst[:30]}")
        
    if rejected:
        lines.append("")
        lines.append("━━━━━━━━━━━━━━━━━━")
        lines.append("🚫 <b>נפסלו</b>")
        for r in rejected[:5]:
            lines.append(f"   • {r['ticker']} — Event Score: {r.get('event_score', 0):.0f}")
            
    lines += [
        "",
        "━━━━━━━━━━━━━━━━━━",
        "🤖 QUANT LEADER: המניה המובילה במדדי מומנטום, נזילות וסיכון",
        "⚠️ ניתוח בלבד – לא המלצת השקעה"
    ]
    return "\n".join(lines)
