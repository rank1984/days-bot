"""
DAYS-BOT V4.1 – Full Scan

Analyzes the best discovery candidates.

Design:
- Discovery already happened.
- Expensive analyzers run only on top 25.
- Analyzer failure never kills the candidate.
- Always returns a list.
- Main.py remains compatible with:
      for c in top20:
"""

from scanner.analyzers.float_analyzer import (
    get_float_and_short,
)

from scanner.scoring_engine import (
    calculate_composite_score,
)

from scanner.analyzers.sec_analyzer import (
    check_offering_risk,
)

from scanner.analyzers.catalyst_analyzer import (
    classify_catalyst,
)

from scanner.analyzers.sentiment_social import (
    get_stocktwits_sentiment,
)

from scanner.analyzers.news_analyzer import (
    fetch_news,
)

from scanner.analyzers.volume_analyzer import (
    calculate_rvol,
)

from scanner.analyzers.rs_analyzer import (
    get_relative_strength,
)

from scanner.analyzers.personality_analyzer import (
    get_stock_personality,
)

from scanner.analyzers.sympathy_scanner import (
    find_sympathy_candidates,
)

from scanner.vwap_engine import (
    calculate_vwap,
    calculate_pm_vwap_from_candidate,
)

from risk.trade_plan_v34 import (
    build_trade_plan,
)

from utils.config import (
    ACCOUNT_SIZE,
    MAX_RISK_PER_TRADE_V31,
    MAX_POSITION_VALUE_PCT,
    MAX_ANALYSIS_CANDIDATES,
    TOP_RESEARCH_CANDIDATES,
)


def _safe_call(
    function,
    *args,
    default=None,
    label="analyzer",
    ticker="",
):
    """
    A single failed analyzer must never terminate the scan.
    """

    try:
        result = function(*args)

        if result is None:
            return default

        return result

    except Exception as e:

        print(
            f"[FullScan] {ticker} "
            f"{label} failed: {e}"
        )

        return default


def _normalize_float_data(data):
    if not isinstance(data, dict):
        return {}

    return data


def _normalize_dict(data):
    if not isinstance(data, dict):
        return {}

    return data


def full_scan_v34(
    candidates,
    manual=False,
) -> list:

    if not candidates:
        return []

    # --------------------------------------------------------
    # Protect input
    # --------------------------------------------------------

    prepared = []

    for candidate in candidates:

        if not isinstance(candidate, dict):
            continue

        ticker = str(
            candidate.get(
                "ticker",
                "",
            )
        ).strip().upper()

        if not ticker:
            continue

        candidate = dict(candidate)

        candidate["ticker"] = ticker

        prepared.append(candidate)

    if not prepared:
        return []

    # Discovery ranking first.
    prepared.sort(
        key=lambda x: (
            x.get(
                "event_score",
                0,
            ),
            abs(
                x.get(
                    "gap_pct",
                    0,
                )
            ),
            x.get(
                "pm_volume",
                0,
            ),
        ),
        reverse=True,
    )

    # --------------------------------------------------------
    # Expensive analysis only for top N
    # --------------------------------------------------------

    scan_candidates = prepared[
        :MAX_ANALYSIS_CANDIDATES
    ]

    enriched = []

    print(
        f"[FullScan] Analyzing "
        f"{len(scan_candidates)} candidates..."
    )

    for index, candidate in enumerate(
        scan_candidates,
        1,
    ):

        ticker = candidate["ticker"]

        print(
            f"[FullScan] "
            f"{index}/{len(scan_candidates)} "
            f"{ticker}"
        )

        analysis = {}

        # ----------------------------------------------------
        # Float / Short
        # ----------------------------------------------------

        float_data = _safe_call(
            get_float_and_short,
            ticker,
            default={},
            label="float",
            ticker=ticker,
        )

        float_data = _normalize_float_data(
            float_data
        )

        analysis["float_data"] = (
            float_data
        )

        analysis["float"] = (
            float_data.get("float")
        )

        analysis["short_interest"] = (
            float_data.get(
                "short_interest"
            )
        )

        # ----------------------------------------------------
        # RVOL
        # ----------------------------------------------------

        rvol = _safe_call(
            calculate_rvol,
            candidate,
            default=0,
            label="rvol",
            ticker=ticker,
        )

        try:
            rvol = float(rvol or 0)
        except Exception:
            rvol = 0

        analysis["rvol"] = rvol

        # ----------------------------------------------------
        # Relative Strength
        # ----------------------------------------------------

        rs = _safe_call(
            get_relative_strength,
            ticker,
            default=0,
            label="relative_strength",
            ticker=ticker,
        )

        analysis["rs"] = rs

        # ----------------------------------------------------
        # News
        # ----------------------------------------------------

        news = _safe_call(
            fetch_news,
            ticker,
            default=[],
            label="news",
            ticker=ticker,
        )

        analysis["news"] = news

        # ----------------------------------------------------
        # Catalyst
        # ----------------------------------------------------

        catalyst = _safe_call(
            classify_catalyst,
            news,
            default={},
            label="catalyst",
            ticker=ticker,
        )

        catalyst = _normalize_dict(
            catalyst
        )

        analysis["catalyst"] = catalyst

        # Make catalyst available to swing engine.
        candidate["catalyst_quality"] = (
            catalyst.get(
                "score",
                0,
            )
        )

        # ----------------------------------------------------
        # Sentiment
        # ----------------------------------------------------

        sentiment = _safe_call(
            get_stocktwits_sentiment,
            ticker,
            default={},
            label="sentiment",
            ticker=ticker,
        )

        analysis["sentiment"] = (
            _normalize_dict(sentiment)
        )

        # ----------------------------------------------------
        # SEC
        # ----------------------------------------------------

        sec_risk = _safe_call(
            check_offering_risk,
            ticker,
            default={},
            label="sec",
            ticker=ticker,
        )

        analysis["sec_risk"] = (
            _normalize_dict(sec_risk)
        )

        # ----------------------------------------------------
        # Personality
        # ----------------------------------------------------

        personality = _safe_call(
            get_stock_personality,
            ticker,
            candidate.get(
                "gap_pct",
                0,
            ),
            default={},
            label="personality",
            ticker=ticker,
        )

        analysis["personality"] = (
            _normalize_dict(personality)
        )

        # ----------------------------------------------------
        # VWAP
        # ----------------------------------------------------

        vwap_data = _safe_call(
            calculate_vwap,
            ticker,
            lookback_minutes=30,
            default=None,
            label="vwap",
            ticker=ticker,
        )

        if not vwap_data:

            vwap_data = _safe_call(
                calculate_pm_vwap_from_candidate,
                candidate,
                default={},
                label="pm_vwap",
                ticker=ticker,
            )

        analysis["vwap"] = (
            _normalize_dict(vwap_data)
        )

        # ----------------------------------------------------
        # Sympathy
        # ----------------------------------------------------

        sympathy = _safe_call(
            find_sympathy_candidates,
            candidate,
            max_candidates=3,
            default=[],
            label="sympathy",
            ticker=ticker,
        )

        analysis["sympathy"] = (
            sympathy
            if isinstance(
                sympathy,
                list,
            )
            else []
        )

        # ----------------------------------------------------
        # Composite score
        # ----------------------------------------------------

        composite_score = _safe_call(
            calculate_composite_score,
            candidate,
            analysis,
            default=0,
            label="composite_score",
            ticker=ticker,
        )

        try:
            composite_score = float(
                composite_score or 0
            )
        except Exception:
            composite_score = 0

        candidate["composite_score"] = round(
            max(
                0,
                min(
                    100,
                    composite_score,
                ),
            ),
            1,
        )

        # ----------------------------------------------------
        # Attach analysis
        # ----------------------------------------------------

        candidate["analysis"] = analysis

        # Compatibility aliases.
        candidate["float"] = analysis.get(
            "float"
        )

        candidate["short_interest"] = (
            analysis.get(
                "short_interest"
            )
        )

        candidate["rvol"] = analysis.get(
            "rvol",
            0,
        )

        candidate["rs"] = analysis.get(
            "rs"
        )

        candidate["sec_risk"] = analysis.get(
            "sec_risk",
            {},
        )

        candidate["personality"] = (
            analysis.get(
                "personality",
                {},
            )
        )

        # ----------------------------------------------------
        # Research flags
        # ----------------------------------------------------

        candidate["research_status"] = (
            "ANALYZED"
        )

        candidate["manual"] = bool(
            manual
        )

        enriched.append(candidate)

    # --------------------------------------------------------
    # Sort
    # --------------------------------------------------------

    enriched.sort(
        key=lambda x: (
            x.get(
                "composite_score",
                0,
            ),
            x.get(
                "event_score",
                0,
            ),
        ),
        reverse=True,
    )

    # --------------------------------------------------------
    # Always return Top 5
    # --------------------------------------------------------

    top5 = enriched[
        :TOP_RESEARCH_CANDIDATES
    ]

    if not top5:
        # Last-resort fallback.
        return prepared[
            :TOP_RESEARCH_CANDIDATES
        ]

    # --------------------------------------------------------
    # Build conditional plans.
    #
    # We do NOT require high score here.
    # The plan can exist while decision remains WAIT_BREAKOUT.
    # --------------------------------------------------------

    for candidate in top5:

        plan = _safe_call(
            build_trade_plan,
            candidate,
            account_size=ACCOUNT_SIZE,
            max_risk_pct=MAX_RISK_PER_TRADE_V31,
            max_position_pct=MAX_POSITION_VALUE_PCT,
            default={},
            label="trade_plan",
            ticker=candidate["ticker"],
        )

        if not isinstance(plan, dict):
            plan = {}

        candidate.update(
            {
                "entry": plan.get(
                    "entry"
                ),
                "stop": plan.get(
                    "stop"
                ),
                "target_1": plan.get(
                    "target_1"
                ),
                "target_2": plan.get(
                    "target_2"
                ),
                "position_size": plan.get(
                    "position_size",
                    0,
                ),
                "max_loss": plan.get(
                    "max_loss",
                    0,
                ),
                "risk_per_share": plan.get(
                    "risk_per_share"
                ),
                "plan_valid": plan.get(
                    "plan_valid",
                    False,
                ),
                "plan_error": plan.get(
                    "plan_error"
                ),
                "decision": plan.get(
                    "decision",
                    "NO_TRADE",
                ),
            }
        )

    print(
        "[FullScan] Top 5:",
        ", ".join(
            f"{c['ticker']}="
            f"{c.get('composite_score', 0):.1f}"
            for c in top5
        ),
    )

    return top5
