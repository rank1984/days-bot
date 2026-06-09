"""
scoring.py V3
--------------
Gap           25  — הכי חשוב
PM RVOL       20  — soft, לא פוסל
Dollar Volume 15  — נזילות
News          15  — catalyst
Float         15  — קטן = חזק
Price          5  — sweet spot
Momentum       5  — gap × dvol

Grade:
A+  85+   — פריצה מיידית
A   70-84  — Watch closely
B   55-69  — Secondary
C   <55    — Ignore
"""

import pandas as pd
import numpy as np


def _norm(series: pd.Series, lo: float, hi: float) -> pd.Series:
    c = series.clip(lo, hi)
    return (c - lo) / (hi - lo) if hi > lo else pd.Series(0.0, index=series.index)


def get_grade(score: float) -> str:
    if score >= 85: return "A+"
    if score >= 70: return "A"
    if score >= 55: return "B"
    return "C"


def score_candidates(df: pd.DataFrame) -> pd.DataFrame:
    if df.empty:
        return df

    out = df.copy()

    # Gap Score (25)
    out["gap_score"] = (_norm(out["gap_pct"], 8, 35) * 25).round(1)

    # PM RVOL Score (20) — SOFT
    rvol_col = "pm_rvol" if "pm_rvol" in out.columns else "vol_ratio"
    out["rvol_score"] = out[rvol_col].apply(
        lambda r: min(r * 8, 20) if r > 0 else 2
    ).round(1)

    # Dollar Volume Score (15)
    if "dollar_volume" in out.columns:
        out["dvol_score"] = (_norm(out["dollar_volume"], 100_000, 5_000_000) * 15).round(1)
    else:
        out["dvol_score"] = 0

    # News Score (15)
    if "news_score" in out.columns:
        out["news_pts"] = out["news_score"].apply(
            lambda s: 15 if s >= 30 else
                      12 if s >= 25 else
                      10 if s >= 20 else
                       7 if s >= 10 else
                       0 if s < 0  else 3
        )
    else:
        out["news_pts"] = 3

    # Float Score (15)
    def float_pts(f):
        if f == 0:                return 7
        if f < 5_000_000:         return 15
        if f < 10_000_000:        return 13
        if f < 20_000_000:        return 10
        if f < 50_000_000:        return 7
        if f < 100_000_000:       return 4
        return 2
    out["float_score"] = out["float"].apply(float_pts)

    # Price Score (5)
    def price_pts(p):
        if 2 <= p <= 10:   return 5
        if 10 < p <= 15:   return 3
        if 1 <= p < 2:     return 2
        return 1
    out["price_score"] = out["price"].apply(price_pts)

    # Momentum (5)
    if "dollar_volume" in out.columns:
        m_raw = np.log1p(out["gap_pct"] * out["dollar_volume"] / 1_000_000)
        out["momentum_score"] = (_norm(m_raw, 0, np.log1p(30 * 5)) * 5).round(1)
    else:
        out["momentum_score"] = 0

    # Total
    out["score"] = (
        out["gap_score"]  + out["rvol_score"]  + out["dvol_score"] +
        out["news_pts"]   + out["float_score"] + out["price_score"] +
        out["momentum_score"]
    ).round(1).clip(0, 100)

    # Grade
    out["grade"] = out["score"].apply(get_grade)

    out.sort_values("score", ascending=False, inplace=True)
    out.reset_index(drop=True, inplace=True)

    if len(out) > 0:
        top = out.iloc[0]
        print(f"[Scoring] Top: {top['ticker']} score={top['score']:.1f} grade={top['grade']}")
    return out
