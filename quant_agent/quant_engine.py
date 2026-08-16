"""
AI Quant Engine V1
Layer 2 above DAYS-BOT.

Purpose:
- Re-rank DAYS-BOT candidates independently
- Evaluate momentum, liquidity, spread, RVOL and breakout quality
- Estimate execution quality
- Produce a transparent quantitative score

IMPORTANT:
This module does NOT execute trades.
"""

from typing import Dict, Any, List
from math import isfinite


# ============================================================
# CONFIG
# ============================================================

MIN_PRICE = 1.00
MAX_PRICE = 20.00

MIN_GAP = 2.0
MAX_GAP = 20.0

MIN_RVOL = 1.50
GOOD_RVOL = 2.50

MIN_DOLLAR_VOLUME = 250_000
GOOD_DOLLAR_VOLUME = 1_000_000

MAX_SPREAD_PCT = 1.50
GOOD_SPREAD_PCT = 0.50

MAX_FLOAT = 50_000_000

MIN_OPPORTUNITY = 55
MAX_RISK = 70


# ============================================================
# HELPERS
# ============================================================

def safe_float(value, default=0.0):
    try:
        if value is None:
            return default

        value = float(value)

        if not isfinite(value):
            return default

        return value

    except Exception:
        return default


def clamp(value, low=0.0, high=100.0):
    return max(low, min(high, value))


# ============================================================
# HARD FILTERS
# ============================================================

def hard_filter(candidate: Dict[str, Any]) -> Dict[str, Any]:

    ticker = candidate.get("ticker", "?")

    price = safe_float(candidate.get("price"))
    gap = safe_float(candidate.get("gap_pct"))
    rvol = safe_float(
        candidate.get("rvol"),
        candidate.get("pm_rvol", 0)
    )

    dvol = safe_float(candidate.get("dollar_volume"))
    spread = safe_float(candidate.get("spread_pct"))

    float_shares = safe_float(
        candidate.get("float"),
        candidate.get("float_shares", 0)
    )

    reasons = []

    # Price
    if price < MIN_PRICE:
        reasons.append("price too low")

    if price > MAX_PRICE:
        reasons.append("price too high")

    # Gap
    if gap < MIN_GAP:
        reasons.append("gap too small")

    if gap > MAX_GAP:
        reasons.append("gap extended")

    # RVOL
    if rvol > 0 and rvol < MIN_RVOL:
        reasons.append("RVOL insufficient")

    # Dollar volume
    if dvol > 0 and dvol < MIN_DOLLAR_VOLUME:
        reasons.append("dollar volume too low")

    # Spread
    if spread > MAX_SPREAD_PCT:
        reasons.append("spread too wide")

    # Float
    if float_shares > MAX_FLOAT:
        reasons.append("float too high")

    passed = len(reasons) == 0

    return {
        "ticker": ticker,
        "passed": passed,
        "reasons": reasons
    }


# ============================================================
# OPPORTUNITY SCORE
# ============================================================

def calculate_opportunity(candidate: Dict[str, Any]) -> float:

    gap = safe_float(candidate.get("gap_pct"))
    rvol = safe_float(
        candidate.get("rvol"),
        candidate.get("pm_rvol", 0)
    )

    dvol = safe_float(candidate.get("dollar_volume"))
    float_shares = safe_float(candidate.get("float"))

    momentum = safe_float(candidate.get("momentum_score"))
    relative_strength = safe_float(
        candidate.get("relative_strength")
    )

    news_score = safe_float(candidate.get("news_score"))

    score = 0.0

    # --------------------------------------------------------
    # GAP / MOMENTUM
    # --------------------------------------------------------

    if 3 <= gap <= 10:
        score += 20
    elif 2 <= gap < 3:
        score += 12
    elif 10 < gap <= 15:
        score += 12
    elif gap > 15:
        score += 5

    # --------------------------------------------------------
    # RVOL
    # --------------------------------------------------------

    if rvol >= 4:
        score += 20
    elif rvol >= 3:
        score += 17
    elif rvol >= 2.5:
        score += 14
    elif rvol >= 2:
        score += 10
    elif rvol >= 1.5:
        score += 6

    # --------------------------------------------------------
    # DOLLAR VOLUME
    # --------------------------------------------------------

    if dvol >= 2_000_000:
        score += 20
    elif dvol >= 1_000_000:
        score += 16
    elif dvol >= 500_000:
        score += 12
    elif dvol >= 250_000:
        score += 7

    # --------------------------------------------------------
    # FLOAT
    # --------------------------------------------------------

    if 0 < float_shares <= 15_000_000:
        score += 12
    elif float_shares <= 30_000_000:
        score += 8
    elif float_shares <= 50_000_000:
        score += 4

    # --------------------------------------------------------
    # INTERNAL MOMENTUM
    # --------------------------------------------------------

    score += clamp(momentum * 0.10, 0, 8)

    # --------------------------------------------------------
    # RELATIVE STRENGTH
    # --------------------------------------------------------

    if relative_strength >= 5:
        score += 8
    elif relative_strength >= 3:
        score += 6
    elif relative_strength >= 1:
        score += 3

    # --------------------------------------------------------
    # CATALYST
    # --------------------------------------------------------

    score += clamp(news_score * 0.8, 0, 8)

    return round(clamp(score), 1)


# ============================================================
# RISK SCORE
# Higher = WORSE
# ============================================================

def calculate_risk(candidate: Dict[str, Any]) -> float:

    gap = safe_float(candidate.get("gap_pct"))
    spread = safe_float(candidate.get("spread_pct"))
    rvol = safe_float(
        candidate.get("rvol"),
        candidate.get("pm_rvol", 0)
    )

    dvol = safe_float(candidate.get("dollar_volume"))
    float_shares = safe_float(candidate.get("float"))

    risk = 20.0

    # --------------------------------------------------------
    # EXTENDED GAP
    # --------------------------------------------------------

    if gap > 15:
        risk += 20
    elif gap > 10:
        risk += 12
    elif gap > 8:
        risk += 6

    # --------------------------------------------------------
    # SPREAD
    # --------------------------------------------------------

    if spread > 1.5:
        risk += 25
    elif spread > 1.0:
        risk += 15
    elif spread > 0.5:
        risk += 8

    # --------------------------------------------------------
    # LOW RVOL
    # --------------------------------------------------------

    if rvol < 1.5:
        risk += 20
    elif rvol < 2:
        risk += 10

    # --------------------------------------------------------
    # LOW LIQUIDITY
    # --------------------------------------------------------

    if 0 < dvol < 250_000:
        risk += 20
    elif dvol < 500_000:
        risk += 10

    # --------------------------------------------------------
    # FLOAT
    # --------------------------------------------------------

    if float_shares > 50_000_000:
        risk += 8

    return round(clamp(risk), 1)


# ============================================================
# TRADEABILITY
# ============================================================

def calculate_tradeability(candidate: Dict[str, Any]) -> Dict[str, Any]:

    spread = safe_float(candidate.get("spread_pct"))
    dvol = safe_float(candidate.get("dollar_volume"))
    rvol = safe_float(
        candidate.get("rvol"),
        candidate.get("pm_rvol", 0)
    )

    reasons = []

    if spread > MAX_SPREAD_PCT:
        reasons.append("spread too wide")

    if dvol > 0 and dvol < MIN_DOLLAR_VOLUME:
        reasons.append("low dollar volume")

    if rvol > 0 and rvol < MIN_RVOL:
        reasons.append("low RVOL")

    passed = len(reasons) == 0

    return {
        "status": "PASS" if passed else "FAIL",
        "reasons": reasons
    }


# ============================================================
# FINAL SCORE
# ============================================================

def calculate_final_score(
    opportunity: float,
    risk: float,
    tradeability: str
) -> float:

    if tradeability != "PASS":
        return 0.0

    # Opportunity dominates.
    # Risk is a penalty.
    score = (
        opportunity * 0.75
        +
        (100 - risk) * 0.25
    )

    return round(clamp(score), 1)


# ============================================================
# SIGNAL STATE
# ============================================================

def determine_state(candidate: Dict[str, Any]) -> str:

    price = safe_float(candidate.get("price"))
    pm_high = safe_float(candidate.get("pm_high"))

    rvol = safe_float(
        candidate.get("rvol"),
        candidate.get("pm_rvol", 0)
    )

    if pm_high <= 0:
        return "WATCH"

    distance = ((pm_high - price) / pm_high) * 100

    # Already breaking out
    if price >= pm_high and rvol >= 2.0:
        return "READY"

    # Very close to PMH
    if distance <= 1.0 and rvol >= 1.5:
        return "BREAKOUT_PENDING"

    if distance <= 3.0:
        return "PREPARE"

    return "WATCH"


# ============================================================
# ANALYZE ONE
# ============================================================

def analyze_candidate(candidate: Dict[str, Any]) -> Dict[str, Any]:

    ticker = candidate.get("ticker", "?")

    filters = hard_filter(candidate)

    opportunity = calculate_opportunity(candidate)

    risk = calculate_risk(candidate)

    tradeability = calculate_tradeability(candidate)

    final_score = calculate_final_score(
        opportunity,
        risk,
        tradeability["status"]
    )

    state = determine_state(candidate)

    if not filters["passed"]:
        decision = "NO TRADE"
    elif tradeability["status"] != "PASS":
        decision = "NO TRADE"
    elif opportunity < MIN_OPPORTUNITY:
        decision = "WATCH"
    elif risk > MAX_RISK:
        decision = "WATCH"
    else:
        decision = state

    return {
        "ticker": ticker,
        "price": safe_float(candidate.get("price")),
        "gap_pct": safe_float(candidate.get("gap_pct")),
        "days_score": safe_float(candidate.get("score")),
        "days_status": candidate.get("status", "UNKNOWN"),
        "days_hits": candidate.get("hits", 1),

        "opportunity": opportunity,
        "risk": risk,
        "tradeability": tradeability["status"],
        "tradeability_reasons": tradeability["reasons"],

        "final_score": final_score,
        "state": state,
        "decision": decision,

        "rvol": safe_float(
            candidate.get("rvol"),
            candidate.get("pm_rvol", 0)
        ),

        "dollar_volume": safe_float(
            candidate.get("dollar_volume")
        ),

        "float": safe_float(
            candidate.get("float")
        ),

        "pm_high": safe_float(
            candidate.get("pm_high")
        ),

        "vwap": safe_float(
            candidate.get("vwap")
        ),

        "catalyst": candidate.get(
            "catalyst",
            "—"
        ),

        "news_score": safe_float(
            candidate.get("news_score")
        ),

        "filter_passed": filters["passed"],
        "filter_reasons": filters["reasons"]
    }


# ============================================================
# ANALYZE WATCHLIST
# ============================================================

def analyze_watchlist(
    candidates: List[Dict[str, Any]]
) -> List[Dict[str, Any]]:

    results = []

    for candidate in candidates:
        try:
            result = analyze_candidate(candidate)
            results.append(result)
        except Exception as e:
            print(
                f"[QuantEngine] Error analyzing "
                f"{candidate.get('ticker', '?')}: {e}"
            )

    results.sort(
        key=lambda x: x.get("final_score", 0),
        reverse=True
    )

    return results
