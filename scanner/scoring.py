import pandas as pd
import numpy as np


def _norm(series: pd.Series, lo: float, hi: float) -> pd.Series:
    clipped = series.clip(lo, hi)
    return (clipped - lo) / (hi - lo) if hi > lo else pd.Series(0.0, index=series.index)


def score_candidates(df: pd.DataFrame) -> pd.DataFrame:
    if df.empty:
        return df

    out = df.copy()

    out["vol_score"]      = (_norm(out["vol_ratio"], 1, 10) * 30).round(1)
    out["gap_score"]      = (_norm(out["gap_pct"], 5, 30) * 20).round(1)
    out["sector_score"]   = np.where(
        out["is_leader"], 20,
        np.where(out["is_sympathy"], 14, 0)
    )

    def price_pts(p):
        if 2 <= p <= 10:  return 10
        elif 10 < p <= 15: return 6
        elif 1 <= p < 2:   return 4
        return 2

    out["price_score"]    = out["price"].apply(price_pts)
    momentum_raw          = np.log1p(out["gap_pct"] * out["vol_ratio"])
    out["momentum_score"] = (_norm(momentum_raw, 0, np.log1p(30 * 15)) * 20).round(1)
    out["score"]          = (
        out["vol_score"] + out["gap_score"] + out["sector_score"] +
        out["price_score"] + out["momentum_score"]
    ).round(1)

    out.sort_values("score", ascending=False, inplace=True)
    out.reset_index(drop=True, inplace=True)
    print(f"[Scoring] Top score: {out['score'].iloc[0]:.1f} ({out['ticker'].iloc[0]})")
    return out
