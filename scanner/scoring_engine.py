"""
DAYS-BOT V4.1 – Deterministic Scoring Engine

Important:
This is ranking logic, NOT an automatic trading engine.

Missing data = neutral / unknown.
It must NOT automatically destroy the candidate.
"""

from utils.config import LEARNING_MODE


def _safe_float(value, default=0.0):
    try:
        if value is None:
            return default
        return float(value)
    except Exception:
        return default


def _score_gap(gap):
    gap = _safe_float(gap)

    if gap >= 20:
        return 30
    if gap >= 15:
        return 27
    if gap >= 10:
        return 23
    if gap >= 7:
        return 18
    if gap >= 5:
        return 13
    if gap >= 3:
        return 8
    if gap > 0:
        return 4

    return 0


def _score_volume(volume):
    volume = _safe_float(volume)

    if volume >= 2_000_000:
        return 25
    if volume >= 1_000_000:
        return 22
    if volume >= 500_000:
        return 18
    if volume >= 250_000:
        return 14
    if volume >= 100_000:
        return 9
    if volume >= 50_000:
        return 5

    return 0


def _score_pm_distance(dist):
    dist = _safe_float(dist, -100)

    if dist >= -0.5:
        return 20
    if dist >= -1:
        return 17
    if dist >= -2:
        return 14
    if dist >= -3:
        return 9
    if dist >= -5:
        return 5

    return 0


def _score_rvol(rvol):
    rvol = _safe_float(rvol)

    if rvol >= 5:
        return 15
    if rvol >= 3:
        return 13
    if rvol >= 2:
        return 10
    if rvol >= 1.5:
        return 7
    if rvol >= 1:
        return 4

    # Unknown / unavailable
    if rvol == 0:
        return 0

    return 0


def _score_float(float_val):
    float_val = _safe_float(float_val)

    if float_val <= 0:
        return 0

    if float_val < 5_000_000:
        return 15

    if float_val < 10_000_000:
        return 13

    if float_val < 20_000_000:
        return 11

    if float_val < 50_000_000:
        return 7

    if float_val < 100_000_000:
        return 3

    return 0


def _score_short(short):
    short = _safe_float(short)

    # Support both decimal and percentage formats.
    if short > 1:
        short = short / 100.0

    if short >= 0.25:
        return 15

    if short >= 0.15:
        return 11

    if short >= 0.10:
        return 8

    if short >= 0.05:
        return 5

    if short > 0:
        return 2

    return 0


def _score_catalyst(catalyst):
    if not isinstance(catalyst, dict):
        return 0

    score = _safe_float(
        catalyst.get("score"),
        0,
    )

    # Support analyzers returning 0-10 or 0-100.
    if score > 10:
        score = score / 10.0

    return max(
        0,
        min(20, score * 2),
    )


def _score_sentiment(sentiment):
    if not isinstance(sentiment, dict):
        return 0

    value = _safe_float(
        sentiment.get(
            "sentiment_score",
            0,
        )
    )

    # Expected -1 to +1.
    if -1 <= value <= 1:
        return max(
            0,
            min(10, (value + 1) * 5),
        )

    # If analyzer returns 0-100.
    if 0 <= value <= 100:
        return max(
            0,
            min(10, value / 10),
        )

    return 0


def calculate_composite_score(
    candidate: dict,
    analysis: dict,
) -> float:

    # ========================================================
    # POSITIVE SCORE
    # ========================================================

    score = 0.0

    gap = _safe_float(
        candidate.get("gap_pct")
    )

    pm_volume = _safe_float(
        candidate.get("pm_volume")
    )

    pm_distance = _safe_float(
        candidate.get(
            "pm_dist_signed",
            -100,
        )
    )

    rvol = _safe_float(
        analysis.get("rvol")
    )

    float_val = _safe_float(
        analysis.get("float")
    )

    short = _safe_float(
        analysis.get("short_interest")
    )

    score += _score_gap(gap)
    score += _score_volume(pm_volume)
    score += _score_pm_distance(pm_distance)
    score += _score_rvol(rvol)
    score += _score_float(float_val)
    score += _score_short(short)

    score += _score_catalyst(
        analysis.get("catalyst")
    )

    score += _score_sentiment(
        analysis.get("sentiment")
    )

    # ========================================================
    # RISK ADJUSTMENTS
    # ========================================================

    sec_risk = analysis.get(
        "sec_risk",
        {},
    )

    if isinstance(sec_risk, dict):
        if sec_risk.get("has_offering"):
            risk_level = str(
                sec_risk.get(
                    "risk_level",
                    "LOW",
                )
            ).upper()

            if risk_level == "HIGH":
                score -= 25
            elif risk_level == "MEDIUM":
                score -= 15
            else:
                score -= 7

    personality = analysis.get(
        "personality",
        {},
    )

    if isinstance(personality, dict):
        personality_name = str(
            personality.get(
                "personality",
                "NEUTRAL",
            )
        ).upper()

        if personality_name == "GAP_AND_CRAP":
            score -= 25

    # Large float is a disadvantage, but NOT an automatic rejection.
    if float_val > 100_000_000:
        score -= 10
    elif float_val > 50_000_000:
        score -= 5

    # Weak spread.
    spread = _safe_float(
        candidate.get(
            "spread_pct"
        )
    )

    if spread > 3:
        score -= 20
    elif spread > 2:
        score -= 10
    elif spread > 1:
        score -= 3

    # ========================================================
    # RESEARCH MODE PRINCIPLE
    # ========================================================
    #
    # Do NOT impose:
    # gap >= 10
    # RVOL >= 3
    # float <= 20M
    #
    # as destructive hard penalties.
    #
    # Those variables are still visible in the score.
    # Hard gates belong in Tradeability, not Discovery.
    # ========================================================

    return round(
        max(0, min(100, score)),
        1,
    )
