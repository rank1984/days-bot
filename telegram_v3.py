"""
telegram_v3.py – V3.5 Telegram Formatter
Research Report, Trade Card, Debug, No Candidates
"""

import requests
from datetime import datetime
import pytz

ET = pytz.timezone("America/New_York")


def send_message(token: str, chat_id: str, text: str) -> bool:
    """
    Send a Telegram message with automatic fallback from HTML to plain text.
    """
    if not token or not chat_id:
        return False

    url = f"https://api.telegram.org/bot{token}/sendMessage"

    for parse_mode in ["HTML", None]:
        try:
            payload = {
                "chat_id": chat_id,
                "text": text,
                "disable_web_page_preview": True,
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


# ============================================================
# RESEARCH REPORT (V3.5)
# ============================================================

def format_research_report(result: dict, now_et: datetime) -> str:
    """
    Full research report with Top 5, Funnel, Near Misses, Market Regime, Decision.
    Always sent, even when there are no trade candidates.
    """
    lines = []
    lines.append("━━━━━━━━━━━━━━━━━━━━")
    lines.append("📊 DAYS-BOT V3.5 – RESEARCH SCAN")
    lines.append(f"📅 {now_et.strftime('%Y-%m-%d')} | 🕐 {now_et.strftime('%H:%M')} ET")
    lines.append("━━━━━━━━━━━━━━━━━━━━")

    # Market Regime
    regime = result.get('regime', {})
    lines.append("🧭 MARKET REGIME")
    lines.append(regime.get('description', 'Unknown'))
    lines.append("")

    # Discovery Funnel
    funnel = result.get('funnel', {})
    lines.append("━━━━━━━━━━━━━━━━━━━━")
    lines.append("🔎 DISCOVERY FUNNEL")
    lines.append("━━━━━━━━━━━━━━━━━━━━")
    lines.append(f"Universe:              {funnel.get('universe', 0)}")
    lines.append(f"Discovery qualified:   {funnel.get('discovery', 0)}")
    lines.append(f"Analysis qualified:    {funnel.get('analysis', 0)}")
    lines.append(f"Trade Candidates:      {funnel.get('trade', 0)}")
    lines.append("")

    # Top 5 Discovery
    top5 = result.get('top5', [])
    lines.append("━━━━━━━━━━━━━━━━━━━━")
    lines.append("🏆 TOP 5 DISCOVERY")
    lines.append("━━━━━━━━━━━━━━━━━━━━")

    for i, c in enumerate(top5, 1):
        a = c.get('analysis', {})
        lines.append(f"{i}️⃣ {c['ticker']}")
        lines.append(f"Score: {c.get('composite_score', c.get('event_score', 0))}/100")
        lines.append(f"Price: ${c['price']:.2f} | Gap: {c['gap_pct']:+.1f}%")
        lines.append(f"PM Vol: {c.get('pm_volume', 0):,}")
        if a.get('rvol'):
            lines.append(f"RVOL: {a['rvol']:.1f}x")
        if a.get('float'):
            lines.append(f"Float: {a['float']:,.0f}")
        if a.get('short_interest'):
            lines.append(f"Short Interest: {a['short_interest']*100:.1f}%")
        lines.append(f"PMH: ${c.get('pm_high', 0):.2f} | VWAP: ${c.get('pm_vwap', 0):.2f}")

        # Status
        if c.get('plan_valid', False):
            lines.append("✅ FINAL: TRADE CANDIDATE")
        else:
            reason = "Not qualified"
            if a.get('personality', {}).get('personality') == "GAP_AND_CRAP":
                reason = "Personality = GAP_AND_CRAP"
            elif a.get('sec_risk', {}).get('has_offering'):
                reason = "SEC risk detected"
            elif a.get('rvol', 0) < 3:
                reason = "RVOL below threshold"
            elif c.get('pm_dist_signed', 0) < 0:
                reason = "Below PM High"
            lines.append(f"❌ FINAL: NO TRADE – {reason}")
        lines.append("")

    # Near Misses
    near_misses = result.get('near_misses', [])
    if near_misses:
        lines.append("━━━━━━━━━━━━━━━━━━━━")
        lines.append("🎯 NEAR MISSES")
        lines.append("━━━━━━━━━━━━━━━━━━━━")
        for nm in near_misses:
            lines.append(f"🥇 {nm['ticker']} — {nm['score']}/100")
            lines.append(f"Missing: {nm['reason']}")
            lines.append("")

    # Trade Candidates (if any)
    trade_candidates = result.get('trade_candidates', [])
    if trade_candidates:
        lines.append("━━━━━━━━━━━━━━━━━━━━")
        lines.append("✅ TRADE CANDIDATES")
        lines.append("━━━━━━━━━━━━━━━━━━━━")
        for c in trade_candidates[:3]:
            lines.append(f"• {c['ticker']} – Entry: ${c.get('entry', 0):.2f} | Stop: ${c.get('stop', 0):.2f}")
            lines.append(f"  T1: ${c.get('target_1', 0):.2f} | T2: ${c.get('target_2', 0):.2f} | Shares: {c.get('position_size', 0)}")
    else:
        lines.append("━━━━━━━━━━━━━━━━━━━━")
        lines.append("🚫 DECISION: NO TRADE")
        lines.append("No setup met all confirmation criteria.")
        lines.append("The Top 5 above are the strongest discoveries.")

    lines.append("")
    lines.append("⏳ Next scan: 09:30 ET")
    lines.append("━━━━━━━━━━━━━━━━━━━━")
    lines.append("🤖 DAYS-BOT V3.5 – MANUAL EXECUTION ONLY")
    return "\n".join(lines)


# ============================================================
# V3.4 TRADE CARD
# ============================================================

def format_trade_card_v34(candidate: dict) -> str:
    """
    Detailed trade card for a single candidate.
    Used for top pick when trade candidates exist.
    """
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

    # Fundamentals
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
            lines.append(f"  RS: {rs:.2f}")
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


# ============================================================
# NO CANDIDATES (Fallback)
# ============================================================

def format_no_candidates_v34(date: str, now_et: datetime, learning_mode: bool, debug: bool) -> str:
    """
    Fallback message when even research engine yields nothing.
    """
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


# ============================================================
# DEBUG REPORT
# ============================================================

def format_debug_report(candidate: dict) -> str:
    """
    Detailed debug view for a single candidate, showing all fields.
    """
    a = candidate.get('analysis', {})
    lines = []
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
# LEGACY FORMAT (V3.0 / V3.1 / V3.2 – kept for compatibility)
# ============================================================

def format_decision_card(stock_data: dict, quant_data: dict, ai_decision: dict) -> str:
    """Legacy V3.0 format."""
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


def format_trade_card_v31(plan: dict) -> str:
    """Legacy V3.1 format."""
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
