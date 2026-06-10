"""
news.py — Finnhub News Catalyst
---------------------------------
סורק חדשות 24 שעות אחרונות לכל מניה.
מחזיר ציון + תווית קריאה לאדם.
"""

import requests
from datetime import datetime, timedelta
from utils.config import FINNHUB_API_KEY, POSITIVE_CATALYSTS, NEGATIVE_CATALYSTS


def fetch_news(ticker: str, hours: int = 24) -> list:
    """שולף חדשות מ-Finnhub עבור טווח שעות אחרון."""
    try:
        now   = datetime.utcnow()
        start = (now - timedelta(hours=hours)).strftime("%Y-%m-%d")
        end   = now.strftime("%Y-%m-%d")
        url   = "https://finnhub.io/api/v1/company-news"
        resp  = requests.get(
            url,
            params={
                "symbol": ticker,
                "from":   start,
                "to":     end,
                "token":  FINNHUB_API_KEY,
            },
            timeout=5,
        )
        if resp.status_code == 200:
            return resp.json()[:10]
    except Exception:
        pass
    return []


def score_news(ticker: str) -> tuple:
    """
    מחזיר (score, headline).
    score > 0  → חדשות חיוביות
    score < 0  → offering/dilution — לסנן
    score = 0  → אין חדשות
    """
    articles = fetch_news(ticker)
    if not articles:
        return 0, "No news"

    best_score    = 0
    best_headline = "No catalyst"

    for article in articles:
        headline = article.get("headline", "").lower()
        summary  = article.get("summary",  "").lower()
        text     = headline + " " + summary
        score    = 0

        # חדשות שליליות
        for neg in NEGATIVE_CATALYSTS:
            if neg in text:
                score -= 40
                break

        # חדשות חיוביות
        if score >= 0:
            if "fda" in text or "approval" in text or "approved" in text:
                score += 30
            elif "acquisition" in text or "merger" in text or "acquires" in text:
                score += 25
            elif "contract" in text or "award" in text or "grant" in text:
                score += 20
            elif "earnings" in text or "revenue" in text or "profit" in text:
                score += 15
            elif "patent" in text or "partnership" in text:
                score += 10
            elif any(p in text for p in POSITIVE_CATALYSTS):
                score += 5

        if score > best_score:
            best_score    = score
            best_headline = article.get("headline", "")[:80]

    return best_score, best_headline


def get_catalyst_label(news_score: int, headline: str) -> str:
    """ממיר ציון לתווית קריאה קצרה."""
    if news_score >= 30: return "🔥 FDA/Approval"
    if news_score >= 25: return "🤝 רכישה/מיזוג"
    if news_score >= 20: return "📄 חוזה/מענק"
    if news_score >= 15: return "💰 תוצאות רבעוניות"
    if news_score >= 10: return "📋 פטנט/שותפות"
    if news_score >= 5:  return "📰 חדשות חיוביות"
    if news_score < 0:   return "⚠️ הנפקה/דילול"
    return "—"
