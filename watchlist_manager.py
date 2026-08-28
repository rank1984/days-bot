import sqlite3
from database.db import get_connection, init_db


class WatchlistManager:
    def __init__(self):
        init_db()

    def add_to_watchlist(self, candidate: dict):
        conn = get_connection()
        cursor = conn.cursor()

        cursor.execute("""
            INSERT INTO alerts (
                ticker, price, gap_pct, spread_pct,
                pm_volume, pm_bars, pm_high, pm_vwap,
                pm_dist_signed, pm_high_dist, pm_data_quality,
                rvol, rvol_status, catalyst_score, catalyst_status,
                strategy_version, run_mode, event_score
            ) VALUES (
                :ticker, :price, :gap_pct, :spread_pct,
                :pm_volume, :pm_bars, :pm_high, :pm_vwap,
                :pm_dist_signed, :pm_high_dist, :pm_data_quality,
                :rvol, :rvol_status, :catalyst_score, :catalyst_status,
                :strategy_version, :run_mode, :event_score
            )
        """, {
            "ticker": candidate.get("ticker"),
            "price": candidate.get("price"),
            "gap_pct": candidate.get("gap_pct"),
            "spread_pct": candidate.get("spread_pct"),
            "pm_volume": candidate.get("pm_volume"),
            "pm_bars": candidate.get("pm_bars"),
            "pm_high": candidate.get("pm_high"),
            "pm_vwap": candidate.get("pm_vwap"),
            "pm_dist_signed": candidate.get("pm_dist_signed"),
            "pm_high_dist": candidate.get("pm_high_dist"),
            "pm_data_quality": candidate.get("pm_data_quality"),
            "rvol": candidate.get("rvol"),
            "rvol_status": candidate.get("rvol_status", "N/A"),
            "catalyst_score": candidate.get("catalyst_score", 0),
            "catalyst_status": candidate.get("catalyst_status", "N/A"),
            "strategy_version": candidate.get("strategy_version", "V2.14"),
            "run_mode": candidate.get("run_mode", "EXPERIMENT"),
            "event_score": candidate.get("event_score", 0),
        })

        conn.commit()
        conn.close()
