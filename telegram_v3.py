"""
telegram_v3.py – V3.4 Telegram Formatter with HTML fallback to plain text
"""
import requests
from datetime import datetime
import pytz

ET = pytz.timezone("America/New_York")

def send_message(token: str, chat_id: str, text: str) -> bool:
    if not token or not chat_id:
        return False
    url = f"https://api.telegram.org/bot{token}/sendMessage"
    # Try HTML first
    for parse_mode in ["HTML", None]:
        try:
            payload = {
                "chat_id": chat_id,
                "text": text,
                "disable_web_page_preview": True
            }
            if parse_mode:
                payload["parse_mode"] = parse_mode
            resp = requests.post(url, json=payload, timeout=30)
            if resp.status_code == 200:
                return True
            print(f"[Telegram] {parse_mode} failed: {resp.status_code}")
        except Exception as e:
            print(f"[Telegram] {parse_mode} error: {e}")
    return False

def format_trade_card_v34(candidate: dict) -> str:
    a = candidate.get('analysis', {})
    lines = []
    lines.append("━━━━━━━━━━━━━━━━━━━━")
    lines.append(f"🚀 {candidate['ticker']} – TOP PICK")
    lines.append(f"ציון: {candidate.get('event_score', 0)}/100")
    lines.append("━━━━━━━━━━━━━━━━━━━━")
    lines.append(f"💰 מחיר: ${candidate['price']:.2f}  |  Gap: {candidate['gap_pct']:+.1f}%")
    lines.append(f"📊 PM High: ${candidate['pm_high']:.2f}  |  VWAP: ${candidate['pm_vwap']:.2f}")
    lines.append(f"📦 PM Volume: {candidate['pm_volume']:,}")
    lines.append("")
    float_val = a.get('float', 0)
    short = a.get('short_interest', 0)
    rvol = a.get('rvol', 0)
    rs = a.get('rs', 0)
    if float_val or short or rvol:
        lines.append("📊 FUNDAMENTALS:")
        if float_val: lines.append(f"  Float: {float_val:,.0f}")
        if short: lines.append(f"  Short Interest: {short*100:.1f}%")
        if rvol: lines.append(f"  RVOL: {rvol:.1f}x")
        if rs: lines.append(f"  RS: {rs:.2f}")
        lines.append("")
    personality = a.get('personality', {})
    if personality.get('sample_size', 0) > 0:
        lines.append("🧠 PERSONALITY:")
        lines.append(f"  Type: {personality.get('personality', 'NEUTRAL')}")
        lines.append(f"  Failure Rate: {personality.get('failure_rate', 0):.1f}%")
        lines.append("")
    catalyst = a.get('catalyst', {})
    if catalyst.get('type') and catalyst.get('type') != "NO_NEWS":
        lines.append("🔬 CATALYST:")
        lines.append(f"  Type: {catalyst.get('type', 'UNKNOWN')}")
        lines.append(f"  Quality: {catalyst.get('score', 0)}/10")
        lines.append(f"  {catalyst.get('summary', '')}")
        lines.append("")
    sent = a.get('sentiment', {})
    if sent.get('total_messages', 0) > 0:
        lines.append("💬 SENTIMENT:")
        lines.append(f"  Bull: {sent.get('bull_pct', 0):.0f}%  Bear: {sent.get('bear_pct', 0):.0f}%")
        lines.append(f"  Net: {sent.get('sentiment_score', 0):.2f}")
        lines.append("")
    sec = a.get('sec_risk', {})
    if sec.get('has_offering'):
        lines.append(f"⚠️ SEC RISK: {sec.get('risk_level')} – {sec.get('filing_type')}")
        lines.append("")
    lines.append("━━━━━━━━━━━━━━━━━━━━")
    lines.append("🎯 TRADE PLAN")
    lines.append("━━━━━━━━━━━━━━━━━━━━")
    lines.append(f"STATUS: {candidate.get('decision', 'WATCH')}")
    lines.append("")
    lines.append(f"Entry: ${candidate.get('entry', 0):.2f}")
    lines.append(f"Stop:  ${candidate.get('stop', 0):.2f}")
    lines.append(f"T1:    ${candidate.get('target_1', 0):.2f}")
    lines.append(f"T2:    ${candidate.get('target_2', 0):.2f}")
    lines.append(f"Risk/share: ${candidate.get('risk_per_share', 0):.2f}")
    lines.append(f"Shares: {candidate.get('position_size', 0)}")
    lines.append(f"Max Loss: ${candidate.get('max_loss', 0):.2f}")
    lines.append("")
    lines.append(f"⏱ Hold: {candidate.get('hold_type', 'NONE')}")
    lines.append("")
    lines.append("❌ CANCEL IF:")
    for cond in candidate.get('invalidation_conditions', ['VWAP lost', 'Breakout fails']):
        lines.append(f"  • {cond}")
    lines.append("")
    lines.append("━━━━━━━━━━━━━━━━━━━━")
    lines.append("⚠️ MANUAL EXECUTION ONLY")
    return "\n".join(lines)

def format_no_candidates_v34(date: str, now_et, learning_mode: bool, debug: bool) -> str:
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
    lines.append("🔒 <b>מסננים מלאים</b>")
    lines.append("  הפעל עם --debug כדי לראות את כל המועמדים:")
    lines.append("  python main.py fullscan_v34 --manual --debug")
    lines.append("")
    lines.append("⏳ <b>הסריקה הבאה בעוד 15 דקות</b>")
    lines.append("")
    lines.append("━━━━━━━━━━━━━━━━━━━━")
    lines.append("🤖 DAYS-BOT – ביצוע ידני בלבד")
    return "\n".join(lines)