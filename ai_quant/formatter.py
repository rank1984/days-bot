"""
AI Quant Agent V1 - Telegram/Text Formatter
"""

from typing import Dict, Any


def fmt(value, decimals=2):

    try:
        return f"{float(value):.{decimals}f}"
    except Exception:
        return "—"


def format_candidate(
    candidate: Dict[str, Any],
    rank: int
) -> str:

    ticker = candidate["ticker"]

    score = candidate.get(
        "final_score",
        0
    )

    opportunity = candidate.get(
        "opportunity_score",
        0
    )

    risk = candidate.get(
        "risk_score",
        0
    )

    tradeability = candidate.get(
        "tradeability_score",
        0
    )

    price = candidate.get(
        "live_price",
        candidate.get("price", 0)
    )

    state = determine_state(candidate)

    return f"""
🥇 #{rank} {ticker} — {fmt(score)}/100

State: {state}

Opportunity: {fmt(opportunity)}
Risk: {fmt(risk)}
Tradeability: {fmt(tradeability)}

Price: ${fmt(price)}
Gap: +{fmt(candidate.get('gap_pct', 0))}%
RVOL: {fmt(candidate.get('rvol', 0))}x

PMH: ${fmt(candidate.get('pm_high', 0))}
VWAP: ${fmt(candidate.get('vwap', 0))}

Spread: {fmt(candidate.get('spread_pct', 0))}%
$ Volume: ${fmt(candidate.get('dollar_volume', 0), 0)}

DAYS Score: {fmt(candidate.get('days_score', 0))}
DAYS Status: {candidate.get('days_status', '—')}
Hits: {candidate.get('hits', 0)}
"""


def determine_state(
    candidate: Dict[str, Any]
) -> str:

    if not candidate.get("filter_pass"):
        return "INVALIDATED"

    price = candidate.get(
        "live_price",
        0
    )

    pm_high = candidate.get(
        "pm_high",
        0
    )

    rvol = candidate.get(
        "rvol",
        0
    )

    vwap = candidate.get(
        "vwap",
        0
    )

    if (
        price >= pm_high
        and rvol >= 1.5
    ):
        return "READY"

    if (
        pm_high > 0
        and price >= pm_high * 0.97
        and price >= vwap
    ):
        return "BREAKOUT_PENDING"

    return "PREPARE"


def format_report(
    result: Dict[str, Any]
) -> str:

    lines = []

    lines.append(
        "🔥 AI SMALL-CAP QUANT V1"
    )

    lines.append(
        "━━━━━━━━━━━━━━━━━━"
    )

    lines.append(
        f"📊 Candidates: {result.get('total', 0)}"
    )

    lines.append(
        f"✅ Passed: {len(result.get('passed', []))}"
    )

    lines.append(
        f"❌ Rejected: {len(result.get('rejected', []))}"
    )

    lines.append(
        "━━━━━━━━━━━━━━━━━━"
    )

    for index, candidate in enumerate(
        result.get("top", []),
        start=1
    ):

        lines.append(
            format_candidate(
                candidate,
                index
            )
        )

        lines.append(
            "━━━━━━━━━━━━━━━━━━"
        )

    if result.get("rejected"):

        lines.append(
            "🚫 REJECTED"
        )

        for candidate in result["rejected"]:

            lines.append(
                f"• {candidate['ticker']} — "
                f"{candidate.get('rejection_reason', 'UNKNOWN')}"
            )

    return "\n".join(lines)
