"""
AI Small-Cap Quant Engine

מחשב Score עצמאי על בסיס נתוני Live.
DAYS-BOT score משמש כ-feature בלבד.
"""

from typing import Dict, Any


def clamp(value: float, minimum=0.0, maximum=100.0):
    return max(minimum, min(maximum, value))


def calculate_opportunity(candidate: Dict[str, Any]) -> float:

    score = 0.0

    gap = candidate.get("live_gap_pct", 0.0)
    rvol = candidate.get("rvol", 0.0)
    price = candidate.get("live_price", 0.0)
    pm_high = candidate.get("pm_high", price)

    # Positive gap
    if gap >= 10:
        score += 25
    elif gap >= 7:
        score += 20
    elif gap >= 5:
        score += 15
    elif gap >= 3:
        score += 10
    elif gap >= 1:
        score += 5

    # RVOL
    if rvol >= 5:
        score += 25
    elif rvol >= 3:
        score += 20
    elif rvol >= 2:
        score += 15
    elif rvol >= 1.5:
        score += 10
    elif rvol >= 1:
        score += 5

    # Distance from PM high
    if pm_high > 0:

        distance = (
            (pm_high - price)
            / pm_high
        ) * 100

        if distance <= 1:
            score += 25
        elif distance <= 2:
            score += 20
        elif distance <= 4:
            score += 12
        elif distance <= 6:
            score += 5

    # DAYS-BOT is only a weak feature
    days_score = candidate.get(
        "days_score",
        0
    )

    if days_score >= 90:
        score += 5
    elif days_score >= 80:
        score += 4
    elif days_score >= 70:
        score += 3

    return clamp(score)


def calculate_risk(candidate: Dict[str, Any]) -> float:

    risk = 0.0

    spread = candidate.get(
        "spread_pct"
    )

    gap = candidate.get(
        "live_gap_pct",
        0
    )

    rvol = candidate.get(
        "rvol",
        0
    )

    # Spread risk
    if spread is None:
        risk += 15
    elif spread > 2:
        risk += 40
    elif spread > 1:
        risk += 25
    elif spread > 0.5:
        risk += 15
    elif spread > 0.25:
        risk += 8

    # Excessive gap = exhaustion risk
    if gap > 15:
        risk += 25
    elif gap > 10:
        risk += 15
    elif gap > 7:
        risk += 8

    # Low participation
    if rvol < 1:
        risk += 25
    elif rvol < 1.5:
        risk += 15

    return clamp(risk)


def tradeability(candidate: Dict[str, Any]) -> str:

    spread = candidate.get(
        "spread_pct"
    )

    dollar_volume = candidate.get(
        "dollar_volume",
        0
    )

    if spread is not None and spread > 2:
        return "FAIL"

    if dollar_volume < 100_000:
        return "FAIL"

    return "PASS"


def calculate_final_score(
    opportunity: float,
    risk: float,
    tradeable: str
) -> float:

    if tradeable == "FAIL":
        return 0.0

    score = (
        opportunity * 0.75
        +
        (100 - risk) * 0.25
    )

    return round(
        clamp(score),
        1
    )


def analyze_candidate(
    candidate: Dict[str, Any]
) -> Dict[str, Any]:

    opportunity = calculate_opportunity(
        candidate
    )

    risk = calculate_risk(
        candidate
    )

    tradeable = tradeability(
        candidate
    )

    final_score = calculate_final_score(
        opportunity,
        risk,
        tradeable
    )

    result = dict(candidate)

    result.update({
        "opportunity_score": round(
            opportunity,
            1
        ),
        "risk_score": round(
            risk,
            1
        ),
        "tradeability": tradeable,
        "final_score": final_score,
    })

    return result


def rank_candidates(
    candidates
):

    analyzed = [
        analyze_candidate(c)
        for c in candidates
    ]

    analyzed.sort(
        key=lambda x: x.get(
            "final_score",
            0
        ),
        reverse=True
    )

    return analyzed
