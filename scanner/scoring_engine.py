"""
DAYS-BOT V4.3 – Scoring Engine
"""
from utils.config import LEARNING_MODE


def _safe_float(value, default=0.0):
    try:
        if value is None:
            return default
        return float(value)
    except (TypeError, ValueError):
        return default


def _score_pm_distance(dist):
    """
    PM Distance score.
    DISABLED temporarily until real PM data is confirmed flowing.
    See issue: pm_high is currently fake (== price) in discovery.
    """
    # DISABLED: real PM data not yet confirmed
    # dist = _safe_float(dist, -100)
    # if dist >= -0.5:
    #     return 20
    # elif dist >= -2.0:
    #     return 12
    # elif dist >= -5.0:
    #     return 5
    # else:
    #     return 0
    return 0  # neutral until PM data is real


def calculate_composite_score(candidate: dict, analysis: dict) -> float:
    """
    Calculate a composite score (0-100) for ranking candidates.
    Missing data = neutral/unknown, not a penalty.
    Hard gates belong in Tradeability, not Discovery.
    """
    score = 0.0

    # 1. Gap (0-30)
    gap = candidate.get('gap_pct', 0)
    score += min(max(gap, 0) * 2, 30)

    # 2. PM Volume (0-25)
    pm_vol = candidate.get('pm_volume', 0)
    score += min((pm_vol / 100_000) * 15, 25)

    # 3. PM Distance (DISABLED – see above)
    pm_distance = candidate.get('pm_dist_signed', -100)
    score += _score_pm_distance(pm_distance)

    # 4. RVOL (0-15)
    rvol = analysis.get('rvol', 0)
    if rvol:
        if rvol >= 10:
            score += 15
        elif rvol >= 5:
            score += 10
        elif rvol >= 3:
            score += 5

    # 5. Float (0-15) – lower is better
    float_val = analysis.get('float', 0)
    if float_val:
        if float_val < 5_000_000:
            score += 15
        elif float_val < 10_000_000:
            score += 12
        elif float_val < 20_000_000:
            score += 8
        elif float_val < 50_000_000:
            score += 4

    # 6. Short Interest (0-15)
    short = analysis.get('short_interest', 0)
    if short:
        if short >= 0.25:
            score += 15
        elif short >= 0.15:
            score += 10
        elif short >= 0.10:
            score += 5

    # 7. Catalyst Quality (0-20)
    catalyst = analysis.get('catalyst', {})
    cat_score = catalyst.get('score', 0)
    score += cat_score * 2

    # 8. Sentiment (0-10)
    sentiment = analysis.get('sentiment', {}).get('sentiment_score', 0)
    if sentiment:
        score += (sentiment + 1) * 5

    # ============================================================
    # PENALTIES (soft, not hard gates)
    # ============================================================

    # SEC Offering
    if analysis.get('sec_risk', {}).get('has_offering'):
        risk_level = analysis['sec_risk'].get('risk_level', 'LOW')
        if risk_level == 'HIGH':
            score -= 30
        elif risk_level == 'MEDIUM':
            score -= 20
        else:
            score -= 10

    # Personality GAP_AND_CRAP
    personality = analysis.get('personality', {}).get('personality', 'NEUTRAL')
    if personality == "GAP_AND_CRAP":
        if LEARNING_MODE:
            score -= 30
        else:
            score -= 50  # strong penalty, not hard reject

    # Float > 50M
    if float_val and float_val > 50_000_000:
        if LEARNING_MODE:
            score -= 25
        else:
            score -= 20

    # Gap < 10%
    if gap < 10:
        if LEARNING_MODE:
            score -= 20
        else:
            score -= 15

    # RVOL < 3
    if rvol and rvol < 3:
        if LEARNING_MODE:
            score -= 20
        else:
            score -= 10

    # Short Interest < 5% (no squeeze potential)
    if short and short < 0.05:
        if LEARNING_MODE:
            score -= 10
        else:
            score -= 5

    # Normalize
    return round(max(0, min(100, score)), 1)
