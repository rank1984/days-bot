"""
Catalyst Engine – fetches and classifies news from Finnhub
"""
import requests
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional

# ── CATALYST KEYWORDS & SCORES ──────────────────────────
CATALYST_MAP = {
    'fda approval': 30,
    'fda approves': 30,
    'fda cleared': 25,
    'approval': 25,
    'breakthrough': 25,
    'acquisition': 20,
    'acquires': 20,
    'merger': 20,
    'contract': 18,
    'partnership': 16,
    'collaboration': 16,
    'earnings': 15,
    'revenue': 15,
    'eps': 15,
    'beat': 15,
    'grant': 12,
    'award': 12,
    'patent': 12,
    'positive': 12,
    'clearance': 12,
    'trial': 10,
    'phase': 10,
    'designation': 8,
    'agreement': 8,
    'expansion': 7,
    'order': 7,
    'backlog': 6,
    'win': 6,
}

NEGATIVE_MAP = {
    'offering': -20,
    'direct offering': -25,
    'atm': -25,
    'pipe': -20,
    'resale': -20,
    'warrant': -15,
    'dilution': -30,
    'shelf': -15,
    'follow-on': -20,
    'convertible': -15,
    'reverse split': -25,
    'going concern': -20,
    'nasdaq notice': -15,
}


def classify_catalyst(headlines: List[str]) -> Dict[str, Any]:
    """Classifies catalyst from news headlines."""
    if not headlines:
        return {'type': 'UNKNOWN', 'score': 0, 'headline': '', 'quality': 'NONE', 'is_negative': False, 'flags': []}

    text = ' '.join(headlines).lower()
    score = 0
    flags = []
    matched_type = 'UNKNOWN'
    matched_headline = headlines[0]

    for keyword, value in CATALYST_MAP.items():
        if keyword in text:
            score += value
            flags.append(keyword)
            matched_type = keyword.upper().replace(' ', '_')
            if score > 20:
                matched_headline = next((h for h in headlines if keyword in h.lower()), headlines[0])

    for keyword, value in NEGATIVE_MAP.items():
        if keyword in text:
            score += value
            flags.append(f'NEGATIVE:{keyword}')
            matched_type = 'NEGATIVE'

    if score >= 25:
        quality = 'HIGH'
    elif score >= 15:
        quality = 'MEDIUM'
    elif score >= 5:
        quality = 'LOW'
    else:
        quality = 'NONE'

    return {
        'type': matched_type,
        'score': min(100, max(-100, score)),
        'headline': matched_headline[:120],
        'quality': quality,
        'is_negative': score < 0,
        'flags': flags[:5],
    }


def get_catalyst_from_finnhub(symbol: str, finnhub_key: str) -> Dict[str, Any]:
    """
    Fetches news from Finnhub using the correct endpoint.
    Falls back to generic news if company-news fails.
    """
    if not finnhub_key:
        return {'type': 'UNKNOWN', 'score': 0, 'headline': '', 'quality': 'NONE', 'is_negative': False, 'flags': []}

    try:
        # Try company-news first (specific to symbol)
        end = datetime.now()
        start = end - timedelta(days=3)
        url = f"https://finnhub.io/api/v1/company-news"
        params = {
            'symbol': symbol,
            'from': start.strftime('%Y-%m-%d'),
            'to': end.strftime('%Y-%m-%d'),
            'token': finnhub_key
        }
        resp = requests.get(url, params=params, timeout=5)
        if resp.status_code == 200:
            data = resp.json()
            if data and len(data) > 0:
                headlines = [item.get('headline', '') for item in data[:5] if item.get('headline')]
                if headlines:
                    return classify_catalyst(headlines)

        # Fallback: generic news (if company-news returned empty)
        url2 = f"https://finnhub.io/api/v1/news"
        params2 = {
            'symbol': symbol,
            'token': finnhub_key
        }
        resp2 = requests.get(url2, params=params2, timeout=5)
        if resp2.status_code == 200:
            data2 = resp2.json()
            if data2 and len(data2) > 0:
                headlines2 = [item.get('headline', '') for item in data2[:5] if item.get('headline')]
                if headlines2:
                    return classify_catalyst(headlines2)

    except Exception as e:
        print(f"[CatalystEngine] Error for {symbol}: {e}")

    # If no news found, return UNKNOWN (not a blocker)
    return {'type': 'UNKNOWN', 'score': 0, 'headline': '', 'quality': 'NONE', 'is_negative': False, 'flags': []}
