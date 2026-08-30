"""
telegram_v3.py – V3.4 Trade Card Formatter
"""

import requests
from datetime import datetime
import pytz

ET = pytz.timezone("America/New_York")


def send_message(token: str, chat_id: str, text: str) -> bool:
    """Send a Telegram message"""
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
        print(f"[Telegram] Failed: {resp.status_code}")
        return False
    except Exception as e:
        print(f"[Telegram] Error: {e}")
        return False


# ============================================================
# V3.4 TRADE CARD
# ============================================================

def format_trade_card_v34(candidate: dict) -> str:
    """
    פורמט V3.4 – מציג את כל הנתונים הרלוונטיים למסחר:
    - Score, Gap, PM Volume, PM High, VWAP
    - Float, Short Interest, RVOL, RS
    - Personality, Catalyst, Sentiment, SEC Risk
    - Entry, Stop, Targets, Position Size, Max Loss
    - Hold Type, Decision, Invalidation
    """
    a = candidate.get('analysis', {})
    lines = []

    lines.append("━━━━━━━━━━━━━━━━━━━━")
    lines.append(f"🚀 {candidate['ticker']} – TOP PICK")
    lines.append(f"ציון: {candidate.get('event_score', 0)}/100")
    lines.append("━━━━━━━━━━━━━━━━━━━━")

    # Price & Gap
    lines.append(f"💰 מחיר: ${candidate['price']:.2f}  |  Gap: {candidate['gap_pct']:+.1f}%")
    lines.append(f"📊 PM High: ${candidate['pm_high']:.2f}  |  VWAP: ${candidate['pm_vwap']:.2f}")
    lines.append(f"📦 PM Volume: {candidate['pm_volume']:,}")
    lines.append("")

    # Fundamentals (if available)
    float_val = a.get('float', 0)
    short = a.get('short_interest', 0)
    rvol = a.get('rvol', 0)
    rs = a.get('rs', 0)
    if float_val or short or rvol:
        lines.append("📊 FUNDAMENTALS:")
        if float_val:
            lines.append(f"  Float: {float_val:,.0f}")
        if short:
            lines.append(f"  Short Interest: {short*100:.1f}%")
        if rvol:
            lines.append(f"  RVOL: {rvol:.1f}x")
        if rs:
            lines.append(f"  Relative Strength: {rs:.2f}")
        lines.append("")

    # Personality
    personality = a.get('personality', {})
    if personality.get('sample_size', 0) > 0:
        lines.append("🧠 PERSONALITY:")
        lines.append(f"  Type: {personality.get('personality', 'NEUTRAL')}")
        lines.append(f"  Failure Rate: {personality.get('failure_rate', 0):.1f}%")
        lines.append("")

    # Catalyst
    catalyst = a.get('catalyst', {})
    if catalyst.get('type') and catalyst.get('type') != "NO_NEWS":
        lines.append("🔬 CATALYST:")
        lines.append(f"  Type: {catalyst.get('type', 'UNKNOWN')}")
        lines.append(f"  Quality: {catalyst.get('score', 0)}/10")
        lines.append(f"  {catalyst.get('summary', '')}")
        lines.append("")

    # Sentiment
    sent = a.get('sentiment', {})
    if sent.get('total_messages', 0) > 0:
        lines.append("💬 SENTIMENT:")
        lines.append(f"  Bull: {sent.get('bull_pct', 0):.0f}%  Bear: {sent.get('bear_pct', 0):.0f}%")
        lines.append(f"  Net: {sent.get('sentiment_score', 0):.2f}")
        lines.append("")

    # SEC Risk
    sec = a.get('sec_risk', {})
    if sec.get('has_offering'):
        lines.append(f"⚠️ SEC RISK: {sec.get('risk_level')} – {sec.get('filing_type')}")
        lines.append("")

    # Sympathy Plays
    sympathy = a.get('sympathy', [])
    if sympathy:
        lines.append("🔄 SYMPATHY PLAYS:")
        for s in sympathy[:3]:
            lines.append(f"  • {s['ticker']} – ${s['price']:.2f} (vol: {s.get('pm_volume', 0):,})")
        lines.append("")

    # Trade Plan
    lines.append("━━━━━━━━━━━━━━━━━━━━")
    lines.append("🎯 TRADE PLAN")
    lines.append("━━━━━━━━━━━━━━━━━━━━")
    lines.append(f"STATUS: {candidate.get('decision', 'WATCH')}")
    lines.append("")
    lines.append(f"Entry: ${candidate.get('entry', 0):.2f}")
    lines.append(f"Stop:  ${candidate.get('stop', 0):.2f}")
    lines.append(f"T1:    ${candidate.get('target_1', 0):.2f}  ({candidate.get('risk_reward_1', 0):.1f}R)")
    lines.append(f"T2:    ${candidate.get('target_2', 0):.2f}  ({candidate.get('risk_reward_2', 0):.1f}R)")
    lines.append("")
    lines.append(f"Risk/share: ${candidate.get('risk_per_share', 0):.2f}")
    lines.append(f"Shares: {candidate.get('position_size', 0)}")
    lines.append(f"Max Loss: ${candidate.get('max_loss', 0):.2f}")
    lines.append("")
    lines.append(f"⏱ Hold: {candidate.get('hold_type', 'NONE')}")
    lines.append("")
    lines.append("🔔 BUY ONLY IF:")
    lines.append("  ✓ Breakout confirmed")
    lines.append("  ✓ Volume expansion")
    lines.append("  ✓ Above VWAP")
    lines.append("  ✓ Spread acceptable")
    lines.append("")
    lines.append("❌ CANCEL IF:")
    for cond in candidate.get('invalidation_conditions', []):
        lines.append(f"  • {cond}")
    lines.append("")
    lines.append("🧠 AI SUMMARY:")
    lines.append(candidate.get('ai_summary', 'No AI summary available.'))
    lines.append("")
    lines.append("━━━━━━━━━━━━━━━━━━━━")
    lines.append("⚠️ MANUAL EXECUTION ONLY")
    return "\n".join(lines)


# ============================================================
# V3.3 FULL ALERT (KEPT FOR COMPATIBILITY)
# ============================================================

def format_full_alert_v33(candidate: dict) -> str:
    """Alias for format_trade_card_v34 (compatibility)"""
    return format_trade_card_v34(candidate)


# ============================================================
# DEBUG REPORT
# ============================================================

def format_debug_report(candidate: dict) -> str:
    """פורמט Debug – מציג את כל הנתונים הגולמיים של המועמד"""
    lines = []
    a = candidate.get('analysis', {})
    lines.append("━━━━━━━━━━━━━━━━━━━━")
    lines.append(f"🐞 DEBUG – {candidate['ticker']}")
    lines.append(f"ציון: {candidate.get('event_score', 0)}/100")
    lines.append("━━━━━━━━━━━━━━━━━━━━")
    lines.append(f"💰 מחיר: ${candidate['price']:.2f}  |  Gap: {candidate['gap_pct']:+.1f}%")
    lines.append(f"📊 PM High: ${candidate['pm_high']:.2f}  |  VWAP: ${candidate['pm_vwap']:.2f}")
    lines.append(f"📦 PM Volume: {candidate['pm_volume']:,}")
    lines.append("")

    float_val = a.get('float', 0)
    short = a.get('short_interest', 0)
    rvol = a.get('rvol', 0)
    lines.append("📊 FUNDAMENTALS:")
    lines.append(f"  Float: {float_val:,.0f}" if float_val else "  Float: N/A")
    lines.append(f"  Short Interest: {short*100:.1f}%" if short else "  Short Interest: N/A")
    lines.append(f"  RVOL: {rvol:.1f}x" if rvol else "  RVOL: N/A")
    lines.append("")

    personality = a.get('personality', {})
    if personality.get('sample_size', 0) > 0:
        lines.append(f"🧠 Personality: {personality.get('personality', 'NEUTRAL')} (Failure: {personality.get('failure_rate', 0):.1f}%)")

    catalyst = a.get('catalyst', {})
    lines.append(f"🔬 Catalyst: {catalyst.get('type', 'UNKNOWN')} (Score: {catalyst.get('score', 0)}/10)")

    sent = a.get('sentiment', {})
    lines.append(f"💬 Sentiment: {sent.get('bull_pct', 0):.0f}% Bull / {sent.get('bear_pct', 0):.0f}% Bear")

    sec = a.get('sec_risk', {})
    lines.append(f"⚠️ SEC Risk: {sec.get('risk_level', 'NONE')} – {sec.get('filing_type', 'No filing')}")
    lines.append("")

    lines.append("🎯 TRADE PLAN:")
    if candidate.get('entry'):
        lines.append(f"  Entry: ${candidate['entry']:.2f} | Stop: ${candidate['stop']:.2f}")
        lines.append(f"  T1: ${candidate['target_1']:.2f} ({candidate.get('risk_reward_1', 0):.1f}R)")
        lines.append(f"  T2: ${candidate['target_2']:.2f} ({candidate.get('risk_reward_2', 0):.1f}R)")
        lines.append(f"  Shares: {candidate.get('position_size', 0)}")
    else:
        lines.append("  ❌ No valid trade plan")
    lines.append("━━━━━━━━━━━━━━━━━━━━")
    return "\n".join(lines)


# ============================================================
# NO CANDIDATES MESSAGE
# ============================================================

def format_no_candidates_v34(date: str, now_et, learning_mode: bool, debug: bool) -> str:
    """הודעה כאשר אין מועמדים שעברו את כל המסננים"""
    lines = []
    lines.append("━━━━━━━━━━━━━━━━━━━━")
    lines.append("📊 DAYS-BOT V3.4 – דוח סריקה")
    lines.append(f"📅 {date}  |  🕐 {now_et.strftime('%H:%M:%S')} ET")
    lines.append("━━━━━━━━━━━━━━━━━━━━")
    lines.append("")
    lines.append("😴 <b>אין מועמדויות שעברו את כל המסננים</b>")
    lines.append("")
    lines.append("🔍 <b>סיבות אפשריות:</b>")
    lines.append("  • Gap < 10%")
    lines.append("  • RVOL < 3x")
    lines.append("  • Float > 50M")
    lines.append("  • SEC Offering detected")
    lines.append("  • Personality = GAP_AND_CRAP")
    lines.append("")
    if learning_mode:
        lines.append("📖 <b>LEARNING MODE פעיל</b>")
        lines.append("  המסננים מוקלים – חלק מהמועמדים")
        lines.append("  עדיין נפסלו בגלל תנאים קשים.")
    else:
        lines.append("🔒 <b>מסננים מלאים</b>")
        lines.append("  הפעל עם --debug כדי לראות את כל המועמדים:")
        lines.append("  python main.py fullscan_v34 --manual --debug")
    lines.append("")
    lines.append("📁 <b>לוג מלא</b>")
    lines.append(f"  data/logs/daily_log_{date}.json")
    lines.append("")
    lines.append("⏳ <b>הסריקה הבאה בעוד 15 דקות</b>")
    lines.append("")
    lines.append("━━━━━━━━━━━━━━━━━━━━")
    lines.append("🤖 DAYS-BOT – ביצוע ידני בלבד")
    return "\n".join(lines)
