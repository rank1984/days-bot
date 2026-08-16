"""
AI Quant Agent V1 - Independent Quant Scoring

DAYS-BOT score אינו משמש כ-Final Score.
"""

from typing import Dict, Any


def clamp(value: float, minimum=0.0, maximum=100.0):
    return max(minimum, min(maximum, value))


def score_rvol(rvol: float) -> float:

    if rvol >= 5.0:
        return 100

    if rvol >= 3.0:
        return 85

    if rvol >= 2.0:
        return 70

    if rvol >= 1.5:
        return 55

    if rvol >= 1.0:
        return 40

    return 20


def score_gap(gap: float) -> float:

    if 3 <= gap <= 10:
        return 100

    if 2 <= gap < 3:
        return 75

    if 10 < gap <= 15:
        return 70

    if 1 <= gap < 2:
        return 50

    if 15 < gap <= 20:
        return 40

    return 20


def score_pmh(distance: float) -> float:

    if distance <= 0.5:
        return 100

    if distance <= 1.0:
        return 90

    if distance <= 2.0:
        return 75

    if distance <= 4.0:
        return 55

    if distance <= 7.0:
        return 30

    return 10


def score_vwap(candidate: Dict[str, Any]) -> float:

    price = candidate.get("live_price", 0)
    vwap = candidate.get("vwap", 0)

    if price <= 0 or vwap <= 0:
        return 30

    distance_pct = ((price - vwap) / vwap) * 100

    if distance_pct >= 2:
        return 100

    if distance_pct >= 1:
        return 85

    if distance_pct >= 0:
        return 70

    if distance_pct >= -1:
        return 40

    return 15


def score_liquidity(candidate: Dict[str, Any]) -> float:

    dvol = candidate.get(
        "dollar_volume",
        0
    )

    spread = candidate.get(
        "spread_pct",
        0
    )

    # Dollar volume
    if dvol >= 5_000_000:
        base = 100
    elif dvol >= 2_000_000:
        base = 85
    elif dvol >= 1_000_000:
        base = 70
    elif dvol >= 500_000:
        base = 55
    elif dvol >= 100_000:
        base = 40
    else:
        base = 20

    # Spread penalty
    spread_penalty = min(
        40,
        spread * 15
    )

    return clamp(base - spread_penalty)


def score_catalyst(candidate: Dict[str, Any]) -> float:

    text = str(
        candidate.get("news") or ""
    ).lower()

    positive = [
        "fda",
        "approval",
        "contract",
        "agreement",
        "acquisition",
        "merger",
        "earnings",
        "revenue",
        "partnership",
        "breakthrough",
        "grant",
    ]

    strong = [
        "fda",
        "approval",
        "acquisition",
        "merger",
        "major contract",
    ]

    for word in strong:
        if word in text:
            return 100

    for word in positive:
        if word in text:
            return 75

    return 40


def calculate_scores(
    candidate: Dict[str, Any]
) -> Dict[str, Any]:

    if not candidate.get("filter_pass"):
        candidate["opportunity_score"] = 0
        candidate["risk_score"] = 100
        candidate["tradeability_score"] = 0
        candidate["final_score"] = 0
        return candidate

    rvol_score = score_rvol(
        candidate.get("rvol", 1)
    )

    gap_score = score_gap(
        candidate.get("gap_pct", 0)
    )

    pmh_score = score_pmh(
        candidate.get(
            "distance_to_high_pct",
            100
        )
    )

    vwap_score = score_vwap(candidate)

    liquidity_score = score_liquidity(
        candidate
    )

    catalyst_score = score_catalyst(
        candidate
    )

    opportunity = (
        rvol_score * 0.20 +
        gap_score * 0.15 +
        pmh_score * 0.20 +
        vwap_score * 0.15 +
        liquidity_score * 0.20 +
        catalyst_score * 0.10
    )

    opportunity = clamp(opportunity)

    # Risk
    spread = candidate.get(
        "spread_pct",
        0
    )

    risk = 10

    if spread > 1.0:
        risk += 25
    elif spread > 0.5:
        risk += 10

    if candidate.get("gap_pct", 0) > 15:
        risk += 20

    if candidate.get("rvol", 1) < 1.5:
        risk += 20

    risk = clamp(risk, 0, 100)

    # Tradeability
    tradeability = (
        liquidity_score * 0.65 +
        (100 - min(spread * 40, 100)) * 0.35
    )

    tradeability = clamp(tradeability)

    # Final
    risk_factor = 1 - (risk / 200)

    tradeability_factor = (
        0.5 + tradeability / 200
    )

    final = (
        opportunity *
        risk_factor *
        tradeability_factor
    )

    candidate["rvol_score"] = round(rvol_score, 2)
    candidate["gap_score"] = round(gap_score, 2)
    candidate["pmh_score"] = round(pmh_score, 2)
    candidate["vwap_score"] = round(vwap_score, 2)
    candidate["liquidity_score"] = round(
        liquidity_score,
        2
    )
    candidate["catalyst_score"] = round(
        catalyst_score,
        2
    )

    candidate["opportunity_score"] = round(
        opportunity,
        2
    )

    candidate["risk_score"] = round(
        risk,
        2
    )

    candidate["tradeability_score"] = round(
        tradeability,
        2
    )

    candidate["final_score"] = round(
        final,
        2
    )

    return candidate
