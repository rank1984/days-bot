def format_decision_card(stock_data, quant_data, ai_data):
    """
    Builds the V3.0 Telegram Decision Card.
    """
    # Emojis for states
    decision = ai_data.get('decision', 'NO TRADE').upper()
    state_emoji = "🟢 TRADE SETUP" if decision == "TRADE" else ("🟡 WAIT SETUP" if decision == "WAIT" else "🔴 NO TRADE")
    regime = quant_data.get('regime', 'NEUTRAL')
    regime_emoji = "🟢" if regime == "FAVORABLE" else ("🟡" if regime == "NEUTRAL" else "🔴")
    
    # Format the Why/Risks lists
    whys = "\n".join([f"+ {w}" for w in ai_data.get('why_list', [])])
    risks = "\n".join([f"- {r}" for r in ai_data.get('risks_list', [])])
    
    ticker = stock_data.get('ticker', 'UNKNOWN')
    
    msg = f"""
━━━━━━━━━━━━━━━━━━━━
🚨 DAYS-BOT V3.0
━━━━━━━━━━━━━━━━━━━━
🥇 {ticker}
{state_emoji}

AI SCORE: {ai_data.get('score')}/100
REGIME: {regime_emoji} {regime}

Price:      ${stock_data.get('price')}
Trigger:    ${quant_data.get('trigger')}
Entry:      ${quant_data.get('entry_min')} - ${quant_data.get('entry_max')}
Stop:       ${quant_data.get('stop')}
T1:         ${quant_data.get('t1')}
T2:         ${quant_data.get('t2')}

RISK:       ${quant_data.get('risk_dollar')}
POSITION:   {quant_data.get('shares')} shares

TYPE:       {ai_data.get('trade_type')}
HOLD:       {ai_data.get('expected_hold')}

🟢 BUY WHEN:
✅ Break ${quant_data.get('trigger')}
✅ Volume confirms
✅ Spread < 1.5%
✅ Above VWAP

🔴 CANCEL IF:
❌ Failed breakout
❌ VWAP loss
❌ Spread expansion

Confidence: {ai_data.get('confidence')}

WHY THIS STOCK?
{whys}

RISKS
{risks}
━━━━━━━━━━━━━━━━━━━━
"""
    return msg.strip()
