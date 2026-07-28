"""
Trade Manager for DAYS-BOT
מחשב תוכניות מסחר, מעגל את כל המחירים ל-2 ספרות עשרוניות
ומאשר כניסות לעסקה.
"""
import sys
import os
import json
import requests
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, Any, Optional
import alpaca_trade_api as tradeapi

BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))
sys.path.insert(0, str(BASE_DIR / "utils"))

from utils.config import (
    ALPACA_API_KEY,
    ALPACA_SECRET_KEY,
    ENABLE_COOLDOWN,
    COOLDOWN_HOURS,
    TELEGRAM_TOKEN,
    TELEGRAM_CHAT_ID,
)

STOP_LOSS_PCT = 0.03   # 3% סטופ לוס
TAKE_PROFIT_PCT = 0.06 # 6% יעד רווח ראשון (TP1)
RUNNER_PROFIT_PCT = 0.10 # 10% יעד רווח שני (TP2)

COOLDOWN_FILE = os.path.join(BASE_DIR, "data", "cooldown_history.json")


class TradeManager:
    def __init__(self, api: Optional[tradeapi.REST] = None):
        if api:
            self.api = api
        else:
            self.api = tradeapi.REST(
                ALPACA_API_KEY,
                ALPACA_SECRET_KEY,
                base_url='https://paper-api.alpaca.markets'
            )
        self.cooldown_data = self._load_cooldown()

    def _load_cooldown(self) -> Dict[str, str]:
        if os.path.exists(COOLDOWN_FILE):
            try:
                with open(COOLDOWN_FILE, 'r') as f:
                    return json.load(f)
            except Exception:
                return {}
        return {}

    def _save_cooldown(self) -> None:
        try:
            os.makedirs(os.path.dirname(COOLDOWN_FILE), exist_ok=True)
            with open(COOLDOWN_FILE, 'w') as f:
                json.dump(self.cooldown_data, f, indent=2)
        except Exception as e:
            print(f"[TradeManager] Error saving cooldown: {e}")

    def is_in_cooldown(self, symbol: str) -> bool:
        if not ENABLE_COOLDOWN:
            return False
        last_traded_str = self.cooldown_data.get(symbol)
        if not last_traded_str:
            return False
        try:
            last_traded = datetime.fromisoformat(last_traded_str)
            if datetime.now() - last_traded < timedelta(hours=COOLDOWN_HOURS):
                return True
        except Exception:
            pass
        return False

    def check_entry_trigger(self, candidate: Dict[str, Any]) -> bool:
        """
        מאשר כניסה מיידית עבור כל המועמדות בשלב איסוף הנתונים
        """
        return True

    def generate_plan(self, candidate: Dict[str, Any]) -> Dict[str, Any]:
        """
        יוצר תוכנית מסחר ומבצע עיגול ל-2 ספרות עשרוניות לכל המחירים
        """
        symbol = candidate.get('ticker') or candidate.get('symbol', 'UNKNOWN')
        raw_price = float(candidate.get('price', 0.0))

        # עיגול המחירים ל-2 ספרות עשרוניות
        entry_price = round(raw_price, 2)
        stop_price = round(entry_price * (1.0 - STOP_LOSS_PCT), 2)
        tp1_price = round(entry_price * (1.0 + TAKE_PROFIT_PCT), 2)
        tp2_price = round(entry_price * (1.0 + RUNNER_PROFIT_PCT), 2)

        # חישוב כמות מניות
        risk_per_share = max(0.01, entry_price - stop_price)
        shares = max(1, int(100.0 / risk_per_share))

        plan = {
            'ticker': symbol,
            'symbol': symbol,
            'entry': entry_price,
            'price': entry_price,
            'stop': stop_price,
            'stop_loss': stop_price,
            'tp1': tp1_price,
            'tp2': tp2_price,
            'take_profit': tp1_price,
            'runner': True,
            'shares': shares,
            'qty': shares,
            'rr1': round((tp1_price - entry_price) / risk_per_share, 2),
            'rr2': round((tp2_price - entry_price) / risk_per_share, 2),
            'quality_score': candidate.get('score', 0.0),
            'raw_data': candidate
        }
        return plan
