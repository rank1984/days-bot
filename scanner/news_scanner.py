import os
import requests
from typing import List, Dict, Any, Tuple, Optional  # <--- השורה הזו פותרת את השגיאה!

def classify_catalyst(headlines: list) -> Dict[str, Any]:
    """
    Returns catalyst type and score. Never rejects because of missing catalyst.
    """
    if not headlines or not isinstance(headlines, list):
        return {
            "type": "UNKNOWN",
            "score": 0,
            "headline": "",
            "quality": "LOW"
        }

    # Extract first non-empty headline
    valid_headlines = [str(h) for h in headlines if h]
    if not valid_headlines:
        return {
            "type": "UNKNOWN",
            "score": 0,
            "headline": "",
            "quality": "LOW"
        }

    text = " ".join(valid_headlines).lower()

    if "fda" in text or "approval" in text:
        return {"type": "FDA", "score": 10, "headline": valid_headlines[0], "quality": "HIGH"}
    if "acquisition" in text or "merger" in text:
        return {"type": "M&A", "score": 8, "headline": valid_headlines[0], "quality": "HIGH"}
    if "phase" in text and ("trial" in text or "clinical" in text):
        return {"type": "CLINICAL", "score": 7, "headline": valid_headlines[0], "quality": "HIGH"}
    if "bitcoin" in text or "crypto" in text:
        return {"type": "CRYPTO_TREASURY", "score": 7, "headline": valid_headlines[0], "quality": "HIGH"}
    if "earnings" in text or "revenue" in text or "eps" in text:
        return {"type": "EARNINGS", "score": 6, "headline": valid_headlines[0], "quality": "MEDIUM"}
    if "contract" in text or "agreement" in text:
        return {"type": "CONTRACT", "score": 5, "headline": valid_headlines[0], "quality": "MEDIUM"}
    if "pipe" in text or "atm" in text or "offering" in text:
        return {"type": "CAPITAL_STRUCTURE", "score": 2, "headline": valid_headlines[0], "quality": "LOW"}

    return {"type": "MOMENTUM_ONLY", "score": 1, "headline": valid_headlines[0], "quality": "LOW"}


def get_catalyst_news_score(symbol: str) -> Tuple[int, str]:
    """
    Optional Finnhub news fetcher for compatibility.
    Returns (score, primary_headline).
    """
    api_key = os.getenv("FINNHUB_API_KEY", "")
    if not api_key:
        return 0, "—"

    try:
        url = f"https://finnhub.io/api/v1/company-news?symbol={symbol}&token={api_key}"
        resp = requests.get(url, timeout=5)
        if resp.status_code == 200:
            data = resp.json()
            if data and isinstance(data, list) and len(data) > 0:
                headlines = [item.get("headline", "") for item in data[:5] if item.get("headline")]
                if headlines:
                    res = classify_catalyst(headlines)
                    return res["score"], res["headline"]
    except Exception as e:
        pass

    return 0, "—"
