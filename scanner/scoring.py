"""
scoring.py — ציון 0-100 + דירוג AI
-------------------------------------
Volume    30  — RVOL אמיתי
Gap       20  — גודל גאפ
Float     15  — float קטן = בונוס גדול
News      15  — catalyst חיובי
Price     10  — sweet spot $2-$10
Momentum  10  — gap × dollar_volume

AI Rating — Claude מנתח כל מניה ונותן: Grade + סיבה קצרה
"""
import os
import time
import requests
import pandas as pd
import numpy as np


ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY", "")


def _norm(series: pd.Series, lo: float, hi: float) -> pd.Series:
    clipped = series.clip(lo, hi)
    return (clipped - lo) / (hi - lo) if hi > lo else pd.Series(0.0, index=series.index)


def get_ai_rating(row: dict) -> tuple[str, str]:
    """
    שולח נתוני מניה ל-Claude ומקבל:
    - grade: A / B / C / D
    - reason: משפט אחד בעברית

    מחזיר ("?", "") אם אין API key או שגיאה.
    """
    if not ANTHROPIC_API_KEY:
        return "?", ""

    ticker       = row.get("ticker", "")
    gap          = row.get("gap_pct", 0)
    rvol         = row.get("vol_ratio", 0)
    price        = row.get("price", 0)
    float_shares = int(row.get("float", 0))
    dollar_vol   = int(row.get("dollar_volume", 0))
    catalyst     = row.get("catalyst", "אין")
    score        = row.get("score", 0)
    sector       = row.get("sector", "לא ידוע")

    float_str = f"{float_shares/1_000_000:.1f}M" if float_shares > 0 else "לא ידוע"
    dvol_str  = f"${dollar_vol/1_000_000:.1f}M" if dollar_vol >= 1_000_000 else f"${dollar_vol:,}"

    prompt = f"""אתה מומחה מסחר יומי (day trading) במניות ארה"ב. נתח את המניה הבאה לפני פתיחת שוק:

מניה: {ticker}
גאפ פתיחה: +{gap:.1f}%
RVOL: {rvol:.1f}x
מחיר: ${price:.2f}
Float: {float_str}
Dollar Volume פרימרקט: {dvol_str}
Catalyst: {catalyst}
סקטור: {sector}
ציון אלגוריתמי: {score:.0f}/100

דרג את ההזדמנות למסחר יומי:
- A = הזדמנות מעולה, כל האינדיקטורים תומכים
- B = הזדמנות טובה עם כמה סימני שאלה
- C = מעניין אבל סיכון גבוה / חסרים נתונים
- D = לא מומלץ למסחר יומי

ענה בפורמט JSON בלבד, ללא טקסט נוסף:
{{"grade": "B", "reason": "RVOL גבוה עם catalyst ברור אבל float גדול מדי"}}"""

    try:
        resp = requests.post(
            "https://api.anthropic.com/v1/messages",
            headers={
                "x-api-key":         ANTHROPIC_API_KEY,
                "anthropic-version": "2023-06-01",
                "content-type":      "application/json",
            },
            json={
                "model":      "claude-haiku-4-5-20251001",
                "max_tokens": 100,
                "messages":   [{"role": "user", "content": prompt}],
            },
            timeout=15,
        )
        resp.raise_for_status()
        text = resp.json()["content"][0]["text"].strip()

        # נקה backticks אם יש
        text = text.replace("```json", "").replace("```", "").strip()

        import json
        data   = json.loads(text)
        grade  = data.get("grade", "?")
        reason = data.get("reason", "")
        return grade, reason

    except Exception as e:
        print(f"[AI] {row.get('ticker','')} error: {e}")
        return "?", ""


def score_candidates(df: pd.DataFrame) -> pd.DataFrame:
    if df.empty:
        return df

    out = df.copy()

    # Volume Score (30)
    out["vol_score"] = (_norm(out["vol_ratio"], 1, 15) * 30).round(1)

    # Gap Score (20)
    out["gap_score"] = (_norm(out["gap_pct"], 5, 40) * 20).round(1)

    # Float Score (15)
    def float_pts(f):
        if f == 0:              return 5
        if f < 5_000_000:       return 15
        if f < 10_000_000:      return 12
        if f < 20_000_000:      return 8
        return 3
    out["float_score"] = out["float"].apply(float_pts)

    # News Score (15)
    if "news_score" in out.columns:
        out["news_pts"] = out["news_score"].apply(
            lambda s: 15 if s >= 30 else
                      12 if s >= 25 else
                      10 if s >= 20 else
                       7 if s >= 10 else
                       0 if s <  0  else 3
        )
    else:
        out["news_pts"] = 3

    # Price Score (10)
    def price_pts(p):
        if 2 <= p <= 10:  return 10
        if 10 < p <= 15:  return 6
        if 1 <= p < 2:    return 4
        return 2
    out["price_score"] = out["price"].apply(price_pts)

    # Momentum Score (10)
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

    # AI Rating — רק על Top 10 כדי לחסוך קריאות API
    print("[Scoring] Getting AI ratings...")
    out["ai_grade"]  = "?"
    out["ai_reason"] = ""

    for idx in out.head(10).index:
        row              = out.loc[idx].to_dict()
        grade, reason    = get_ai_rating(row)
        out.at[idx, "ai_grade"]  = grade
        out.at[idx, "ai_reason"] = reason
        time.sleep(0.3)  # rate limit קטן

    if len(out) > 0:
        top = out.iloc[0]
        print(f"[Scoring] Top: {top['ticker']} score={top['score']:.1f} AI={top['ai_grade']}")

    return out
