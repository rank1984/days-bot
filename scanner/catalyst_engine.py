import os
import requests

def get_catalyst_score(symbol: str) -> dict:
    """
    Fetches news/catalyst data from Finnhub API for a given symbol.
    Provides explicit status tracking: CATALYST_OK, CATALYST_NOT_FOUND, 
    CATALYST_API_ERROR, CATALYST_DATA_UNAVAILABLE.
    """
    api_key = os.getenv("FINNHUB_API_KEY")

    if not api_key:
        print(f"[Catalyst ERROR] {symbol}: FINNHUB_API_KEY missing from environment variables")
        return {
            "score": 0.0,
            "headline": None,
            "status": "CATALYST_DATA_UNAVAILABLE",
            "error": "FINNHUB_API_KEY_MISSING",
        }

    try:
        url = f"https://finnhub.io/api/v1/company-news?symbol={symbol.upper()}&from=2026-08-01&to=2026-08-27&token={api_key}"
        
        response = requests.get(url, timeout=10)
        response.raise_for_status()
        news_items = response.json()

        if not isinstance(news_items, list) or len(news_items) == 0:
            print(f"[Catalyst INFO] {symbol}: No news found on Finnhub")
            return {
                "score": 0.0,
                "headline": None,
                "status": "CATALYST_NOT_FOUND",
                "error": None,
            }

        latest_news = news_items[0]
        headline = latest_news.get("headline", "")
        summary = latest_news.get("summary", "")

        score = 3.0  # Base passing score for existing news
        combined_text = (headline + " " + summary).lower()

        if any(k in combined_text for k in ["fda", "approval", "earnings", "contract", "merger", "acquisition", "buyout"]):
            score = 8.0
        elif any(k in combined_text for k in ["offering", "dilution", "lawsuit", "investigation"]):
            score = 1.0

        print(f"[Catalyst SUCCESS] {symbol} | Score: {score} | Status: CATALYST_OK")
        return {
            "score": score,
            "headline": headline,
            "status": "CATALYST_OK",
            "error": None,
        }

    except Exception as e:
        print(f"[Catalyst ERROR] {symbol}: {e}")
        return {
            "score": 0.0,
            "headline": None,
            "status": "CATALYST_API_ERROR",
            "error": str(e),
        }
