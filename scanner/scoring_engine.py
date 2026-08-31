"""
V3.5 Scoring Engine – Computes Discovery, Analysis, Trade Scores with Rejection Reasons
"""
from utils.config import LEARNING_MODE

def calculate_scores(candidate: dict, analysis: dict) -> dict:
    """
    Returns: {
        discovery_score: float,
        analysis_score: float,
        trade_score: float,
        rejection_reason: str or None,
        is_trade_candidate: bool
    }
    """
    result = {
        "discovery_score": candidate.get('discovery_score', 0),
        "analysis_score": 0,
        "trade_score": 0,
        "rejection_reason": None,
        "is_trade_candidate": False,
    }

    # Analysis Score (based on all metrics)
    score = 0
    float_val = analysis.get('float', 0)
    short = analysis.get('short_interest', 0)
    rvol = analysis.get('rvol', 0)
    catalyst = analysis.get('catalyst', {}).get('score', 0)
    sentiment = analysis.get('sentiment', {}).get('sentiment_score', 0)
    personality = analysis.get('personality', {}).get('personality', 'NEUTRAL')
    sec_risk = analysis.get('sec_risk', {}).get('risk_level', 'LOW')

    # Float
    if float_val and float_val < 5_000_000:
        score += 15
    elif float_val and float_val < 10_000_000:
        score += 10
    elif float_val and float_val < 20_000_000:
        score += 5
    elif float_val and float_val > 50_000_000:
        score -= 10

    # Short Interest
    if short and short > 0.25:
        score += 15
    elif short and short > 0.15:
        score += 10

    # RVOL
    if rvol and rvol > 5:
        score += 15
    elif rvol and rvol > 3:
        score += 8
    elif rvol and rvol < 2:
        score -= 5

    # Catalyst
    score += catalyst * 2

    # Sentiment
    if sentiment:
        score += sentiment * 5

    # Personality
    if personality == "STRONG_FOLLOWER":
        score += 10
    elif personality == "GAP_AND_CRAP":
        score -= 20

    # SEC Risk
    if sec_risk == "HIGH":
        score -= 30
    elif sec_risk == "MEDIUM":
        score -= 15

    result["analysis_score"] = round(max(0, min(100, score)), 1)

    # Trade Score = weighted combination
    trade_score = (result["discovery_score"] * 0.4) + (result["analysis_score"] * 0.6)
    result["trade_score"] = round(trade_score, 1)

    # Determine if trade candidate
    rejection_reasons = []

    # Hard checks
    if float_val and float_val > 50_000_000:
        rejection_reasons.append("Float > 50M")
    if candidate.get('gap_pct', 0) < 10:
        rejection_reasons.append("Gap < 10%")
    if rvol and rvol < 3:
        rejection_reasons.append("RVOL < 3x")
    if sec_risk == "HIGH":
        rejection_reasons.append("SEC HIGH risk")
    if personality == "GAP_AND_CRAP":
        rejection_reasons.append("Personality = GAP_AND_CRAP")

    if rejection_reasons and not LEARNING_MODE:
        result["rejection_reason"] = " | ".join(rejection_reasons)
        result["is_trade_candidate"] = False
    else:
        result["is_trade_candidate"] = True
        result["rejection_reason"] = None

    return result
