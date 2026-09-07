"""
DAYS-BOT V4.3 – Catalyst Analyzer
Heuristic fallback based on news keywords (no Gemini dependency).
"""
import re
from typing import List


def classify_catalyst(headlines: List[str]) -> dict:
    """
    Classify catalyst based on news headlines.
    Returns: {"type": str, "score": int, "summary": str}
    """
    if not headlines:
        return {
            "type": "UNAVAILABLE",
            "score": 0,
            "summary": "אין חדשות אחרונות."
        }

    # Combine headlines
    text = " ".join(headlines[:5]).upper()

    # Strong catalysts
    strong_keywords = {
        "FDA": ["FDA", "APPROVAL", "TRIAL", "PHASE"],
        "EARNINGS": ["EARNINGS", "BEAT", "RAISES", "GUIDANCE", "REVENUE"],
        "CONTRACT": ["CONTRACT", "AGREEMENT", "PARTNERSHIP", "COLLABORATION"],
        "M&A": ["ACQUISITION", "MERGER", "BUYOUT", "TAKEOVER"],
    }

    # Weak catalysts
    weak_keywords = ["ANALYST", "UPGRADE", "INITIATES", "COVERAGE", "REITERATES"]

    # Check for strong catalysts
    for cat_type, keywords in strong_keywords.items():
        if any(kw in text for kw in keywords):
            # Check additional context
            if cat_type == "FDA" and ("APPROVAL" in text or "POSITIVE" in text):
                return {
                    "type": "FDA_APPROVAL",
                    "score": 9,
                    "summary": "אישור/התקדמות רגולטורית משמעותית."
                }
            elif cat_type == "EARNINGS" and ("BEAT" in text or "RAISES" in text):
                return {
                    "type": "EARNINGS",
                    "score": 8,
                    "summary": "תוצאות דוחות כספיים חיוביות."
                }
            elif cat_type == "CONTRACT":
                return {
                    "type": "CONTRACT",
                    "score": 8,
                    "summary": "חוזה או שותפות אסטרטגית חדשה."
                }
            elif cat_type == "M&A":
                return {
                    "type": "M&A",
                    "score": 9,
                    "summary": "רכישה או מיזוג משמעותי."
                }
            else:
                return {
                    "type": "STRONG",
                    "score": 7,
                    "summary": "חדשות חיוביות משמעותיות."
                }

    # Check for weak catalysts
    if any(kw in text for kw in weak_keywords):
        return {
            "type": "WEAK",
            "score": 4,
            "summary": "חדשות קלות - אנליסט/כיסוי."
        }

    # Check for general positive/negative sentiment
    positive = ["POSITIVE", "GROWTH", "EXPANSION", "LAUNCH", "NEW", "SUCCESS"]
    negative = ["NEGATIVE", "DECLINE", "LOSS", "DELAY", "FAILURE", "INVESTIGATION"]

    if any(kw in text for kw in positive):
        return {
            "type": "GENERAL",
            "score": 5,
            "summary": "חדשות כלליות עם נטייה חיובית."
        }

    if any(kw in text for kw in negative):
        return {
            "type": "GENERAL",
            "score": 2,
            "summary": "חדשות כלליות עם נטייה שלילית."
        }

    # Default
    return {
        "type": "GENERAL",
        "score": 3,
        "summary": "חדשות כלליות ללא קטליזטור מובהק."
    }