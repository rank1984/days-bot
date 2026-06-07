"""
news.py — שדרוג #2: News Catalyst Detection
--------------------------------------------
מ-Polygon News API:
✅ FDA, Contract, Acquisition, Earnings, Patent → ציון חיובי
❌ Offering, Dilution, Shelf → ציון שלילי (מסנן החוצה)
"""

import requests
from utils.config import POLYGON_API_KEY, POSITIVE_CATALYSTS, NEGATIVE_CATALYSTS

POLYGON_BASE = "https://api.polygon.io"


def fetch_news(ticker: str, limit: int = 5) -> list[dict]:
    """שולף חדשות אחרונות עבור מניה מ-Polygon."""
    try:
        url  = (
            f"{POLYGON_BASE}/v2/reference/news"
            f"?ticker={ticker}&limit={limit}&apiKey={POLYGON_API_KEY}"
        )
        resp = requests.get(url, timeout=5)
        if resp.status_code == 200:
            return resp.json().get("results", [])
    except Exception:
        pass
    return []


def score_news(ticker: str) -> tuple[int, str]:
    """
    מחשב news_score ומחזיר (score, headline).

    score > 0  → חדשות טובות
    score < 0  → offering/dilution → לסנן
    score = 0  → אין חדשות
    """
    articles = fetch_news(ticker)
    if not articles:
        return 0, "No news"

    best_score    = 0
    best_headline = "No catalyst"

    for article in articles:
        headline = article.get("title", "").lower()
        desc     = article.get("description", "").lower()
        text     = headline + " " + desc
        score    = 0

        # חדשות שליליות — offering/dilution
        for neg in NEGATIVE_CATALYSTS:
            if neg in text:
                score -= 40
                break

        # חדשות חיוביות — catalyst
        for pos in POSITIVE_CATALYSTS:
            if pos in text:
                if "fda" in text or "approval" in text:
                    score += 30
                elif "acquisition" in text or "merger" in text:
                    score += 25
                elif "contract" in text or "award" in text:
                    score += 20
                elif "earnings" in text or "revenue" in text:
                    score += 15
                else:
                    score += 10
                break

        if score > best_score:
            best_score    = score
            best_headline = article.get("title", "")[:60]

    return best_score, best_headline


def get_catalyst_label(news_score: int, headline: str) -> str:
    """ממיר ציון חדשות לתווית קריאה."""
    if news_score >= 30:
        return f"🔥 FDA/Approval"
    elif news_score >= 25:
        return f"🤝 M&A"
    elif news_score >= 20:
        return f"📄 Contract"
    elif news_score >= 15:
        return f"💰 Earnings"
    elif news_score >= 10:
        return f"📰 News"
    elif news_score < 0:
        return f"⚠️ Offering"
    return "—"
