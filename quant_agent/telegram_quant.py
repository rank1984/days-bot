"""
Telegram formatter for AI Quant Agent V1
"""

from typing import List, Dict, Any


def _money(value):
    if not value:
        return "—"
    return f"${value:.2f}"


def format_quant_report(
    results: List[Dict[str, Any]],
    source_count: int
) -> str:

    passed = [
        r for r in results
        if r.get("filter_passed")
    ]

    rejected = [
        r for r in results
        if not r.get("filter_passed")
    ]

    tradable = [
        r for r in results
        if r.get("tradeability") == "PASS"
    ]

    top = tradable[:3]

    lines = []

    lines.append("🔥 AI SMALL-CAP QUANT")
    lines.append("━━━━━━━━━━━━━━━━━━")
    lines.append(f"📊 Input: {source_count} candidates")
    lines.append(f"✅ Passed filters: {len(passed)}")
    lines.append(f"❌ Rejected: {len(rejected)}")
    lines.append(f"🎯 Tradeable: {len(tradable)}")
    lines.append("━━━━━━━━━━━━━━━━━━")

    if not top:
        lines.append("🚫 NO TRADE")
        lines.append("No candidate currently meets the execution filters.")
        lines.append("━━━━━━━━━━━━━━━━━━")

    medals = ["🥇", "🥈", "🥉"]

    for index, r in enumerate(top):

        medal = medals[index]

        lines.append(
            f"{medal} {r['ticker']} — "
            f"{r['final_score']:.0f}/100"
        )

        lines.append(
            f"State: {r['state']}"
        )

        lines.append(
            f"Opportunity: {r['opportunity']:.0f} | "
            f"Risk: {r['risk']:.0f} | "
            f"Tradeability: {r['tradeability']}"
        )

        lines.append("")

        lines.append(
            f"Gap: {r['gap_pct']:+.1f}%"
        )

        lines.append(
            f"Price: {_money(r['price'])}"
        )

        lines.append(
            f"RVOL: {r['rvol']:.2f}x"
        )

        if r["dollar_volume"] > 0:
            lines.append(
                f"DVol: ${r['dollar_volume']:,.0f}"
            )

        if r["float"] > 0:
            lines.append(
                f"Float: {r['float']:,.0f}"
            )

        if r["pm_high"] > 0:
            lines.append(
                f"PMH: {_money(r['pm_high'])}"
            )

        if r["vwap"] > 0:
            lines.append(
                f"VWAP: {_money(r['vwap'])}"
            )

        lines.append(
            f"📰 {r['catalyst']}"
        )

        lines.append(
            f"DAYS-BOT: {r['days_score']:.0f} "
            f"| {r['days_status']}"
        )

        lines.append("━━━━━━━━━━━━━━━━━━")

    if rejected:

        lines.append("🚫 REJECTED")

        for r in rejected[:5]:

            reasons = r.get(
                "filter_reasons",
                []
            )

            reason_text = ", ".join(reasons)

            if not reason_text:
                reason_text = "quant filter"

            lines.append(
                f"• {r['ticker']} — {reason_text}"
            )

        lines.append("━━━━━━━━━━━━━━━━━━")

    if top:

        best = top[0]

        lines.append(
            f"🤖 QUANT LEADER: {best['ticker']}"
        )

        lines.append(
            "Best combination of momentum, "
            "liquidity, risk and execution quality."
        )

    lines.append("")
    lines.append("⚠️ Analysis only — not investment advice")

    return "\n".join(lines)
