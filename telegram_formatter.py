from typing import List, Dict, Any


def format_quant_report_v22(candidates: List[Dict[str, Any]], scan_time: str = "MAIN") -> str:
    """
    Formats the V2.3 Premarket Telegram Report including PRE-RUNNER metrics and summaries.
    """
    if not candidates:
        return f"🚨 **DAYS-BOT V2.3 SCAN [{scan_time}]**\n\nNo valid candidates identified."

    # State Counter Metrics
    prerunner_count = sum(1 for c in candidates if c.get('state') == 'PRE-RUNNER')
    early_count = sum(1 for c in candidates if c.get('state') == 'EARLY')
    extended_count = sum(1 for c in candidates if c.get('state') == 'EXTENDED')
    prepare_count = sum(1 for c in candidates if c.get('state') == 'PREPARE')
    watch_count = sum(1 for c in candidates if c.get('state') == 'WATCH')

    header = (
        f"⚡ **DAYS-BOT V2.3 QUANT REPORT [{scan_time}]**\n"
        f"📊 PRE-RUNNER: {prerunner_count} | EARLY: {early_count} | EXTENDED: {extended_count}\n"
        f"🎯 PREPARE: {prepare_count} | WATCH: {watch_count}\n"
        "────────────────────────────\n\n"
    )

    body_items = []
    for c in candidates:
        symbol = c.get('symbol', 'UNKNOWN')
        price = c.get('price', 0.0)
        gap_pct = c.get('gap_pct', 0.0)
        rvol = c.get('rvol', 0.0)
        event_score = c.get('event_score', 0)
        grade = c.get('grade', 'N/A')
        state = c.get('state', 'REJECT')

        prev_gain = c.get('prev_gain', 0.0)
        prev_rvol = c.get('prev_rvol', 0.0)
        float_shares = c.get('float_shares', None)
        vol_building = c.get('volume_building', False)

        float_fmt = f"{float_shares / 1_000_000:.1f}M" if float_shares else "N/A"
        continuation_indicator = "🟢 Building continuation" if vol_building else "⚪ Neutral flow"

        item = (
            f"📌 **{symbol}** (${price:.2f}) | **Score:** {event_score} ({grade})\n"
            f"📈 Prev Day: +{prev_gain:.1f}%\n"
            f"📊 Prev RVOL: {prev_rvol:.1f}x\n"
            f"⚡ Today Gap: {gap_pct:+.1f}%\n"
            f"📊 Today RVOL: {rvol:.1f}x\n"
            f"💰 Float: {float_fmt}\n"
            f"🏷️ State: **{state}**\n"
            f"{continuation_indicator}\n"
        )
        body_items.append(item)

    footer = "\n🤖 *DAYS-BOT V2.3 Engine - Automated Execution Freeze Active*"
    return header + "\n".join(body_items) + footer
