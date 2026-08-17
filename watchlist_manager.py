"""
Watchlist Manager - SQLite based watchlist for DAYS-BOT (V2 Updated)
"""
import sqlite3
from datetime import datetime
from typing import Dict, Any, List

DB_PATH = "watchlist.db"

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
                last_seen TEXT,
                status TEXT DEFAULT 'WATCH',
                hits INTEGER DEFAULT 1,
                stop_price REAL,
                tp1 REAL,
                tp2 REAL,
                rr1 REAL,
                rr2 REAL,
                dvol REAL,
                vwap REAL
            )
        """)
        
        # ====== V2: הוסף שדות חדשים אם חסרים ======
        columns = [row[1] for row in conn.execute("PRAGMA table_info(watchlist)")]
        new_fields = {
            "rvol_score": "REAL",
            "float_turnover": "REAL",
            "float_turnover_score": "REAL",
            "float_score": "REAL",
            "gap_score": "REAL",
            "liquidity_score": "REAL",
            "catalyst_score": "REAL",
            "event_score": "REAL",
            "setup_grade": "TEXT",
            "dilution_risk": "TEXT",
            "risk_score": "REAL",
            "red_flags": "TEXT",
            "float_shares": "REAL",
            "spread_pct": "REAL",
            "catalyst_type": "TEXT",
        }
        for field, dtype in new_fields.items():
            if field not in columns:
                conn.execute(f"ALTER TABLE watchlist ADD COLUMN {field} {dtype}")
                
        conn.commit()
        conn.close()

    def _determine_status(self, candidate: Dict[str, Any]) -> str:
        score = candidate.get('score', 0)
        rvol = candidate.get('rvol', 0)
        if score >= 70 and rvol >= 10:
            return 'READY'
        elif score >= 50:
            return 'PREPARE'
        return 'WATCH'

    def add_to_watchlist(self, candidate: Dict[str, Any]):
        ticker = candidate['ticker']
        pm_high = candidate.get('pm_high', candidate['price'] * 1.02)
        trigger_price = round(pm_high * 1.005, 2)
        
        # V2 fields
        stop_price = round(candidate['price'] * 0.95, 2)
        tp1 = round(candidate['price'] * 1.06, 2)
        tp2 = round(candidate['price'] * 1.12, 2)
        rr1 = round((tp1 - candidate['price']) / (candidate['price'] - stop_price), 2) if (candidate['price'] - stop_price) > 0 else 0
        rr2 = round((tp2 - candidate['price']) / (candidate['price'] - stop_price), 2) if (candidate['price'] - stop_price) > 0 else 0
        
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
                    pm_high = ?, trigger_price = ?, catalyst = ?,
                    hits = hits + 1, last_seen = ?, status = ?,
                    stop_price = ?, tp1 = ?, tp2 = ?, rr1 = ?, rr2 = ?,
                    dvol = ?, vwap = ?,
                    rvol_score = ?, float_turnover = ?, float_turnover_score = ?,
                    float_score = ?, gap_score = ?, liquidity_score = ?,
                    catalyst_score = ?, event_score = ?, setup_grade = ?,
                    dilution_risk = ?, risk_score = ?, red_flags = ?,
                    float_shares = ?, spread_pct = ?, catalyst_type = ?
                WHERE id = ?
            """, (
                candidate['price'], candidate['gap_pct'], candidate.get('score', 0), candidate.get('rvol', 0),
                pm_high, trigger_price, candidate.get('catalyst', ''),
                datetime.now().isoformat(), self._determine_status(candidate),
                stop_price, tp1, tp2, rr1, rr2,
                candidate.get('dollar_volume', 0), candidate.get('vwap_est', 0),
                candidate.get('rvol_score', 0),
                candidate.get('float_turnover'),
                candidate.get('float_turnover_score', 0),
                candidate.get('float_score', 0),
                candidate.get('gap_score', 0),
                candidate.get('liquidity_score', 0),
                candidate.get('catalyst_score', 0),
                candidate.get('event_score', 0),
                candidate.get('setup_grade', 'UNKNOWN'),
                candidate.get('dilution_risk', 'UNKNOWN'),
                candidate.get('risk_score', 0),
                ",".join(candidate.get('red_flags', [])),
                candidate.get('float_shares', 0),
                candidate.get('spread_pct', 0),
                candidate.get('catalyst_type', 'UNKNOWN'),
                row[0]
            ))
        else:
            conn.execute("""
                INSERT INTO watchlist (
                    ticker, price, gap_pct, score, rvol,
                    pm_high, trigger_price, catalyst,
                    added_time, last_seen, status, hits,
                    stop_price, tp1, tp2, rr1, rr2, dvol, vwap,
                    rvol_score, float_turnover, float_turnover_score,
                    float_score, gap_score, liquidity_score,
                    catalyst_score, event_score, setup_grade,
                    dilution_risk, risk_score, red_flags,
                    float_shares, spread_pct, catalyst_type
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                ticker, candidate['price'], candidate['gap_pct'], candidate.get('score', 0), candidate.get('rvol', 0),
                pm_high, trigger_price, candidate.get('catalyst', ''),
                datetime.now().isoformat(), datetime.now().isoformat(),
                self._determine_status(candidate), 1,
                stop_price, tp1, tp2, rr1, rr2,
                candidate.get('dollar_volume', 0), candidate.get('vwap_est', 0),
                candidate.get('rvol_score', 0),
                candidate.get('float_turnover'),
                candidate.get('float_turnover_score', 0),
                candidate.get('float_score', 0),
                candidate.get('gap_score', 0),
                candidate.get('liquidity_score', 0),
                candidate.get('catalyst_score', 0),
                candidate.get('event_score', 0),
                candidate.get('setup_grade', 'UNKNOWN'),
                candidate.get('dilution_risk', 'UNKNOWN'),
                candidate.get('risk_score', 0),
                ",".join(candidate.get('red_flags', [])),
                candidate.get('float_shares', 0),
                candidate.get('spread_pct', 0),
                candidate.get('catalyst_type', 'UNKNOWN')
            ))
        conn.commit()
        conn.close()
        print(f"[Watchlist] ✅ {ticker} added/updated (Trigger: ${trigger_price:.2f})")

    def get_watchlist(self) -> List[Dict[str, Any]]:
        conn = sqlite3.connect(DB_PATH)
        conn.row_factory = sqlite3.Row
        cursor = conn.execute("SELECT * FROM watchlist WHERE status != 'EXECUTED' ORDER BY score DESC")
        rows = [dict(row) for row in cursor.fetchall()]
        conn.close()
        return rows
