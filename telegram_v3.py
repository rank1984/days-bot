"""
V3.2 – Single Decision Card
"""
def format_trade_card_v32(candidate, plan, confirmed=False):
    lines = []
    lines.append("━━━━━━━━━━━━━━━━━━━━")
    lines.append("🚨 DAYS-BOT V3.2")
    lines.append("TRADE DECISION" if confirmed else "PRE-MARKET WATCH")
    lines.append("━━━━━━━━━━━━━━━━━━━━")
    lines.append(f"🥇 {candidate['ticker']}")
    lines.append(f"Score: {candidate['opportunity_score']}/100")
    lines.append(f"Grade: {candidate['grade']}")
    lines.append("")
    lines.append("📈 SETUP")
    lines.append(f"Gap:       {candidate['gap_pct']:+.1f}%")
    lines.append(f"PM High:   ${candidate['pm_high']:.2f}")
    lines.append(f"VWAP:      ${candidate['pm_vwap']:.2f}")
    lines.append(f"PM Volume: {candidate['pm_volume']:,}")
    lines.append("")
    if confirmed:
        lines.append("🟢 STATUS: CONFIRMED BREAKOUT")
        lines.append(f"Current: ${candidate.get('current_price', 0):.2f}")
    else:
        lines.append("🟡 STATUS: WAIT FOR BREAKOUT")

    if plan.get('decision') != "NO TRADE":
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
        for cond in plan['invalidation_conditions']:
            lines.append(f"• {cond}")
    else:
        lines.append("")
        lines.append("❌ NO TRADE – " + plan.get('reason', ''))

    lines.append("")
    lines.append("🤖 AI (summary)")
    lines.append("Strong setup, but manual execution required.")
    lines.append("━━━━━━━━━━━━━━━━━━━━")
    return "\n".join(lines)
