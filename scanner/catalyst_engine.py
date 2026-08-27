import os
import requests

def get_catalyst_score(symbol: str) -> dict:
    """
    Fetches news/catalyst data from Finnhub API for a given symbol and calculates a catalyst score.
    Includes explicit error diagnostics.
    """
    api_key = os.getenv("FINNHUB_API_KEY")

    if not api_key:
        print(f"[Catalyst ERROR] {symbol}: FINNHUB_API_KEY missing from environment variables")
        return {
            "score": 0,
            "headline": None,
            "type": "UNKNOWN",
            "error": "FINNHUB_API_KEY missing",
        }

    try:
        # Finnhub Company News Endpoint
        url = f"https://finnhub.io/api/v1/company-news?symbol={symbol.upper()}&from=2026-08-01&to=2026-08-27&token={api_key}"
        
        response = requests.get(url, timeout=10)
        response.raise_for_status()
        news_items = response.json()

        if not isinstance(news_items, list) or len(news_items) == 0:
            print(f"[Catalyst INFO] {symbol}: No news found on Finnhub")
            return {
                "score": 0,
                "headline": None,
                "type": "NONE",
                "error": None,
            }

        # Analysis of the latest news item
        latest_news = news_items[0]
        headline = latest_news.get("headline", "")
        summary = latest_news.get("summary", "")

        score = 5  # Base score if news exists
        news_type = "GENERAL_NEWS"

        combined_text = (headline + " " + summary).lower()
        if any(k in combined_text for k in ["fda", "approval", "earnings", "contract", "merger", "acquisition", "buyout"]):
            score = 8
            news_type = "HIGH_IMPACT"
        elif any(k in combined_text for k in ["offering", "dilution", "lawsuit", "investigation"]):
            score = 2
            news_type = "NEGATIVE"

        print(f"[Catalyst SUCCESS] {symbol} | Score: {score} | Type: {news_type}")
        return {
            "score": score,
            "headline": headline,
            "type": news_type,
            "error": None,
        }

    except Exception as e:
        print(f"[Catalyst ERROR] {symbol}: {e}")
        return {
            "score": 0,
            "headline": None,
            "type": "UNKNOWN",
            "error": str(e),
        }
