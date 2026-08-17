"""
Watchlist Manager – stores candidates, tracks triggers and breakout prices
"""
sqlite3_import_ok = True
try:
    import sqlite3
    import os
    from datetime import datetime
    from typing import Dict, List, Any
    from zoneinfo import ZoneInfo
    from database.db import DB_PATH
except ImportError:
    sqlite3_import_ok = False

ET = ZoneInfo("America/New_York") if 'ZoneInfo' in globals() else None

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
                last_seen TEXT,
                ready_price REAL,
                ready_time TEXT,
                stop_price REAL,
                tp1 REAL,
                tp2 REAL,
                rr1 REAL,
                rr2 REAL,
                dvol REAL,
                vwap REAL
            )
        """)
        # הוסף שדות חדשים אם חסרים
        columns = [row[1] for row in conn.execute("PRAGMA table_info(watchlist)")]
        new_fields = {
            'rvol_score': 'REAL',
            'float_turnover': 'REAL',
            'float_turnover_score': 'REAL',
            'float_score': 'REAL',
            'gap_score': 'REAL',
            'liquidity_score': 'REAL',
            'catalyst_score': 'REAL',
            'event_score': 'REAL',
            'setup_grade': 'TEXT',
            'dilution_risk': 'TEXT',
            'risk_score': 'REAL',
            'red_flags': 'TEXT',
            'float_shares': 'REAL',
            'spread_pct': 'REAL'
        }
        for field, dtype in new_fields.items():
            if field not in columns:
                conn.execute(f"ALTER TABLE watchlist ADD COLUMN {field} {dtype}")
        conn.commit()
        conn.close()
    
    def _determine_status(self, candidate: Dict) -> str:
        price = candidate['price']
        pm_high = candidate.get('pm_high', price * 1.02)
        rvol = candidate.get('rvol', 1.0)
        trigger_price = round(pm_high * 1.005, 2)
        if price >= trigger_price and rvol >= 1.5:
            return 'READY'
        elif price >= pm_high * 0.97 and rvol >= 1.2:
            return 'PREPARE'
        else:
            return 'WATCH'
    
    def add_to_watchlist(self, candidate: Dict[str, Any]):
        ticker = candidate['ticker']
        pm_high = candidate.get('pm_high', candidate['price'] * 1.02)
        trigger_price = round(pm_high * 1.005, 2)
        
        stop_price = round(candidate['price'] * 0.95, 2)
        tp1 = round(candidate['price'] * 1.06, 2)
        tp2 = round(candidate['price'] * 1.12, 2)
        rr1 = round((tp1 - candidate['price']) / (candidate['price'] - stop_price), 2) if (candidate['price'] - stop_price) > 0 else 0
        rr2 = round((tp2 - candidate['price']) / (candidate['price'] - stop_price), 2) if (candidate['price'] - stop_price) > 0 else 0
        dvol = candidate.get('dollar_volume', 0)
        vwap = candidate.get('vwap_est', 0)

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
                    float_score = ?, gap_score = ?, liquidity_score = ?, catalyst_score = ?,
                    event_score = ?, setup_grade = ?, dilution_risk = ?, risk_score = ?,
                    red_flags = ?, float_shares = ?, spread_pct = ?
                WHERE id = ?
            """, (
                candidate.get('price'), candidate.get('gap_pct'), candidate.get('score', 0), candidate.get('rvol', 0),
                pm_high, trigger_price, candidate.get('catalyst', ''),
                datetime.now().isoformat(), self._determine_status(candidate),
                stop_price, tp1, tp2, rr1, rr2, dvol, vwap,
                candidate.get('rvol_score'), candidate.get('float_turnover'), candidate.get('float_turnover_score'),
                candidate.get('float_score'), candidate.get('gap_score'), candidate.get('liquidity_score'), candidate.get('catalyst_score'),
                candidate.get('event_score'), candidate.get('setup_grade'), candidate.get('dilution_risk'), candidate.get('risk_score'),
                candidate.get('red_flags'), candidate.get('float_shares'), candidate.get('spread_pct'),
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
                    float_score, gap_score, liquidity_score, catalyst_score,
                    event_score, setup_grade, dilution_risk, risk_score,
                    red_flags, float_shares, spread_pct
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                ticker, candidate.get('price'), candidate.get('gap_pct'), candidate.get('score', 0), candidate.get('rvol', 0),
                pm_high, trigger_price, candidate.get('catalyst', ''),
                datetime.now().isoformat(), datetime.now().isoformat(),
                self._determine_status(candidate), 1,
                stop_price, tp1, tp2, rr1, rr2, dvol, vwap,
                candidate.get('rvol_score'), candidate.get('float_turnover'), candidate.get('float_turnover_score'),
                candidate.get('float_score'), candidate.get('gap_score'), candidate.get('liquidity_score'), candidate.get('catalyst_score'),
                candidate.get('event_score'), candidate.get('setup_grade'), candidate.get('dilution_risk'), candidate.get('risk_score'),
                candidate.get('red_flags'), candidate.get('float_shares'), candidate.get('spread_pct')
            ))
        conn.commit()
        conn.close()
        print(f"[Watchlist] ✅ {ticker} added/updated (Trigger: ${trigger_price:.2f})")
    
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
    
    def mark_ready(self, ticker: str, breakout_price: float):
        conn = sqlite3.connect(DB_PATH)
        conn.execute("""
            UPDATE watchlist
            SET status = 'READY',
                ready_price = ?,
                ready_time = ?
            WHERE ticker = ? AND status != 'EXECUTED'
        """, (breakout_price, datetime.now(ET).isoformat() if ET else datetime.now().isoformat(), ticker))
        conn.commit()
        conn.close()
