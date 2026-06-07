"""
scoring.py — ציון 0-100 משודרג
--------------------------------
Volume    30  — RVOL אמיתי
Gap       20  — גודל גאפ
Float     15  — float קטן = בונוס גדול  (שדרוג #1)
News      15  — catalyst חיובי          (שדרוג #2)
Price     10  — sweet spot $2-$10
Momentum  10  — gap × dollar_volume
"""

import pandas as pd
import numpy as np


def _norm(series: pd.Series, lo: float, hi: float) -> pd.Series:
    clipped = series.clip(lo, hi)
    return (clipped - lo) / (hi - lo) if hi > lo else pd.Series(0.0, index=series.index)


def score_candidates(df: pd.DataFrame) -> pd.DataFrame:
    if df.empty:
        return df

    out = df.copy()

    # Volume Score (30)
    out["vol_score"] = (_norm(out["vol_ratio"], 1, 15) * 30).round(1)

    # Gap Score (20)
    out["gap_score"] = (_norm(out["gap_pct"], 5, 40) * 20).round(1)

    # שדרוג #1 — Float Score (15)
    # float קטן = ציון גבוה
    # <5M = 15, <10M = 12, <20M = 8, unknown(0) = 5
    def float_pts(f):
        if f == 0:       return 5    # לא ידוע
        if f < 5_000_000:  return 15
        if f < 10_000_000: return 12
        if f < 20_000_000: return 8
        return 3

    out["float_score"] = out["float"].apply(float_pts)

    # שדרוג #2 — News Score (15)
    # news_score מ-scanner/news.py, מנורמל ל-15 נקודות
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

    # Price Score (10)
    def price_pts(p):
        if 2 <= p <= 10:   return 10
        if 10 < p <= 15:   return 6
        if 1 <= p < 2:     return 4
        return 2

    out["price_score"] = out["price"].apply(price_pts)

    # Momentum Score (10) — gap × dollar_volume
    if "dollar_volume" in out.columns:
        momentum_raw = np.log1p(out["gap_pct"] * out["dollar_volume"] / 1_000_000)
        out["momentum_score"] = (_norm(momentum_raw, 0, np.log1p(40 * 10)) * 10).round(1)
    else:
        out["momentum_score"] = 0

    # Total
    out["score"] = (
        out["vol_score"] + out["gap_score"] + out["float_score"] +
        out["news_pts"]  + out["price_score"] + out["momentum_score"]
    ).round(1)

    out.sort_values("score", ascending=False, inplace=True)
    out.reset_index(drop=True, inplace=True)

    if len(out) > 0:
        print(f"[Scoring] Top: {out['ticker'].iloc[0]} score={out['score'].iloc[0]:.1f}")
    return out
