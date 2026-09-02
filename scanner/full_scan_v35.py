"""
DAYS-BOT V4.1 – Full Research Scan

Principles:
- Always preserve Top 5 research candidates.
- Enrichment failures become UNKNOWN.
- Optional analyzers never destroy discovery.
- Trade candidate is separate from research candidate.
- Intraday and Swing scores are preserved separately.
"""

from scanner.analyzers.float_analyzer import get_float_and_short
from scanner.analyzers.sec_analyzer import check_offering_risk
from scanner.analyzers.catalyst_analyzer import classify_catalyst
from scanner.analyzers.sentiment_social import get_stocktwits_sentiment
from scanner.analyzers.news_analyzer import fetch_news
from scanner.analyzers.volume_analyzer import calculate_rvol
from scanner.analyzers.rs_analyzer import get_relative_strength
from scanner.analyzers.personality_analyzer import get_stock_personality
from scanner.analyzers.sympathy_scanner import find_sympathy_candidates

from scanner.vwap_engine import (
    calculate_vwap,
    calculate_pm_vwap_from_candidate,
)

from risk.trade_plan_v34 import build_trade_plan
from scanner.scoring_engine import calculate_scores

from utils.config import (
    ACCOUNT_SIZE,
    MAX_RISK_PER_TRADE_V31,
    MAX_POSITION_VALUE_PCT,
)


# ============================================================
# SAFE CALL
# ============================================================

def _safe_call(
    fn,
    *args,
    default=None,
    **kwargs
):
    try:
        result = fn(*args, **kwargs)

        if result is None:
            return default

        return result

    except Exception as e:
        return default


# ============================================================
# NORMALIZE
# ============================================================

def _normalize_analysis(
    analysis: dict
) -> dict:

    if not isinstance(
        analysis.get("float_data"),
        dict
    ):
        analysis["float_data"] = {}

    if not isinstance(
        analysis.get("sec_risk"),
        dict
    ):
        analysis["sec_risk"] = {
            "risk_level": "UNKNOWN"
        }

    if not isinstance(
        analysis.get("catalyst"),
        dict
    ):
        analysis["catalyst"] = {
            "score": 0,
            "type": "UNKNOWN"
        }

    if not isinstance(
        analysis.get("personality"),
        dict
    ):
        analysis["personality"] = {
            "personality": "UNKNOWN"
        }

    if not isinstance(
        analysis.get("sympathy"),
        list
    ):
        analysis["sympathy"] = []

    return analysis


# ============================================================
# FULL SCAN
# ============================================================

def full_scan_v35(
    candidates,
    manual=False
) -> dict:

    if not candidates:
        return {
            "top5_research": [],
            "trade_candidates": [],
            "filter_funnel": {},
            "near_misses": [],
        }

    enriched = []

    filter_stats = {
        "total": len(candidates),

        "price_ok": 0,
        "gap_ok": 0,
        "pm_ok": 0,

        "rvol_ok": 0,
        "float_ok": 0,
        "sec_ok": 0,
        "personality_ok": 0,

        "analysis_success": 0,
        "analysis_partial": 0,

        "trade_candidates": 0,
    }

    # --------------------------------------------------------
    # IMPORTANT:
    # Scan up to 25, not just hard-passed candidates.
    # --------------------------------------------------------

    for original in candidates[:25]:

        c = dict(original)

        ticker = c.get("ticker")

        if not ticker:
            continue

        analysis = {}

        # ----------------------------------------------------
        # Basic data
        # ----------------------------------------------------

        price = c.get("price")

        if price is not None:
            filter_stats["price_ok"] += 1

        gap_pct = c.get(
            "gap_pct",
            0
        ) or 0

        if gap_pct >= 5:
            filter_stats["gap_ok"] += 1

        pm_volume = c.get(
            "pm_volume",
            0
        ) or 0

        if pm_volume > 0:
            filter_stats["pm_ok"] += 1

        # ----------------------------------------------------
        # Float
        # ----------------------------------------------------

        float_data = _safe_call(
            get_float_and_short,
            ticker,
            default={}
        )

        analysis["float_data"] = (
            float_data
            if isinstance(float_data, dict)
            else {}
        )

        analysis["float"] = (
            analysis["float_data"]
            .get("float")
        )

        analysis["short_interest"] = (
            analysis["float_data"]
            .get("short_interest")
        )

        float_value = analysis["float"]

        if (
            float_value is not None
            and float_value < 50_000_000
        ):
            filter_stats["float_ok"] += 1

        # ----------------------------------------------------
        # RVOL
        # ----------------------------------------------------

        rvol = _safe_call(
            calculate_rvol,
            c,
            default=None
        )

        analysis["rvol"] = rvol

        if (
            rvol is not None
            and rvol >= 3
        ):
            filter_stats["rvol_ok"] += 1

        # ----------------------------------------------------
        # News
        # ----------------------------------------------------

        news = _safe_call(
            fetch_news,
            ticker,
            default=[]
        )

        analysis["news"] = (
            news
            if news is not None
            else []
        )

        # ----------------------------------------------------
        # Catalyst
        # ----------------------------------------------------

        catalyst = _safe_call(
            classify_catalyst,
            analysis["news"],
            default={
                "score": 0,
                "type": "UNKNOWN"
            }
        )

        analysis["catalyst"] = catalyst

        # ----------------------------------------------------
        # Sentiment
        # ----------------------------------------------------

        sentiment = _safe_call(
            get_stocktwits_sentiment,
            ticker,
            default={
                "score": None,
                "label": "UNKNOWN"
            }
        )

        analysis["sentiment"] = sentiment

        # ----------------------------------------------------
        # SEC
        # ----------------------------------------------------

        sec_risk = _safe_call(
            check_offering_risk,
            ticker,
            default={
                "risk_level": "UNKNOWN"
            }
        )

        analysis["sec_risk"] = sec_risk

        if (
            sec_risk.get("risk_level")
            != "HIGH"
        ):
            filter_stats["sec_ok"] += 1

        # ----------------------------------------------------
        # Personality
        # ----------------------------------------------------

        personality = _safe_call(
            get_stock_personality,
            ticker,
            gap_pct,
            default={
                "personality": "UNKNOWN"
            }
        )

        analysis["personality"] = personality

        if (
            personality.get("personality")
            != "GAP_AND_CRAP"
        ):
            filter_stats[
                "personality_ok"
            ] += 1

        # ----------------------------------------------------
        # VWAP
        # ----------------------------------------------------

        vwap_data = _safe_call(
            calculate_vwap,
            ticker,
            lookback_minutes=30,
            default=None
        )

        if not vwap_data:
            vwap_data = (
                calculate_pm_vwap_from_candidate(c)
            )

        analysis["vwap"] = (
            vwap_data
            if vwap_data
            else {
                "vwap": c.get("pm_vwap")
            }
        )

        # ----------------------------------------------------
        # Sympathy
        # ----------------------------------------------------

        sympathy = _safe_call(
            find_sympathy_candidates,
            c,
            max_candidates=3,
            default=[]
        )

        analysis["sympathy"] = (
            sympathy
            if isinstance(sympathy, list)
            else []
        )

        # ----------------------------------------------------
        # Normalize
        # ----------------------------------------------------

        analysis = _normalize_analysis(
            analysis
        )

        # ----------------------------------------------------
        # SCORE
        # ----------------------------------------------------

        scores = _safe_call(
            calculate_scores,
            c,
            analysis,
            default={}
        )

        if not isinstance(scores, dict):
            scores = {}

        c.update(scores)

        # Preserve useful score aliases.
        if "intraday_score" not in c:
            c["intraday_score"] = c.get(
                "trade_score",
                c.get("event_score", 0)
            )

        if "swing_score" not in c:
            c["swing_score"] = c.get(
                "trade_score",
                0
            )

        if "final_score" not in c:
            c["final_score"] = max(
                c.get("intraday_score", 0) or 0,
                c.get("swing_score", 0) or 0
            )

        # ----------------------------------------------------
        # Research metadata
        # ----------------------------------------------------

        c["analysis"] = analysis

        c["research_candidate"] = True

        c["manual"] = manual

        c["data_quality"] = (
            "GOOD"
            if c.get("pm_data_quality")
            in {
                "GOOD_DATA",
                "DAILY_DISCOVERY"
            }
            else "PARTIAL"
        )

        if c["data_quality"] == "GOOD":
            filter_stats[
                "analysis_success"
            ] += 1
        else:
            filter_stats[
                "analysis_partial"
            ] += 1

        enriched.append(c)

    # ========================================================
    # SORT RESEARCH
    # ========================================================

    enriched.sort(
        key=lambda x: (
            x.get("final_score", 0) or 0,
            x.get("event_score", 0) or 0,
            x.get("gap_pct", 0) or 0,
        ),
        reverse=True
    )

    # ========================================================
    # TOP 5 – ALWAYS
    # ========================================================

    top5_research = enriched[:5]

    # ========================================================
    # TRADE CANDIDATES
    # ========================================================

    trade_candidates = [
        c
        for c in enriched
        if c.get(
            "is_trade_candidate",
            False
        )
    ]

    # ========================================================
    # TRADE PLANS
    # ========================================================

    for c in trade_candidates[:5]:

        plan = _safe_call(
            build_trade_plan,
            c,
            ACCOUNT_SIZE,
            MAX_RISK_PER_TRADE_V31,
            MAX_POSITION_VALUE_PCT,
            default={}
        )

        if isinstance(plan, dict):
            c.update(plan)

    filter_stats[
        "trade_candidates"
    ] = len(trade_candidates)

    # ========================================================
    # NEAR MISSES
    # ========================================================

    near_misses = [
        c
        for c in enriched[:10]
        if not c.get(
            "is_trade_candidate",
            False
        )
    ][:5]

    # ========================================================
    # RESULT
    # ========================================================

    return {
        "top5_research": top5_research,

        "trade_candidates":
            trade_candidates[:5],

        "filter_funnel":
            filter_stats,

        "near_misses":
            near_misses,
    }