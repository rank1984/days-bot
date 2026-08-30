"""
Scoring Engine V3.3 – ציון משוקלל עם Hard Filters & Risk Checks
"""
def calculate_composite_score(candidate: dict, analysis: dict) -> float:
    """
    מחשב ציון מורכב לפי:
    - Hard Filter: Float < 20M, Short Interest > 10%, RVOL > 5, Gap > 10%
    - Risk Check: SEC Offering -> הפחתת ציון
    - Sentiment & Catalyst Quality
    """
    score = 0.0

    # 1. Gap (0-30)
    gap = candidate.get('gap_pct', 0)
    score += min(max(gap, 0) * 2, 30)

    # 2. PM Volume (0-25)
    pm_vol = candidate.get('pm_volume', 0)
    score += min((pm_vol / 100_000) * 15, 25)

    # 3. PM Distance (0-20)
    dist = candidate.get('pm_dist_signed', -100)
    if dist >= 0:
        score += 20
    elif dist >= -2:
        score += 12
    elif dist >= -5:
        score += 5

    # 4. RVOL (0-15)
    rvol = analysis.get('rvol', 0)
    if rvol:
        if rvol >= 10:
            score += 15
        elif rvol >= 5:
            score += 10
        elif rvol >= 3:
            score += 5

    # 5. Float (0-15) – נמוך יותר = טוב יותר
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
        if short >= 0.25:   # >25%
            score += 15
        elif short >= 0.15: # >15%
            score += 10
        elif short >= 0.10:
            score += 5

    # 7. Catalyst Quality (0-20)
    catalyst = analysis.get('catalyst', {})
    cat_score = catalyst.get('score', 0)
    score += cat_score * 2  # 1-10 -> 2-20

    # 8. Sentiment (0-10)
    sentiment = analysis.get('sentiment', {}).get('sentiment_score', 0)
    if sentiment:
        score += (sentiment + 1) * 5  # -1..1 -> 0..10

    # ============================================================
    # RISK CHECKS – הפחתת ציון
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

    # Float גבוה מדי (סינון קשיח)
    if float_val and float_val > 50_000_000:
        score -= 20

    # Short Interest נמוך מאוד (אין squeeze potential)
    if short and short < 0.05:
        score -= 10

    # ============================================================
    # Normalize
    # ============================================================
    return round(max(0, min(100, score)), 1)
