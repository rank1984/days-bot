"""
Watchlist Manager – stores candidates across runs, tracks triggers
"""
import sqlite3
import os
from datetime import datetime
from typing import Dict, List, Any

from database.db import DB_PATH

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
                trigger_price REAL,
                catalyst TEXT,
                added_time TEXT,
                status TEXT DEFAULT 'WATCH',
                hits INTEGER DEFAULT 1,
                last_seen TEXT
            )
        """)
        conn.commit()
        conn.close()
    
    def add_to_watchlist(self, candidate: Dict[str, Any]):
        ticker = candidate['ticker']
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
                    price = ?,
                    gap_pct = ?,
                    score = ?,
                    rvol = ?,
                    pm_high = ?,
                    trigger_price = ?,
                    catalyst = ?,
                    hits = hits + 1,
                    last_seen = ?,
                    status = ?
                WHERE id = ?
            """, (
                candidate['price'],
                candidate['gap_pct'],
                candidate.get('score', 0),
                candidate.get('rvol', 0),
                candidate.get('pm_high', candidate['price'] * 1.02),
                candidate.get('trigger_price', candidate['price'] * 1.01),
                candidate.get('catalyst', ''),
                datetime.now().isoformat(),
                self._determine_status(candidate),
                row[0]
            ))
        else:
            conn.execute("""
                INSERT INTO watchlist (
                    ticker, price, gap_pct, score, rvol,
                    pm_high, trigger_price, catalyst,
                    added_time, last_seen, status, hits
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                ticker,
                candidate['price'],
                candidate['gap_pct'],
                candidate.get('score', 0),
                candidate.get('rvol', 0),
                candidate.get('pm_high', candidate['price'] * 1.02),
                candidate.get('trigger_price', candidate['price'] * 1.01),
                candidate.get('catalyst', ''),
                datetime.now().isoformat(),
                datetime.now().isoformat(),
                self._determine_status(candidate),
                1
            ))
        
        conn.commit()
        conn.close()
    
    def _determine_status(self, candidate: Dict) -> str:
        price = candidate['price']
        trigger = candidate.get('trigger_price', price * 1.01)
        pm_high = candidate.get('pm_high', price * 1.02)
        rvol = candidate.get('rvol', 1.0)
        
        if price >= trigger and rvol >= 1.5:
            return 'READY'
        elif price >= pm_high * 0.97 and rvol >= 1.2:
            return 'PREPARE'
        else:
            return 'WATCH'
    
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
