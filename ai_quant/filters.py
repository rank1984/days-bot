"""
AI Quant Agent V1 - Hard Filters

מסנן בעיות ביצוע לפני שהמניה מקבלת Score.
"""

from typing import Dict, Any


# V1 - ערכים התחלתיים בלבד.
# בהמשך נלמד אותם מהיסטוריית עסקאות.
MAX_SPREAD_PCT = 1.50
MIN_DOLLAR_VOLUME = 100_000
MAX_DISTANCE_FROM_HIGH_PCT = 7.0
MAX_DAYS_GAP_PCT = 25.0


def apply_hard_filters(candidate: Dict[str, Any]) -> Dict[str, Any]:

    candidate["filter_pass"] = True
    candidate["rejection_reason"] = None

    # Data
    if not candidate.get("data_ok"):
        return reject(candidate, "NO_LIVE_DATA")

    price = candidate.get("live_price", 0)

    if price <= 0:
        return reject(candidate, "INVALID_PRICE")

    # Spread
    spread = candidate.get("spread_pct", 0)

    if spread > MAX_SPREAD_PCT:
        return reject(
            candidate,
            f"SPREAD_TOO_WIDE:{spread:.2f}%"
        )

    # Dollar volume
    dvol = candidate.get("dollar_volume", 0)

    if dvol < MIN_DOLLAR_VOLUME:
        return reject(
            candidate,
            f"LOW_DOLLAR_VOLUME:{dvol:.0f}"
        )

    # Gap sanity
    gap = candidate.get("gap_pct", 0)

    if gap <= 0:
        return reject(candidate, "NO_POSITIVE_GAP")

    if gap > MAX_DAYS_GAP_PCT:
        return reject(candidate, "EXTREME_GAP")

    # Distance from PMH
    distance = candidate.get(
        "distance_to_high_pct",
        0
    )

    if distance > MAX_DISTANCE_FROM_HIGH_PCT:
        return reject(
            candidate,
            f"TOO_FAR_FROM_HIGH:{distance:.2f}%"
        )

    return candidate


def reject(
    candidate: Dict[str, Any],
    reason: str
) -> Dict[str, Any]:

    candidate["filter_pass"] = False
    candidate["rejection_reason"] = reason

    return candidate
