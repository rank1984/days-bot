"""
News scoring module for DAYS-BOT – Real Finnhub Integration & Logging
"""
import sys
import os
import requests
from datetime import datetime, timedelta
from pathlib import Path
from typing import List, Dict, Tuple, Optional

BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))
sys.path.insert(0, str(BASE_DIR / "utils"))

from utils.config import FINNHUB_API_KEY, POSITIVE_CATALYSTS, NEGATIVE_CATALYSTS


def classify_catalyst(headlines: List[str]) -> Dict[str, Any]:
    """סיווג סוג הקטליזטור מתוך כותרות החדשות"""
    if not headlines:
        return {"type": "UNKNOWN", "score": 0, "headline": "", "quality": "LOW"}

    text = " ".join(headlines).lower()
    headline = headlines[0] if headlines else ""

    if "fda" in text or "approval" in text:
        return {"type": "FDA", "score": 10, "headline": headline, "quality": "HIGH"}
    if "phase" in text and ("trial" in text or "clinical" in text):
        return {"type": "CLINICAL", "score": 7, "headline": headline, "quality": "HIGH"}
    if "earnings" in text or "revenue" in text:
        return {"type": "EARNINGS", "score": 6, "headline": headline, "quality": "MEDIUM"}
    if "acquisition" in text or "merger" in text:
        return {"type": "M&A", "score": 8, "headline": headline, "quality": "HIGH"}
    if "contract" in text or "agreement" in text:
        return {"type": "CONTRACT", "score": 5, "headline": headline, "quality": "MEDIUM"}
    if "bitcoin" in text or "crypto" in text:
        return {"type": "CRYPTO_TREASURY", "score": 7, "headline": headline, "quality": "HIGH"}
    if "pipe" in text or "atm" in text or "offering" in text:
        return {"type": "CAPITAL_STRUCTURE", "score": 2, "headline": headline, "quality": "LOW"}

    return {"type": "MOMENTUM_ONLY", "score": 1, "headline": headline, "quality": "LOW"}


def score_news(headlines: List[str]) -> Tuple[int, int, Optional[str]]:
    """חישוב מאזן חיובי/שלילי של החדשות"""
    if not headlines:
        return 0, 0, None

    text = " ".join(headlines).lower()
    positive_score = 0
    negative_score = 0
    best_catalyst = None
    best_weight = 0

    positive_cats = POSITIVE_CATALYSTS if 'POSITIVE_CATALYSTS' in globals() else []
    for cat in positive_cats:
        if cat in text:
            weight = 1
            if weight > best_weight:
                best_weight = weight
                best_catalyst = cat
            positive_score += weight

    negative_cats = NEGATIVE_CATALYSTS if 'NEGATIVE_CATALYSTS' in globals() else []
    for neg in negative_cats:
        if neg in text:
            negative_score += 1

    positive_score = min(positive_score, 15)
    negative_score = min(negative_score, 5)

    return positive_score, negative_score, best_catalyst


def get_catalyst_label(headlines: List[str]) -> str:
    """הפקת תווית קטליזטור לתצוגה"""
    if not headlines:
        return "—"

    cat_dict = classify_catalyst(headlines)
    if cat_dict["type"] not in ["MOMENTUM_ONLY", "UNKNOWN"]:
        return cat_dict["type"]

    _, _, catalyst = score_news(headlines)

    if catalyst:
        catalyst = catalyst.replace("direct offering", "offering")
        return catalyst.capitalize()

    try:
        first = headlines[0]
        return first[:50] + "..." if len(first) > 50 else first
    except Exception:
        return "—"


def score_news_quality(headlines: List[str]) -> float:
    """החזרת ציון איכות הקטליזטור"""
    cat_dict = classify_catalyst(headlines)
    return float(cat_dict.get("score", 0))


def get_catalyst_news_score(symbol: str) -> Tuple[float, str]:
    """שליפת חדשות עבור מניה מ-Finnhub וסיווג הציון"""
    print(f"[NewsScanner] 🔍 Fetching news for {symbol}...")
    finnhub_key = FINNHUB_API_KEY or os.getenv('FINNHUB_API_KEY')
    print(f"[NewsScanner] FINNHUB_API_KEY: {'✅' if finnhub_key else '❌ MISSING'}")

    if not finnhub_key:
        print(f"[NewsScanner] ⚠️ FINNHUB_API_KEY missing for {symbol}")
        return 0.0, "—"

    to_date = datetime.now().strftime("%Y-%m-%d")
    from_date = (datetime.now() - timedelta(days=3)).strftime("%Y-%m-%d")

    url = f"https://finnhub.io/api/v1/company-news?symbol={symbol}&from={from_date}&to={to_date}&token={finnhub_key}"

    try:
        resp = requests.get(url, timeout=10)
        if resp.status_code == 200:
            articles = resp.json()
            if isinstance(articles, list):
                print(f"[NewsScanner] Found {len(articles)} articles for {symbol}")
                headlines = [a.get('headline', '').strip() for a in articles if a.get('headline')]
                if headlines:
                    cat_result = classify_catalyst(headlines)
                    cat_score = float(cat_result.get("score", 0))
                    headline_text = headlines[0]
                    print(f"[NewsScanner] Catalyst for {symbol}: '{headline_text}' (Score: {cat_score})")
                    return cat_score, headline_text
        else:
            print(f"[NewsScanner] Finnhub API status {resp.status_code} for {symbol}")
    except Exception as e:
        print(f"[NewsScanner] Error fetching news for {symbol}: {e}")

    print(f"[NewsScanner] No valid news found for {symbol}")
    return 0.0, "—"
