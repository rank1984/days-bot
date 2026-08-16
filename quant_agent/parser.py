"""
DAYS-BOT Telegram Watchlist Parser

מקבל את הודעת ה-WATCHLIST הגולמית של DAYS-BOT
וממיר אותה לרשימת מועמדים מובנית.
"""

import re
from typing import List, Dict, Any


TICKER_PATTERN = r"\*\*(?:\d+\.\s*)?([A-Z]{1,6})\*\*"


def parse_watchlist(message: str) -> List[Dict[str, Any]]:
    """
    Parse raw DAYS-BOT Telegram message.

    Expected format example:

    **1. LUMN** 💰 $6.73 Gap: +5.1% Score: 90
    🟡 PREPARE | Hits: 1 📰 —
    """

    if not message:
        return []

    candidates = []

    # מחלק לפי מספרי המניות
    blocks = re.split(r"\*\*\d+\.\s*", message)

    for block in blocks[1:]:
        try:
            ticker_match = re.match(r"([A-Z]{1,6})\*\*", block)
            if not ticker_match:
                continue

            ticker = ticker_match.group(1)

            price_match = re.search(
                r"💰\s*\$?([\d.]+)",
                block
            )

            gap_match = re.search(
                r"Gap:\s*([+-]?[\d.]+)%",
                block,
                re.IGNORECASE
            )

            score_match = re.search(
                r"Score:\s*([\d.]+)",
                block,
                re.IGNORECASE
            )

            hits_match = re.search(
                r"Hits:\s*(\d+)",
                block,
                re.IGNORECASE
            )

            status_match = re.search(
                r"(PREPARE|WATCH|READY|TRIGGERED|INVALIDATED)",
                block,
                re.IGNORECASE
            )

            # חילוץ news
            news_match = re.search(
                r"📰\s*(.*?)(?=\n|━━━━━━━━|$)",
                block,
                re.DOTALL
            )

            price = float(price_match.group(1)) if price_match else None
            gap_pct = float(gap_match.group(1)) if gap_match else None
            days_score = float(score_match.group(1)) if score_match else 0.0
            hits = int(hits_match.group(1)) if hits_match else 1

            status = (
                status_match.group(1).upper()
                if status_match
                else "WATCH"
            )

            news = (
                news_match.group(1).strip()
                if news_match
                else None
            )

            if news in ("—", "-", "", "None"):
                news = None

            if price is None or gap_pct is None:
                continue

            candidates.append({
                "ticker": ticker,
                "price": price,
                "gap_pct": gap_pct,
                "days_score": days_score,
                "days_status": status,
                "hits": hits,
                "news": news,
            })

        except Exception as e:
            print(f"[Parser] Error parsing block: {e}")
            continue

    print(f"[Parser] Parsed {len(candidates)} candidates")

    return candidates
