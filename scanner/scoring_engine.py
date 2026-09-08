"""
DAYS-BOT V5.0.3 – Scoring Engine

Intraday opportunity score.

Maximum base score = 100.

Weights:
    Gap          = 25
    PM Volume    = 20
    Early Move   = 20
    Float        = 15
    Short        = 10
    Catalyst     = 10

RVOL and Sentiment remain informational for now.
SEC offering risk is a soft penalty.
"""

from utils.config import LEARNING_MODE


def _safe_float(value, default=0.0):
    try:
        if value is None:
            return default

        value = float(value)

        return value

    except (TypeError, ValueError):
        return default


# ============================================================
# GAP — MAX 25
# ============================================================

def _score_gap(gap):
    """
    Positive gap only.

    3%   -> 7.5
    5%   -> 12.5
    10%  -> 25
    15%+ -> 25
    """

    gap = max(
        _safe_float(gap, 0),
        0
    )

    return min(
        gap * 2.5,
        25
    )


# ============================================================
# PM VOLUME — MAX 20
# ============================================================

def _score_volume(volume):
    """
    PM volume contribution.

    50K  -> 10
    100K -> 20
    200K+ -> 20
    """

    volume = max(
        _safe_float(volume, 0),
        0
    )

    return min(
        (volume / 100_000) * 20,
        20
    )


# ============================================================
# EARLY MOVE — MAX 20
# ============================================================

def _score_early(early_score):
    """
    Early Move Score:
        0–100

    Converted to:
        0–20 points
    """

    early = max(
        _safe_float(early_score, 0),
        0
    )

    return min(
        early * 0.20,
        20
    )


# ============================================================
# FLOAT — MAX 15
# ============================================================

def _score_float(float_val):

    float_val = _safe_float(
        float_val,
        0
    )

    if float_val <= 0:
        return 0

    if float_val < 5_000_000:
        return 15

    if float_val < 10_000_000:
        return 12

    if float_val < 20_000_000:
        return 9

    if float_val < 30_000_000:
        return 6

    if float_val < 50_000_000:
        return 3

    return 0


# ============================================================
# SHORT INTEREST — MAX 10
# ============================================================

def _score_short_interest(short):

    short = _safe_float(
        short,
        0
    )

    if short >= 0.25:
        return 10

    if short >= 0.15:
        return 7

    if short >= 0.10:
        return 4

    if short >= 0.05:
        return 2

    return 0


# ============================================================
# CATALYST — MAX 10
# ============================================================

def _score_catalyst(catalyst):

    if not isinstance(
        catalyst,
        dict
    ):
        return 0

    cat_score = _safe_float(
        catalyst.get("score"),
        0
    )

    # Existing catalyst scale appears
    # to be approximately 0–10.
    return min(
        max(cat_score, 0),
        10
    )


# ============================================================
# RVOL — INFORMATIONAL
# ============================================================

def _score_rvol(rvol_data):

    if not isinstance(
        rvol_data,
        dict
    ):
        return 0

    status = rvol_data.get(
        "status",
        "UNAVAILABLE"
    )

    rvol = _safe_float(
        rvol_data.get("rvol"),
        0
    )

    if (
        status != "TIME_ADJUSTED"
        or rvol <= 0
    ):
        return 0

    # Deliberately informational.
    # Does not consume the 100-point base score.
    return 0


# ============================================================
# SENTIMENT — INFORMATIONAL
# ============================================================

def _score_sentiment(sentiment):

    if not isinstance(
        sentiment,
        dict
    ):
        return 0

    return 0


# ============================================================
# COMPOSITE SCORE
# ============================================================

def calculate_composite_score(
    candidate: dict,
    analysis: dict
) -> float:

    if not isinstance(candidate, dict):
        return 0.0

    if not isinstance(analysis, dict):
        analysis = {}

    score = 0.0

    # --------------------------------------------------------
    # 1. GAP — 25
    # --------------------------------------------------------

    gap_points = _score_gap(
        candidate.get("gap_pct", 0)
    )

    score += gap_points

    # --------------------------------------------------------
    # 2. PM VOLUME — 20
    # --------------------------------------------------------

    volume_points = _score_volume(
        candidate.get("pm_volume", 0)
    )

    score += volume_points

    # --------------------------------------------------------
    # 3. EARLY MOVE — 20
    # --------------------------------------------------------

    early_score = candidate.get(
        "early_score",
        0
    )

    early_points = _score_early(
        early_score
    )

    score += early_points

    # --------------------------------------------------------
    # 4. FLOAT — 15
    # --------------------------------------------------------

    float_val = analysis.get(
        "float",
        candidate.get("float", 0)
    )

    float_points = _score_float(
        float_val
    )

    score += float_points

    # --------------------------------------------------------
    # 5. SHORT INTEREST — 10
    # --------------------------------------------------------

    short_interest = analysis.get(
        "short_interest",
        candidate.get(
            "short_interest",
            0
        )
    )

    short_points = _score_short_interest(
        short_interest
    )

    score += short_points

    # --------------------------------------------------------
    # 6. CATALYST — 10
    # --------------------------------------------------------

    catalyst = analysis.get(
        "catalyst",
        {}
    )

    catalyst_points = _score_catalyst(
        catalyst
    )

    score += catalyst_points

    # --------------------------------------------------------
    # SOFT RISK PENALTY
    # --------------------------------------------------------

    sec_risk = analysis.get(
        "sec_risk",
        {}
    )

    if isinstance(
        sec_risk,
        dict
    ):

        has_offering = bool(
            sec_risk.get(
                "has_offering",
                False
            )
        )

        if has_offering:

            risk_level = sec_risk.get(
                "risk_level",
                "UNKNOWN"
            )

            if risk_level == "HIGH":
                score -= 30

            elif risk_level == "MEDIUM":
                score -= 20

            elif risk_level == "LOW":
                score -= 10

            elif risk_level == "UNKNOWN":
                score -= 5

    # --------------------------------------------------------
    # PERSONALITY PENALTY
    # --------------------------------------------------------

    personality_data = analysis.get(
        "personality",
        {}
    )

    if isinstance(
        personality_data,
        dict
    ):
        personality = personality_data.get(
            "personality",
            "NEUTRAL"
        )
    else:
        personality = str(
            personality_data
            or "NEUTRAL"
        )

    if personality == "GAP_AND_CRAP":

        score -= (
            15
            if LEARNING_MODE
            else 30
        )

    # --------------------------------------------------------
    # FINAL
    # --------------------------------------------------------

    return round(
        max(
            0,
            min(
                100,
                score
            )
        ),
        1
    )