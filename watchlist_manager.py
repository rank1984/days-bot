"""
Watchlist Manager – V2.8.1 (קריאה נכונה של Candidate Contract)
"""
import sqlite3
import os
from datetime import datetime
from typing import Dict, List, Any
from zoneinfo import ZoneInfo

from database.db import DB_PATH

ET = ZoneInfo("America/New_York")

class WatchlistManager:
    def __init__(self):
        self._ensure_table()
    
    def _ensure_table(self):
        conn = sqlite3.connect(DB_PATH)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS watchlist (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                ticker TEXT NOT NULL,
                price REAL,
                gap_pct REAL,
                score REAL,
                rvol REAL,
                pm_high REAL,
                pm_high_dist REAL,
                trigger_price REAL,
                catalyst TEXT,
                added_time TEXT,
                status TEXT DEFAULT 'WATCH',
                hits INTEGER DEFAULT 1,
                last_seen TEXT,
                ready_price REAL,
                ready_time TEXT,
                stop_price REAL,
                tp1 REAL,
                tp2 REAL,
                rr1 REAL,
                rr2 REAL,
                dvol REAL,
                vwap REAL,
                spread_pct REAL,
                event_score REAL,
                grade TEXT,
                state TEXT,
                catalyst_score REAL,
                rvol_method TEXT
            )
        """)
        conn.commit()
        conn.close()
    
    def _determine_status(self, candidate: Dict) -> str:
        price = candidate['price']
        pm_high = candidate.get('pm_high', price * 1.02)
        rvol = candidate.get('rvol', 1.0)
        trigger_price = round(pm_high * 1.005, 2)
        if price >= trigger_price and rvol >= 1.5:
            return 'QUALIFIED'
        elif price >= pm_high * 0.97 and rvol >= 1.2:
            return 'PREPARE'
        else:
            return 'WATCH'
    
    def add_to_watchlist(self, candidate: Dict[str, Any]):
        # ====== Read from Contract (אחיד!) ======
        ticker = candidate.get('ticker', '???')
        price = float(candidate.get('price', 0))
        gap = float(candidate.get('gap_pct', 0))
        rvol = float(candidate.get('rvol', 0))
        pm_high = float(candidate.get('pm_high', price * 1.02))
        pm_high_dist = float(candidate.get('pm_high_dist', 999.0))
        vwap = float(candidate.get('pm_vwap', price))
        spread_pct = candidate.get('spread_pct')  # may be None
        catalyst = candidate.get('catalyst', '—')
        catalyst_score = float(candidate.get('catalyst_score', 0))
        event_score = float(candidate.get('event_score', 0))
        grade = candidate.get('grade', '?')
        state = candidate.get('state', 'WATCH')
        rvol_method = candidate.get('rvol_method', 'ESTIMATED')

        trigger_price = round(pm_high * 1.005, 2)
        stop_price = round(price * 0.95, 2)
        tp1 = round(price * 1.06, 2)
        tp2 = round(price * 1.12, 2)
        rr1 = round((tp1 - price) / (price - stop_price), 2) if (price - stop_price) > 0 else 0
        rr2 = round((tp2 - price) / (price - stop_price), 2) if (price - stop_price) > 0 else 0
        dvol = price * candidate.get('pm_volume', 0)

        conn = sqlite3.connect(DB_PATH)
        cursor = conn.execute("""
            SELECT id, hits, status FROM watchlist
            WHERE ticker = ? AND status != 'EXECUTED'
            ORDER BY added_time DESC LIMIT 1
        """, (ticker,))
        row = cursor.fetchone()

        if row:
            conn.execute("""
                UPDATE watchlist SET
                    price = ?, gap_pct = ?, score = ?, rvol = ?,
                    pm_high = ?, pm_high_dist = ?, trigger_price = ?,
                    catalyst = ?, hits = hits + 1, last_seen = ?,
                    status = ?, stop_price = ?, tp1 = ?, tp2 = ?,
                    rr1 = ?, rr2 = ?, dvol = ?, vwap = ?,
                    spread_pct = ?, event_score = ?, grade = ?,
                    state = ?, catalyst_score = ?, rvol_method = ?
                WHERE id = ?
            """, (
                price, gap, event_score, rvol,
                pm_high, pm_high_dist, trigger_price,
                catalyst, datetime.now().isoformat(),
                self._determine_status(candidate),
                stop_price, tp1, tp2, rr1, rr2,
                dvol, vwap,
                spread_pct, event_score, grade,
                state, catalyst_score, rvol_method,
                row[0]
            ))
        else:
            conn.execute("""
                INSERT INTO watchlist (
                    ticker, price, gap_pct, score, rvol,
                    pm_high, pm_high_dist, trigger_price, catalyst,
                    added_time, last_seen, status, hits,
                    stop_price, tp1, tp2, rr1, rr2, dvol, vwap,
                    spread_pct, event_score, grade, state,
                    catalyst_score, rvol_method
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                ticker, price, gap, event_score, rvol,
                pm_high, pm_high_dist, trigger_price, catalyst,
                datetime.now().isoformat(), datetime.now().isoformat(),
                self._determine_status(candidate), 1,
                stop_price, tp1, tp2, rr1, rr2, dvol, vwap,
                spread_pct, event_score, grade, state,
                catalyst_score, rvol_method
            ))
        conn.commit()
        conn.close()
        print(f"[Watchlist] ✅ {ticker} added/updated (Event Score: {event_score:.1f})")
    
    def get_active_watchlist(self) -> List[Dict]:
        conn = sqlite3.connect(DB_PATH)
        conn.row_factory = sqlite3.Row
        cursor = conn.execute("""
            SELECT * FROM watchlist
            WHERE status != 'EXECUTED'
            AND added_time > datetime('now', '-1 day')
            ORDER BY score DESC, hits DESC
            LIMIT 20
        """)
        rows = cursor.fetchall()
        conn.close()
        return [dict(row) for row in rows]
