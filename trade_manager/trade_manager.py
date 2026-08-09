"""
Trade Manager – with Trigger, Status, and dynamic scoring
"""
import sys, os, json
from pathlib import Path
from datetime import datetime, timedelta
from typing import Dict, Any, Optional

BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))
sys.path.insert(0, str(BASE_DIR / "utils"))

from utils.config import *
from scanner.universe import load_universe
import yfinance as yf

STOP_LOSS_PCT = 0.05
TAKE_PROFIT_PCT = 0.06
RUNNER_PROFIT_PCT = 0.10

class TradeManager:
    def __init__(self):
        self.cooldown_data = {}
    
    def check_entry_trigger(self, candidate: Dict) -> Dict:
        """
        בודק תנאי כניסה ומחזיר סטטוס:
        - BUY NOW:  מחיר מעל Trigger + RVOL > 2 + מעל VWAP
        - PREPARE:  מחיר קרוב ל-Trigger (95%+) + RVOL > 1.5
        - WATCH:    מחיר רחוק מ-Trigger
        - SKIP:     תנאים לא מתקיימים
        """
        price = candidate.get('price', 0)
        trigger = candidate.get('trigger_price', price * 1.02)
        rvol = candidate.get('rvol', 1.0)
        
        # 1. Trigger
        if price >= trigger:
            trigger_status = "BUY NOW"
        elif price >= trigger * 0.97:
            trigger_status = "PREPARE"
        else:
            trigger_status = "WATCH"
        
        # 2. RVOL
        if rvol < 1.5:
            trigger_status = "SKIP" if trigger_status == "BUY NOW" else "WATCH"
        
        # 3. VWAP (אם יש)
        vwap = candidate.get('vwap_est', 0)
        if vwap > 0 and price < vwap:
            trigger_status = "SKIP" if trigger_status == "BUY NOW" else trigger_status
        
        return {
            'status': trigger_status,
            'trigger': trigger,
            'current': price,
            'distance': ((trigger - price) / price) * 100,
            'rvol': rvol,
            'vwap': vwap,
            'price_above_vwap': price > vwap if vwap > 0 else True,
        }
    
    def generate_plan(self, candidate: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        symbol = candidate.get('ticker', 'UNKNOWN')
        raw_price = float(candidate.get('price', 0.0))
        
        # עיגול
        entry_price = round(raw_price, 2)
        stop_price = round(entry_price * (1.0 - STOP_LOSS_PCT), 2)
        tp1_price = round(entry_price * (1.0 + TAKE_PROFIT_PCT), 2)
        tp2_price = round(entry_price * (1.0 + RUNNER_PROFIT_PCT), 2)
        
        # Trigger
        trigger_info = self.check_entry_trigger(candidate)
        
        # חישוב RR
        risk_per_share = max(0.01, entry_price - stop_price)
        rr1 = round((tp1_price - entry_price) / risk_per_share, 2)
        
        if rr1 < 1.0:
            print(f"[TradeManager] ⛔ {symbol} - RR1 ({rr1:.2f}) < 1.0")
            return None
        
        # Score – רק אם Trigger == BUY NOW
        if trigger_info['status'] != "BUY NOW":
            print(f"[TradeManager] ⏳ {symbol} - Status: {trigger_info['status']}. Waiting for trigger.")
            return None
        
        plan = {
            'ticker': symbol,
            'entry': entry_price,
            'stop': stop_price,
            'tp1': tp1_price,
            'tp2': tp2_price,
            'rr1': rr1,
            'rr2': round((tp2_price - entry_price) / risk_per_share, 2),
            'quality_score': candidate.get('score', 50),
            'status': trigger_info['status'],
            'trigger': trigger_info['trigger'],
            'trigger_distance': trigger_info['distance'],
            'rvol': candidate.get('rvol', 0),
            'gap': candidate.get('gap_pct', 0),
            'dvol': candidate.get('dollar_volume', 0),
            'catalyst': candidate.get('catalyst', '—'),
            'raw_data': candidate
        }
        return plan
