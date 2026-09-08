"""
DAYS-BOT V5.0.2 – Scoring Engine (Fixed contracts)
"""
from utils.config import LEARNING_MODE


def _safe_float(value, default=0.0):
    try:
        if value is None:
            return default
        return float(value)
    except (TypeError, ValueError):
        return default


def _score_gap(gap):
    return min(max(_safe_float(gap, 0), 0) * 2, 30)


def _score_volume(volume):
    volume = _safe_float(volume, 0)
    return min((volume / 100_000) * 15, 25)


def _score_pm_distance(dist):
    # DISABLED – real PM data not confirmed
    return 0


def _score_rvol(rvol_data):
    """
    rvol_data should be a dict with 'rvol' and 'status'.
    If status == 'TIME_ADJUSTED', use the value.
    Otherwise, return 0 (informational).
    """
    if not isinstance(rvol_data, dict):
        return 0

    status = rvol_data.get('status', 'UNAVAILABLE')
    rvol = _safe_float(rvol_data.get('rvol'), 0)

    if status == 'TIME_ADJUSTED' and rvol > 0:
        if rvol >= 10:
            return 15
        elif rvol >= 5:
            return 10
        elif rvol >= 3:
            return 5
        else:
            return 2  # minimal score for having data

    return 0


def _score_float(float_val):
    float_val = _safe_float(float_val, 0)
    if float_val <= 0:
        return 0
    if float_val < 5_000_000:
        return 15
    elif float_val < 10_000_000:
        return 12
    elif float_val < 20_000_000:
        return 8
    elif float_val < 50_000_000:
        return 4
    return 0


def _score_short_interest(short):
    short = _safe_float(short, 0)
    if short >= 0.25:
        return 15
    elif short >= 0.15:
        return 10
    elif short >= 0.10:
        return 5
    return 0


def _score_catalyst(catalyst):
    if not isinstance(catalyst, dict):
        return 0
    cat_score = catalyst.get('score', 0)
    return min(cat_score * 2, 20)


def _score_sentiment(sentiment):
    if not isinstance(sentiment, dict):
        return 0
    sent_score = sentiment.get('sentiment_score', 0)
    if sent_score:
        return min((sent_score + 1) * 5, 10)
    return 0


def calculate_composite_score(candidate: dict, analysis: dict) -> float:
    score = 0.0

    # 1. Gap (0-30)
    score += _score_gap(candidate.get('gap_pct', 0))

    # 2. PM Volume (0-25)
    score += _score_volume(candidate.get('pm_volume', 0))

    # 3. PM Distance (disabled)
    score += _score_pm_distance(candidate.get('pm_dist_signed'))

    # 4. RVOL (0-15) – using analysis['rvol_data']
    rvol_data = analysis.get('rvol_data', {})
    score += _score_rvol(rvol_data)

    # 5. Float (0-15)
    float_val = analysis.get('float', candidate.get('float', 0))
    score += _score_float(float_val)

    # 6. Short Interest (0-15)
    short_interest = analysis.get('short_interest', candidate.get('short_interest', 0))
    score += _score_short_interest(short_interest)

    # 7. Catalyst (0-20)
    catalyst = analysis.get('catalyst', {})
    score += _score_catalyst(catalyst)

    # 8. Sentiment (0-10)
    sentiment = analysis.get('sentiment', {})
    score += _score_sentiment(sentiment)

    # ============================================================
    # PENALTIES (soft)
    # ============================================================

    # SEC Offering
    sec_risk = analysis.get('sec_risk', {})
    if isinstance(sec_risk, dict) and sec_risk.get('has_offering'):
        risk_level = sec_risk.get('risk_level', 'UNKNOWN')
        if risk_level == 'HIGH':
            score -= 30
        elif risk_level == 'MEDIUM':
            score -= 20
        elif risk_level == 'LOW':
            score -= 10
        elif risk_level == 'UNKNOWN':
            score -= 5  # unknown but has offering flag

    # Personality
    personality_data = analysis.get('personality', {})
    if isinstance(personality_data, dict):
        personality = personality_data.get('personality', 'NEUTRAL')
    else:
        personality = str(personality_data or 'NEUTRAL')

    if personality == "GAP_AND_CRAP":
        score -= 15 if LEARNING_MODE else 30

    return round(max(0, min(100, score)), 1)