"""
telegram_v3.py – V3.0 Decision Cards & V3.1 Trade Plan Cards
"""

import requests
from datetime import datetime
import pytz

ET = pytz.timezone("America/New_York")


def send_message(token: str, chat_id: str, text: str) -> bool:
    """Send a Telegram message (duplicated here for safety if import fails)."""
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
# V3.1 NEW FORMAT (FULL TRADE PLAN CARD)
# ============================================================

def format_trade_card_v31(plan: dict) -> str:
    """
    Format a V3.1 trade plan (enriched candidate) into a beautiful Telegram message.
    Expects all keys from build_trade_plan to be present.
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
