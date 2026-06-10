"""
scoring.py V3
--------------
News Catalyst   30
Gap %           20
RVOL            20
Float           20  (בונוס Low Float)
Dollar Volume   10
Sector Sympathy  5
PM High Bonus    5  (בונוס קרוב לפריצה)
"""

import pandas as pd
import numpy as np


def _norm(series: pd.Series, lo: float, hi: float) -> pd.Series:
    c = series.clip(lo, hi)
    return (c - lo) / (hi - lo) if hi > lo else pd.Series(0.0, index=series.index)


def get_grade(score: float) -> str:
    if score >= 80: return "A+"
    if score >= 65: return "A"
    if score >= 50: return "B"
    return "C"


def score_candidates(df: pd.DataFrame) -> pd.DataFrame:
    if df.empty:
        return df

    out = df.copy()

    # News Catalyst (30) — הכי חשוב
    if "news_score" in out.columns:
        out["news_pts"] = out["news_score"].apply(
            lambda s: 30 if s >= 30 else
                      25 if s >= 25 else
                      20 if s >= 20 else
                      15 if s >= 15 else
                      10 if s >= 10 else
                       5 if s >= 5  else
                       0 if s < 0   else
                       3
        )
    else:
        out["news_pts"] = 3

    # Gap % (20)
    out["gap_score"] = (_norm(out["gap_pct"], 3, 40) * 20).round(1)

    # RVOL (20) — טיירים
    rvol_col = "pm_rvol" if "pm_rvol" in out.columns else "vol_ratio"
    def rvol_pts(r):
        if r >= 3: return 20
        if r >= 2: return 15
        if r >= 1: return 5
        return 0
    out["rvol_score"] = out[rvol_col].apply(rvol_pts)

    # Float (20) — יתרון עצום ל-Low Float
    def float_pts(f):
        if f == 0:              return 5
        if f < 3_000_000:       return 20
        if f < 5_000_000:       return 18
        if f < 10_000_000:      return 15
        if f < 20_000_000:      return 10
        if f < 50_000_000:      return 5
        return 0
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

    # PM High Bonus (+5) — קרוב לפריצה
    out["pmhigh_bonus"] = 0
    if "pm_high_dist" in out.columns:
        out["pmhigh_bonus"] = out["pm_high_dist"].apply(
            lambda x: 5 if abs(x) <= 2 else 0
        )

    # Total
    out["score"] = (
        out["news_pts"]       +
        out["gap_score"]      +
        out["rvol_score"]     +
        out["float_score"]    +
        out["dvol_score"]     +
        out["sympathy_score"] +
        out["pmhigh_bonus"]
    ).round(1).clip(0, 100)

    out["grade"] = out["score"].apply(get_grade)

    out.sort_values("score", ascending=False, inplace=True)
    out.reset_index(drop=True, inplace=True)

    if len(out) > 0:
        top = out.iloc[0]
        print(f"[Scoring] Top: {top['ticker']} "
              f"score={top['score']:.1f} grade={top['grade']}")
    return out
