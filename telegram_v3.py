"""
telegram_v3.py – V3.0 Decision Cards & V3.1/V3.2/V3.3/V3.4 Trade Plan Cards
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
# V3.0 LEGACY FORMAT (KEPT FOR COMPATIBILITY)
# ============================================================

def format_decision_card(stock_data: dict, quant_data: dict, ai_decision: dict) -> str:
    """Legacy V3.0 format - kept to avoid breaking existing code."""
    time_str = datetime.now(ET).strftime("%H:%M ET")
    ticker = stock_data.get("ticker", "???")
    price = stock_data.get("price", 0)
    gap = stock_data.get("gap_pct", 0)
    
    decision = ai_decision.get("decision", "HOLD")
    score = ai_decision.get("score", 0)
    reasoning = ai_decision.get("reasoning", "No reasoning provided.")
    
    regime = quant_data.get("regime", "NEUTRAL")
    entry = quant_data.get("entry", 0)
    stop = quant_data.get("stop", 0)
    tp1 = quant_data.get("tp1", 0)
    tp2 = quant_data.get("tp2", 0)
    
    lines = [
        "🚀 <b>DAYS-BOT V3.0 – DECISION</b>",
        f"📅 {datetime.now(ET).strftime('%Y-%m-%d')}  |  🕐 {time_str}",
        "━━━━━━━━━━━━━━━━━━",
        f"<b>{ticker}</b>  💰 ${price:.2f}  Gap: {gap:+.1f}%",
        f"📊 Regime: {regime}",
        "━━━━━━━━━━━━━━━━━━",
        f"🎯 <b>DECISION: {decision}</b>",
        f"🏆 Score: {score}/100",
        "━━━━━━━━━━━━━━━━━━",
        "📊 <b>Trade Plan</b>",
        f"Entry: ${entry:.2f}",
        f"Stop:  ${stop:.2f}",
        f"TP1:   ${tp1:.2f}",
        f"TP2:   ${tp2:.2f}",
        "━━━━━━━━━━━━━━━━━━",
        f"🧠 <b>AI Analysis</b>",
        reasoning,
        "━━━━━━━━━━━━━━━━━━",
        "⚠️ <b>MANUAL EXECUTION</b>",
        "🚫 לא המלצת השקעה"
    ]
    return "\n".join(lines)


# ============================================================
# V3.1 / V3.2 TRADE PLAN CARD
# ============================================================

def format_trade_card_v31(plan: dict) -> str:
    """
    Format a V3.1 trade plan (enriched candidate) into a beautiful Telegram message.
    """
    lines = []
    lines.append("🚨 DAYS-BOT V3.1")
    lines.append("")
    lines.append(f"🏆 TOP SETUP")
    lines.append("")
    lines.append(f"{plan['ticker']}")
    lines.append(f"${plan['price']:.2f}")
    lines.append(f"Gap {plan.get('gap_pct', 0):+.1f}%")
    lines.append("━━━━━━━━━━━━━━━━")
    lines.append("")
    lines.append("📊 SETUP")
    lines.append(f"Score: {plan.get('opportunity_score', 0):.0f}/100")
    lines.append(f"Grade: {plan.get('grade', 'N/A')}")
    lines.append(f"PM Volume: {plan.get('pm_volume', 0):,}")
    lines.append(f"PM High: ${plan.get('pm_high', 0):.2f}")
    lines.append(f"PM VWAP: ${plan.get('pm_vwap', 0):.2f}")
    lines.append(f"PM Data: {plan.get('pm_data_quality', 'UNKNOWN')}")
    lines.append("")
    lines.append("━━━━━━━━━━━━━━━━")
    lines.append("")
    lines.append("🎯 TRADE PLAN")
    lines.append("")
    lines.append(f"DECISION: {plan.get('decision_detail', 'N/A')}")
    lines.append("")
    
    if plan.get('entry') is not None:
        lines.append(f"BUY TRIGGER: ${plan['entry']:.2f}")
        lines.append(f"STOP: ${plan['stop']:.2f}")
        lines.append(f"TARGET 1: ${plan['target_1']:.2f}")
        lines.append(f"TARGET 2: ${plan['target_2']:.2f}")
        lines.append(f"RISK: ${plan['risk_per_share']:.2f}/share")
        lines.append(f"R:R: {plan.get('risk_reward_1', 0):.1f}R / {plan.get('risk_reward_2', 0):.1f}R")
        lines.append("")
        lines.append("💰 POSITION")
        lines.append(f"Account: ${plan.get('account_size', 5000):,.0f}")
        lines.append(f"Risk: {plan.get('risk_pct', 0.5)*100:.1f}%")
        lines.append(f"Max Loss: ${plan.get('risk_dollars', 0):.2f}")
        lines.append(f"Suggested: {plan.get('position_shares', 0)} shares")
        lines.append("")
        lines.append("⏱ HOLD")
        lines.append(f"{plan.get('hold_type', 'NONE')}")
        lines.append(f"{plan.get('hold_min', 0)}–{plan.get('hold_max', 0)} minutes")
        lines.append("OVERNIGHT: ❌ NO")
        lines.append("")
        lines.append("🟢 CONFIRMATION")
        lines.append("✓ Break PM High")
        lines.append("✓ Volume expansion")
        lines.append("✓ Above VWAP")
        lines.append("")
        lines.append("🔴 INVALIDATION")
        for cond in plan.get('invalidation_conditions', []):
            lines.append(f"✗ {cond}")
        lines.append("")
        lines.append("🧠 AI ANALYSIS")
        lines.append("Strong gap-and-go structure. Wait for confirmation.")
        lines.append("")
        lines.append("⚠️ MANUAL EXECUTION")
        lines.append("No automatic order placed.")
    else:
        lines.append("❌ NO TRADE – " + plan.get('decision_detail', ''))
    
    return "\n".join(lines)


# ============================================================
# V3.2 OPENING CONFIRMATION CARD
# ============================================================

def format_trade_card_v32(candidate, plan, confirmed=False):
    """V3.2 format with opening confirmation status."""
    lines = []
    lines.append("━━━━━━━━━━━━━━━━━━━━")
    lines.append("🚨 DAYS-BOT V3.2")
    lines.append("TRADE DECISION" if confirmed else "PRE-MARKET WATCH")
    lines.append("━━━━━━━━━━━━━━━━━━━━")
    lines.append(f"🥇 {candidate['ticker']}")
    lines.append(f"Score: {candidate.get('opportunity_score', 0)}/100")
    lines.append(f"Grade: {candidate.get('grade', 'N/A')}")
    lines.append("")
    lines.append("📈 SETUP")
    lines.append(f"Gap:       {candidate.get('gap_pct', 0):+.1f}%")
    lines.append(f"PM High:   ${candidate.get('pm_high', 0):.2f}")
    lines.append(f"VWAP:      ${candidate.get('pm_vwap', 0):.2f}")
    lines.append(f"PM Volume: {candidate.get('pm_volume', 0):,}")
    lines.append("")
    if confirmed:
        lines.append("🟢 STATUS: CONFIRMED BREAKOUT")
        lines.append(f"Current: ${candidate.get('current_price', 0):.2f}")
    else:
        lines.append("🟡 STATUS: WAIT FOR BREAKOUT")

    if plan.get('decision') != "NO TRADE" and plan.get('entry') is not None:
        lines.append("")
        lines.append("🎯 ENTRY")
        lines.append(f"${plan['entry']:.2f}")
        lines.append("")
        lines.append("🛑 STOP")
        lines.append(f"${plan['stop']:.2f}")
        lines.append("")
        lines.append("🎯 TARGETS")
        lines.append(f"T1 ${plan['target_1']:.2f}  (+{((plan['target_1']-plan['entry'])/plan['entry']*100):.1f}%)")
        lines.append(f"T2 ${plan['target_2']:.2f}  (+{((plan['target_2']-plan['entry'])/plan['entry']*100):.1f}%)")
        lines.append("")
        lines.append("⚖️ RISK")
        lines.append(f"Risk/share: ${plan['risk_per_share']:.2f}")
        lines.append(f"Suggested shares: {plan['position_shares']}")
        lines.append(f"Max loss: ~${plan['risk_dollars']:.2f}")
        lines.append("")
        lines.append("⏱ HOLDING PLAN")
        lines.append(f"{plan['hold_type']} ({plan['hold_min']}-{plan['hold_max']} min)")
        lines.append("")
        lines.append("🔔 TRIGGER")
        lines.append("Close above PM High + volume confirmation")
        lines.append("")
        lines.append("❌ CANCEL IF")
        for cond in plan.get('invalidation_conditions', []):
            lines.append(f"• {cond}")
    else:
        lines.append("")
        lines.append("❌ NO TRADE – " + plan.get('reason', 'Score too low'))

    lines.append("")
    lines.append("🤖 AI (summary)")
    lines.append("Strong setup, but manual execution required.")
    lines.append("━━━━━━━━━━━━━━━━━━━━")
    return "\n".join(lines)


# ============================================================
# V3.3 / V3.4 FULL ANALYSIS CARD (WITH ALL METRICS)
# ============================================================

def format_full_alert_v33(candidate: dict) -> str:
    """
    פורמט עשיר עם כל הנתונים החדשים של V3.3/V3.4:
    Float, Short Interest, RVOL, RS, Catalyst, Sentiment, SEC Risk,
    Personality, Sympathy, VWAP (V3.4)
    """
    lines = []
    a = candidate.get('analysis', {})
    plan = candidate  # candidate already contains all trade plan fields

    lines.append("━━━━━━━━━━━━━━━━━━━━")
    lines.append(f"🚀 {candidate['ticker']} – TOP PICK")
    lines.append(f"ציון כולל: {candidate.get('composite_score', 0)}/100")
    lines.append("━━━━━━━━━━━━━━━━━━━━")

    # Price & Gap
    lines.append(f"💰 מחיר: ${candidate['price']:.2f}  |  Gap: {candidate['gap_pct']:+.1f}%")
    lines.append(f"📊 PM High: ${candidate['pm_high']:.2f}  |  PM VWAP: ${candidate.get('pm_vwap', 0):.2f}")
    lines.append(f"📦 PM Volume: {candidate['pm_volume']:,}")
    lines.append("")

    # VWAP Data (V3.4)
    vwap = a.get('vwap', {})
    if vwap:
        lines.append("📈 VWAP LEVELS:")
        lines.append(f"  VWAP: ${vwap.get('vwap', 0):.2f}")
        lines.append(f"  Support: ${vwap.get('vwap_support', 0):.2f}")
        lines.append(f"  Resistance: ${vwap.get('vwap_resistance', 0):.2f}")
        lines.append("")

    # Fundamental Data
    float_val = a.get('float', 0)
    short = a.get('short_interest', 0)
    rvol = a.get('rvol', 0)
    rs = a.get('rs', 0)
    lines.append("📊 FUNDAMENTALS:")
    lines.append(f"  Float: {float_val:,.0f}" if float_val else "  Float: N/A")
    lines.append(f"  Short Interest: {short*100:.1f}%" if short else "  Short Interest: N/A")
    lines.append(f"  RVOL: {rvol:.1f}x" if rvol else "  RVOL: N/A")
    lines.append(f"  Relative Strength: {rs:.2f}" if rs else "  RS: N/A")
    lines.append("")

    # Personality (V3.4)
    personality = a.get('personality', {})
    if personality.get('sample_size', 0) > 0:
        lines.append("🧠 STOCK PERSONALITY:")
        lines.append(f"  Type: {personality.get('personality', 'NEUTRAL')}")
        lines.append(f"  Avg 30min Return: {personality.get('avg_30min_return', 0):.1f}%")
        lines.append(f"  Failure Rate: {personality.get('failure_rate', 0):.1f}%")
        lines.append(f"  Sample Size: {personality.get('sample_size', 0)}")
        lines.append("")

    # News & Catalyst
    headlines = a.get('news', [])
    catalyst = a.get('catalyst', {})
    lines.append("📰 NEWS:")
    if headlines:
        for h in headlines[:3]:
            lines.append(f"  • {h}")
    else:
        lines.append("  • No recent news")
    lines.append("")
    lines.append(f"🔬 Catalyst Type: {catalyst.get('type', 'UNKNOWN')}")
    lines.append(f"  Quality Score: {catalyst.get('score', 0)}/10")
    lines.append(f"  {catalyst.get('summary', '')}")

    # Sentiment
    sent = a.get('sentiment', {})
    lines.append("")
    lines.append(f"💬 Sentiment: {sent.get('bull_pct', 0):.0f}% Bull / {sent.get('bear_pct', 0):.0f}% Bear")
    lines.append(f"  Net Score: {sent.get('sentiment_score', 0):.2f}")

    # SEC Risk
    sec = a.get('sec_risk', {})
    if sec.get('has_offering'):
        lines.append("")
        lines.append(f"⚠️ SEC RISK: {sec.get('risk_level')} – Offering filing detected ({sec.get('filing_type')})")
    else:
        lines.append("")
        lines.append("✅ No active SEC offering detected.")

    # Sympathy Plays (V3.4)
    sympathy = a.get('sympathy', [])
    if sympathy:
        lines.append("")
        lines.append("🔄 SYMPATHY PLAYS (same sector):")
        for s in sympathy[:3]:
            lines.append(f"  • {s['ticker']} – ${s['price']:.2f} (vol: {s.get('pm_volume', 0):,})")
        lines.append(f"  Source: {sympathy[0].get('source', 'N/A')}")

    # Trade Plan
    lines.append("")
    lines.append("🎯 TRADE PLAN:")
    lines.append(f"  Entry: ${candidate.get('entry', 0):.2f}")
    lines.append(f"  Stop:  ${candidate.get('stop', 0):.2f}")
    lines.append(f"  T1:    ${candidate.get('target_1', 0):.2f}  ({candidate.get('risk_reward_1', 0):.1f}R)")
    lines.append(f"  T2:    ${candidate.get('target_2', 0):.2f}  ({candidate.get('risk_reward_2', 0):.1f}R)")
    lines.append(f"  Shares: {candidate.get('position_shares', 0)}")
    lines.append(f"  Max Loss: ${candidate.get('risk_dollars', 0):.2f}")

    # Hold Time
    lines.append("")
    lines.append(f"⏱ Hold: {candidate.get('hold_type', 'NONE')} ({candidate.get('hold_min', 0)}-{candidate.get('hold_max', 0)} min)")

    # AI Summary
    lines.append("")
    lines.append("🧠 AI SUMMARY:")
    lines.append(candidate.get('ai_summary', 'N/A'))

    # Invalidation
    lines.append("")
    lines.append("❌ CANCEL IF:")
    for cond in candidate.get('invalidation_conditions', []):
        lines.append(f"  • {cond}")

    lines.append("━━━━━━━━━━━━━━━━━━━━")
    lines.append("⚠️ MANUAL EXECUTION ONLY")
    return "\n".join(lines)
