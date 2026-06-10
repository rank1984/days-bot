"""
scoring.py V3
--------------
News Catalyst   30
Gap %           20
RVOL            20
Float           15
Dollar Volume   10
Sector Sympathy  5
סה"כ           100
"""

import pandas as pd
import numpy as np


def _norm(series: pd.Series, lo: float, hi: float) -> pd.Series:
    c = series.clip(lo, hi)
    return (c - lo) / (hi - lo) if hi > lo else pd.Series(0.0, index=series.index)


def get_grade(score: float) -> str:
    if score >= 85: return "A+"
    if score >= 70: return "A"
    if score >= 60: return "B"
    return "C"


def score_candidates(df: pd.DataFrame) -> pd.DataFrame:
    if df.empty:
        return df

    out = df.copy()

    # News Catalyst (30) — הכי חשוב
    if "news_score" in out.columns:
        out["news_pts"] = out["news_score"].apply(
            lambda s: 30 if s >= 30 else   # FDA/Approval
                      25 if s >= 25 else   # M&A
                      20 if s >= 20 else   # Contract
                      15 if s >= 15 else   # Earnings
                      10 if s >= 10 else   # Patent
                       5 if s >= 5  else   # News
                       0 if s < 0   else   # Offering — לא פוסל אבל 0
                       3                   # אין חדשות
        )
    else:
        out["news_pts"] = 3

    # Gap % (20)
    out["gap_score"] = (_norm(out["gap_pct"], 5, 40) * 20).round(1)

    # RVOL (20) — מודל ניקוד לפי טיירים
    rvol_col = "pm_rvol" if "pm_rvol" in out.columns else "vol_ratio"
    def rvol_pts(r):
        if r >= 3: return 20
        if r >= 2: return 15
        if r >= 1: return 5
        return 0
    out["rvol_score"] = out[rvol_col].apply(rvol_pts)

    # Float (15)
    def float_pts(f):
        if f == 0:              return 7   # לא ידוע
        if f < 5_000_000:       return 15
        if f < 10_000_000:      return 13
        if f < 20_000_000:      return 10
        if f < 50_000_000:      return 7
        if f < 100_000_000:     return 4
        return 2
    out["float_score"] = out["float"].apply(float_pts)

    # Dollar Volume (10)
    if "dollar_volume" in out.columns:
        out["dvol_score"] = (_norm(out["dollar_volume"], 250_000, 5_000_000) * 10).round(1)
    else:
        out["dvol_score"] = 0

    # Sector Sympathy (5)
    if "is_leader" in out.columns:
        out["sympathy_score"] = out.apply(
            lambda r: 5 if r.get("is_leader") else
                      3 if r.get("is_sympathy") else 0,
            axis=1
        )
    else:
        out["sympathy_score"] = 0

    # Total
    out["score"] = (
        out["news_pts"]      +
        out["gap_score"]     +
        out["rvol_score"]    +
        out["float_score"]   +
        out["dvol_score"]    +
        out["sympathy_score"]
    ).round(1).clip(0, 100)

    out["grade"] = out["score"].apply(get_grade)

    out.sort_values("score", ascending=False, inplace=True)
    out.reset_index(drop=True, inplace=True)

    if len(out) > 0:
        top = out.iloc[0]
        print(f"[Scoring] Top: {top['ticker']} "
              f"score={top['score']:.1f} grade={top['grade']}")
    return out
