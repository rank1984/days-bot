"""
Scoring module with new filters and catalyst detection
"""
from typing import Dict, List, Any
from utils.config import *
import re

def calculate_score(candidate: Dict[str, Any], news_score: int = 0, float_shares: int = 0) -> Dict[str, Any]:
    """
    Calculate comprehensive score for a candidate
    """
    score = 0
    breakdown = {}
    
    # 1. Gap (25 points)
    gap = candidate.get('gap_pct', 0)
    if 5 <= gap <= 25:
        gap_score = 25
    elif 3 <= gap < 5:
        gap_score = 20
    elif 25 < gap <= 40:
        gap_score = 15
    else:
        gap_score = 5
    breakdown['gap'] = gap_score
    score += gap_score
    
    # 2. Premarket Volume (25 points)
    vol = candidate.get('pm_volume', 0)
    if vol >= 1_000_000:
        vol_score = 25
    elif vol >= 500_000:
        vol_score = 20
    elif vol >= 200_000:
        vol_score = 15
    else:
        vol_score = 5
    breakdown['volume'] = vol_score
    score += vol_score
    
    # 3. Relative Volume (20 points) - if available
    rvol = candidate.get('relative_volume', 1.0)
    if rvol >= 5.0:
        rvol_score = 20
    elif rvol >= 3.0:
        rvol_score = 15
    elif rvol >= 2.0:
        rvol_score = 10
    else:
        rvol_score = 5
    breakdown['rvol'] = rvol_score
    score += rvol_score
    
    # 4. Dollar Volume (15 points)
    dvol = candidate.get('dollar_volume', 0)
    if dvol >= 5_000_000:
        dvol_score = 15
    elif dvol >= 1_000_000:
        dvol_score = 12
    elif dvol >= 500_000:
        dvol_score = 8
    else:
        dvol_score = 3
    breakdown['dollar_volume'] = dvol_score
    score += dvol_score
    
    # 5. Catalyst (10 points)
    cat_score = min(10, news_score)
    breakdown['catalyst'] = cat_score
    score += cat_score
    
    # 6. Float (5 points) - if available
    if float_shares > 0:
        if float_shares < 20_000_000:
            float_score = 5
        elif float_shares < 50_000_000:
            float_score = 3
        else:
            float_score = 1
    else:
        float_score = 3  # average if no data
    breakdown['float'] = float_score
    score += float_score
    
    # Normalize to 0-100
    score = min(100, score)
    
    # Quality grade
    if score >= 85:
        grade = "🚀 EXCELLENT"
    elif score >= 70:
        grade = "✅ GOOD"
    elif score >= 50:
        grade = "👀 WATCH"
    else:
        grade = "⛔ SKIP"
    
    return {
        'total': score,
        'grade': grade,
        'breakdown': breakdown,
    }


def get_news_score(headlines: List[str]) -> int:
    """
    Score news headlines for catalyst strength
    """
    if not headlines:
        return 0
    
    text = " ".join(headlines).lower()
    score = 0
    
    # Strong catalysts (10 points)
    strong = ["fda", "approval", "breakthrough", "acquisition", "merger"]
    for word in strong:
        if word in text:
            score += 10
            break
    
    # Medium catalysts (5 points)
    medium = ["contract", "partnership", "earnings", "revenue", "clearance"]
    for word in medium:
        if word in text:
            score += 5
            break
    
    # Weak catalysts (2 points)
    weak = ["positive", "trial", "designation", "grant", "award"]
    for word in weak:
        if word in text:
            score += 2
            break
    
    return min(10, score)
