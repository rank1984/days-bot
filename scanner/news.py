"""
News scoring module for DAYS-BOT
"""
import sys
import os
from pathlib import Path

# הוסף את ספריית הבסיס לנתיב
BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))

import re
from typing import List, Dict, Tuple, Optional

from config import *

# ── CATALYSTS ─────────────────────────────────────────────────
POSITIVE_CATALYSTS = [
    "fda", "approval", "approved", "contract", "acquisition",
    "acquires", "merger", "patent", "earnings", "revenue",
    "partnership", "grant", "award", "breakthrough", "positive",
    "phase", "trial", "clearance", "designation",
    "new", "launch", "product", "collaboration", "license",
    "agreement", "expansion", "order", "backlog", "win",
]

NEGATIVE_CATALYSTS = [
    "offering", "direct offering", "shelf", "registration",
    "dilution", "warrant", "priced offering", "atm",
    "bankruptcy", "investigation", "lawsuit", "fine",
    "restatement", "delay", "cancellation", "recall",
]

# ── CATALYST WEIGHTS ─────────────────────────────────────
CATALYST_WEIGHTS = {
    'fda': 10,
    'approval': 9,
    'approved': 9,
    'breakthrough': 8,
    'acquisition': 8,
    'acquires': 8,
    'merger': 8,
    'contract': 7,
    'partnership': 7,
    'earnings': 6,
    'revenue': 6,
    'product': 5,
    'launch': 5,
    'collaboration': 5,
    'license': 5,
    'agreement': 4,
    'expansion': 4,
    'order': 4,
    'backlog': 4,
    'win': 4,
    'grant': 3,
    'award': 3,
    'positive': 3,
    'clearance': 3,
    'trial': 3,
    'phase': 3,
    'designation': 3,
    'patent': 3,
}


def score_news(headlines: List[str]) -> Tuple[int, int, Optional[str]]:
    """
    Scores news headlines for positive and negative sentiment.
    
    Returns:
        Tuple of (positive_score, negative_score, best_catalyst)
    """
    if not headlines:
        return 0, 0, None
    
    text = " ".join(headlines).lower()
    positive_score = 0
    negative_score = 0
    best_catalyst = None
    best_weight = 0
    
    # Check positive catalysts
    for cat in POSITIVE_CATALYSTS:
        if cat in text:
            weight = CATALYST_WEIGHTS.get(cat, 1)
            if weight > best_weight:
                best_weight = weight
                best_catalyst = cat
            positive_score += weight
    
    # Check negative catalysts
    for neg in NEGATIVE_CATALYSTS:
        if neg in text:
            negative_score += 1
    
    # Normalize positive score to reasonable range
    positive_score = min(positive_score, 15)
    negative_score = min(negative_score, 5)
    
    return positive_score, negative_score, best_catalyst


def get_catalyst_label(headlines: List[str]) -> str:
    """
    Returns a short catalyst label for display.
    """
    if not headlines:
        return "—"
    
    _, _, catalyst = score_news(headlines)
    
    if catalyst:
        catalyst = catalyst.replace("direct offering", "offering")
        catalyst = catalyst.capitalize()
        return catalyst
    
    try:
        first = headlines[0]
        if len(first) > 50:
            first = first[:50] + "..."
        return first
    except:
        return "News"
