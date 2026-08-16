"""
AI Quant Agent V1 - DAYS-BOT Watchlist Parser

מקבל את הודעת ה-WATCHLIST של DAYS-BOT
וממיר אותה לנתונים מובנים.

אין כאן שום החלטת מסחר.
"""

import re
from typing import List, Dict, Any


def parse_watchlist(message: str) -> List[Dict[str, Any]]:
    """
    Parse raw DAYS-BOT Telegram watchlist.

    Example:
    1. LUMN 💰 $6.73 Gap: +5.1% Score: 90 🟡 PREPARE | Hits: 1 📰 —
    """

    candidates = []

    if not message:
        return candidates

    pattern = re.compile(
        r"""
        (?P<ticker>[A-Z]{1,6})
        \s+
        .*?
        \$\s*(?P<price>\d+(?:\.\d+)?)
        \s+
        Gap:\s*(?P<gap>[+-]?\d+(?:\.\d+)?)
        %
        .*?
        Score:\s*(?P<score>\d+(?:\.\d+)?)
        .*?
        (?P<status>READY|PREPARE|WATCH)
        .*?
        Hits:\s*(?P<hits>\d+)
        """,
        re.IGNORECASE | re.VERBOSE
    )

    for match in pattern.finditer(message):
        try:
            ticker = match.group("ticker").upper()

            # מניעת זבל
            if ticker in {"USD", "USDT", "USDC"}:
                continue

            candidates.append({
                "ticker": ticker,
                "price": float(match.group("price")),
                "gap_pct": float(match.group("gap")),
                "days_score": float(match.group("score")),
                "days_status": match.group("status").upper(),
                "hits": int(match.group("hits")),
                "news": None,
            })

        except (ValueError, TypeError):
            continue

    return candidates


def parse_and_validate(message: str) -> List[Dict[str, Any]]:
    """
    Parse + basic validation.
    """

    candidates = parse_watchlist(message)

    valid = []

    for c in candidates:

        if not c["ticker"]:
            continue

        if c["price"] <= 0:
            continue

        if c["gap_pct"] <= 0:
            continue

        valid.append(c)

    return valid
