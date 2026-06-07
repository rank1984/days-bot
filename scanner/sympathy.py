import pandas as pd


def tag_sympathy(candidates: pd.DataFrame) -> pd.DataFrame:
    if candidates.empty:
        return candidates

    df = candidates.copy()
    df["is_leader"]   = False
    df["is_sympathy"] = False
    df["leader"]      = ""
    df["reason"]      = "Momentum Play"

    if "sector" not in df.columns or df["sector"].nunique() == 0:
        return df

    sector_leaders = (
        df.loc[df.groupby("sector")["gap_pct"].idxmax()]
        [["sector", "ticker", "gap_pct"]]
        .rename(columns={"ticker": "leader_ticker", "gap_pct": "leader_gap"})
    )

    df = df.merge(sector_leaders, on="sector", how="left")

    for idx, row in df.iterrows():
        if row["ticker"] == row.get("leader_ticker"):
            df.at[idx, "is_leader"] = True
            df.at[idx, "reason"]    = f"Sector Leader ({row['sector']})"
        elif row.get("leader_gap", 0) >= row["gap_pct"] * 1.5:
            df.at[idx, "is_sympathy"] = True
            df.at[idx, "leader"]      = row.get("leader_ticker", "")
            df.at[idx, "reason"]      = (
                f"Sympathy → {row.get('leader_ticker','')} +{row.get('leader_gap',0):.1f}%"
            )

    df.drop(columns=["leader_ticker", "leader_gap"], errors="ignore", inplace=True)
    print(f"[Sympathy] Leaders: {df['is_leader'].sum()} | Sympathy: {df['is_sympathy'].sum()}")
    return df
