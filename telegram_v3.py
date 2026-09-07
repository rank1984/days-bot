def format_research_report(candidates: list, now_et: datetime) -> str:
    lines = []
    lines.append("━━━━━━━━━━━━━━━━━━━━")
    lines.append("🚀 DAYS-BOT V5.0.1 – EARLY MOVE SCAN")
    lines.append(f"📅 {now_et.strftime('%d/%m/%Y')} | 🕐 {now_et.strftime('%H:%M')} ET")
    lines.append("━━━━━━━━━━━━━━━━━━━━")

    if not candidates:
        lines.append("😴 לא נמצאו מועמדים")
        return "\n".join(lines)

    top5 = sorted(candidates, key=lambda x: x.get('composite_score', 0), reverse=True)[:5]

    lines.append("")
    lines.append("━━━━━━━━━━━━━━━━━━━━")
    lines.append("🏆 TOP 5 – EARLY MOVE ANALYSIS")
    lines.append("━━━━━━━━━━━━━━━━━━━━")

    for i, c in enumerate(top5, 1):
        early_score = c.get('early_score', 0)
        early_state = c.get('early_state', 'UNKNOWN')
        components = c.get('early_components', {})

        lines.append(f"{i}️⃣ {c['ticker']}")
        lines.append(f"  Early Move: {early_score:.0f}/100")
        lines.append(f"  State: {early_state}")

        # Show key components if available
        if components:
            comp_str = []
            if components.get('pullback_buying', 0) > 40:
                comp_str.append("✅ Pullback Buying")
            if components.get('pmh_pressure', 0) > 40:
                comp_str.append("✅ PMH Pressure")
            if components.get('volume_acceleration', 0) > 40:
                comp_str.append("✅ Volume Accel")
            if components.get('price_acceleration', 0) > 40:
                comp_str.append("✅ Price Accel")
            if components.get('vwap_control', 0) > 40:
                comp_str.append("✅ Above VWAP")
            if comp_str:
                lines.append("  Behavior: " + " | ".join(comp_str))

        lines.append(f"  Gap: {c.get('gap_pct', 0):+.1f}% | Vol: {c.get('pm_volume', 0):,}")
        lines.append(f"  Data: {c.get('data_status', 'UNKNOWN')}")

        # Action suggestion
        if early_state in ["PRESSURE", "BREAKOUT_SETUP"] and early_score > 60:
            lines.append("  🟠 ACTION: WATCH PMH")
        elif early_state == "BREAKOUT" and early_score > 70:
            lines.append("  🟢 ACTION: PREPARE ENTRY")
        elif early_state in ["MOMENTUM", "EXTENSION"]:
            lines.append("  🟡 ACTION: MONITOR (already moving)")
        else:
            lines.append("  🔵 ACTION: WAIT")

        lines.append("")

    # Decision summary
    actionable = [c for c in top5 if c.get('early_state') in ['BREAKOUT_SETUP', 'BREAKOUT'] and c.get('early_score', 0) > 60]
    if actionable:
        lines.append("━━━━━━━━━━━━━━━━━━━━")
        lines.append("✅ BEST EARLY SETUP")
        best = actionable[0]
        lines.append(f"{best['ticker']} – {best.get('early_state', 'UNKNOWN')} ({best.get('early_score', 0):.0f}/100)")
        lines.append(f"Watch PMH break for entry.")
    else:
        lines.append("━━━━━━━━━━━━━━━━━━━━")
        lines.append("⏳ NO ACTIVE EARLY SETUPS")
        lines.append("No candidate is showing sufficient behavioral pressure.")

    lines.append("")
    lines.append("⏳ Next scan: 09:30 ET")
    lines.append("━━━━━━━━━━━━━━━━━━━━")
    lines.append("⚠️ MANUAL EXECUTION ONLY")
    return "\n".join(lines)
