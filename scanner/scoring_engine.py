"""
DAYS-BOT V4.3 – Scoring Engine

Principles:
- Missing data = neutral/unknown, must NOT automatically destroy the candidate.
- Hard gates belong in Tradeability, not Discovery.
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


def _score_rvol(rvol):
    rvol = _safe_float(rvol, 0)
    if rvol >= 10:
        return 15
    elif rvol >= 5:
        return 10
    elif rvol >= 3:
        return 5
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

    score += _score_gap(candidate.get('gap_pct', 0))
    score += _score_volume(candidate.get('pm_volume', 0))
    score += _score_pm_distance(candidate.get('pm_dist_signed'))
    score += _score_rvol(analysis.get('rvol', 0))
    score += _score_float(analysis.get('float', 0))
    score += _score_short_interest(analysis.get('short_interest', 0))
    score += _score_catalyst(analysis.get('catalyst', {}))
    score += _score_sentiment(analysis.get('sentiment', {}))

    # Soft penalties (not destructive)
    sec_risk = analysis.get('sec_risk', {})
    if sec_risk.get('has_offering'):
        risk_level = sec_risk.get('risk_level', 'LOW')
        if risk_level == 'HIGH':
            score -= 30
        elif risk_level == 'MEDIUM':
            score -= 20
        else:
            score -= 10

    personality = analysis.get('personality', {}).get('personality', 'NEUTRAL')
    if personality == "GAP_AND_CRAP":
        score -= 15 if LEARNING_MODE else 30

    return round(max(0, min(100, score)), 1)