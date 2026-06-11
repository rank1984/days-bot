"""
scoring.py V4
--------------
News Catalyst    30
Gap %            20  (ענישה על >150%, לא hard filter)
RVOL             20
Float            20
Dollar Volume    10
PM Volume Bonus   5
PM High Bonus     7  (בונוס + ענישה)
Sector Sympathy   5
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

    # News Catalyst (30)
    if "news_score" in out.columns:
        out["news_pts"] = out["news_score"].apply(
            lambda s: 30 if s >= 30 else
                      25 if s >= 25 else
                      20 if s >= 20 else
                      15 if s >= 15 else
                      10 if s >= 10 else
                       5 if s >= 5  else
                       0 if s < 0   else 3
        )
    else:
        out["news_pts"] = 3

    # Gap Score (20) — soft penalty, לא hard filter
    def gap_pts(g):
        base = float(_norm(pd.Series([g]), 10, 80).iloc[0]) * 20
        if g > 250:   base -= 10  # כבר התפוצץ
        elif g > 150: base -= 5   # חשוד
        return round(max(base, 0), 1)
    out["gap_score"] = out["gap_pct"].apply(gap_pts)

    # RVOL (20)
    rvol_col = "pm_rvol" if "pm_rvol" in out.columns else "vol_ratio"
    rvol_vals = out[rvol_col]

    if rvol_vals.nunique() <= 1:
        print(f"[Scoring] WARNING: RVOL bug — all values = {rvol_vals.iloc[0]}")
        out["rvol_score"] = 5
    else:
        def rvol_pts(r):
            if r >= 5:  return 20
            if r >= 3:  return 17
            if r >= 2:  return 13
            if r >= 1:  return 7
            return 2
        out["rvol_score"] = rvol_vals.apply(rvol_pts)

    # Float (20)
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
        out["dvol_score"] = (
            _norm(out["dollar_volume"], 1_000_000, 10_000_000) * 10
        ).round(1)
    else:
        out["dvol_score"] = 0

    # PM Volume Bonus (5)
    def pm_vol_bonus(v):
        if v > 5_000_000: return 5
        if v > 2_000_000: return 3
        if v > 1_000_000: return 2
        return 0
    out["pm_vol_bonus"] = out["pm_volume"].apply(pm_vol_bonus) \
                          if "pm_volume" in out.columns else 0

    # PM High Bonus/Penalty (7)
    # קרוב לשיא = חזק, רחוק = קרס
    def pmhigh_pts(dist):
        if dist < 0:    return 0   # מעל השיא — לא ייתכן
        if dist <= 2:   return 7   # קרוב מאוד לפריצה
        if dist <= 5:   return 5
        if dist <= 10:  return 2
        if dist > 25:   return -5  # קרס מהשיא
        return 0
    out["pmhigh_score"] = out["pm_high_dist"].apply(pmhigh_pts) \
                          if "pm_high_dist" in out.columns else 0

    # Sector Sympathy (5)
    if "is_leader" in out.columns:
        out["sympathy_score"] = out.apply(
            lambda r: 5 if r.get("is_leader") else
                      3 if r.get("is_sympathy") else 0, axis=1
        )
    else:
        out["sympathy_score"] = 0

    # Total
    out["score"] = (
        out["news_pts"]       +
        out["gap_score"]      +
        out["rvol_score"]     +
        out["float_score"]    +
        out["dvol_score"]     +
        out["pm_vol_bonus"]   +
        out["pmhigh_score"]   +
        out["sympathy_score"]
    ).round(1).clip(0, 100)

    out["grade"] = out["score"].apply(get_grade)

    out.sort_values("score", ascending=False, inplace=True)
    out.reset_index(drop=True, inplace=True)

    if len(out) > 0:
        top = out.iloc[0]
        print(
            f"[Scoring] Top: {top['ticker']} "
            f"score={top['score']:.1f} grade={top['grade']} "
            f"gap={top['gap_pct']:.1f}%"
        )
    return out
