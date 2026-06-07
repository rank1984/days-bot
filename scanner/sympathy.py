import pandas as pd


def tag_sympathy(candidates: pd.DataFrame) -> pd.DataFrame:
    if candidates.empty:
        return candidates

    df = candidates.copy()
    df["is_leader"]   = False
    df["is_sympathy"] = False
    df["leader"]      = ""
    df["reason"]      = "Momentum Play"

    sector_leaders = (
        df.loc[df.groupby("sector")["gap_pct"].idxmax()]
        [["sector", "ticker", "gap_pct"]]
        .rename(columns={"ticker": "leader_ticker", "gap_pct": "leader_gap"})
    )

    df = df.merge(sector_leaders, on="sector", how="left")

    for idx, row in df.iterrows():
        if row["ticker"] == row["leader_ticker"]:
            df.at[idx, "is_leader"] = True
            df.at[idx, "reason"]    = f"Sector Leader ({row['sector']})"
        else:
            if row["leader_gap"] >= row["gap_pct"] * 1.5:
                df.at[idx, "is_sympathy"] = True
                df.at[idx, "leader"]      = row["leader_ticker"]
                df.at[idx, "reason"]      = (
                    f"Sympathy Play → {row['leader_ticker']} +{row['leader_gap']:.1f}%"
                )

    df.drop(columns=["leader_ticker", "leader_gap"], inplace=True)
    print(f"[Sympathy] Leaders: {df['is_leader'].sum()} | Sympathy: {df['is_sympathy'].sum()}")
    return df
