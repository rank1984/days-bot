"""
Watchlist Manager – V2.11 (FIXED: Stop/TP from trigger_price, filter by last_seen)
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
        trigger_price = round(pm_high * 1.005, 2)
        if price >= trigger_price:
            return 'PREPARE'
        else:
            return 'WATCH'
    
    def add_to_watchlist(self, candidate: Dict[str, Any]):
        ticker = candidate.get('ticker', '???')
        price = float(candidate.get('price', 0))
        gap = float(candidate.get('gap_pct', 0))
        rvol = candidate.get('rvol')
        pm_high = float(candidate.get('pm_high', price * 1.02))
        pm_high_dist = float(candidate.get('pm_high_dist', 999.0))
        vwap = float(candidate.get('pm_vwap', price))
        spread_pct = candidate.get('spread_pct')
        catalyst = candidate.get('catalyst')
        catalyst_score = float(candidate.get('catalyst_score', 0))
        event_score = float(candidate.get('event_score', 0))
        grade = candidate.get('grade', '?')
        state = candidate.get('state', 'WATCH')
        rvol_method = candidate.get('rvol_method', 'N/A')

        # ====== FIX #6: Stop/TP from trigger_price (Entry) ======
        trigger_price = round(pm_high * 1.005, 2)
        entry = trigger_price if trigger_price > price else price  # Entry = trigger (breakout) or current if above

        stop_price = round(entry * 0.95, 2)
        tp1 = round(entry * 1.06, 2)
        tp2 = round(entry * 1.12, 2)
        rr1 = round((tp1 - entry) / (entry - stop_price), 2) if (entry - stop_price) > 0 else 0
        rr2 = round((tp2 - entry) / (entry - stop_price), 2) if (entry - stop_price) > 0 else 0

        dvol = price * candidate.get('pm_volume', 0)

        conn = sqlite3.connect(DB_PATH)
        cursor = conn.execute("""
            SELECT id, hits, status FROM watchlist
            WHERE ticker = ? AND status != 'EXECUTED'
            ORDER BY added_time DESC LIMIT 1
        """, (ticker,))
        row = cursor.fetchone()

        now_str = datetime.now().isoformat()

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
                catalyst, now_str,
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
                now_str, now_str,
                self._determine_status(candidate), 1,
                stop_price, tp1, tp2, rr1, rr2, dvol, vwap,
                spread_pct, event_score, grade, state,
                catalyst_score, rvol_method
            ))
        conn.commit()
        conn.close()

        print(f"[Watchlist] ✅ {ticker} added")
        print(f"  price={price:.2f} | gap={gap:.1f}% | rvol={rvol if rvol is not None else 'N/A'} | spread={spread_pct if spread_pct is not None else 'N/A'}")
        print(f"  entry={entry:.2f} | stop={stop_price:.2f} | tp1={tp1:.2f} | tp2={tp2:.2f}")
        if catalyst:
            print(f"  catalyst={catalyst[:50]}")
        else:
            print(f"  catalyst=N/A")
    
    # ====== FIX #7: Filter by last_seen (not added_time) ======
    def get_active_watchlist(self) -> List[Dict]:
        conn = sqlite3.connect(DB_PATH)
        conn.row_factory = sqlite3.Row
        cursor = conn.execute("""
            SELECT * FROM watchlist
            WHERE status != 'EXECUTED'
            AND last_seen > datetime('now', '-1 day')
            ORDER BY score DESC, hits DESC
            LIMIT 20
        """)
        rows = cursor.fetchall()
        conn.close()
        return [dict(row) for row in rows]
    
    def mark_ready(self, ticker: str, breakout_price: float):
        conn = sqlite3.connect(DB_PATH)
        conn.execute("""
            UPDATE watchlist
            SET status = 'READY',
                ready_price = ?,
                ready_time = ?
            WHERE ticker = ? AND status != 'EXECUTED'
        """, (breakout_price, datetime.now(ET).isoformat(), ticker))
        conn.commit()
        conn.close()
