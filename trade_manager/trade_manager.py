"""
Trade Manager for DAYS-BOT
מנהל המסחר: אחראי על ניהול סיכונים, בדיקת תנאי כניסה, חישוב גודל פוזיציה,
ביצוע פקודות ב-Alpaca, ניהול Cooldown ושליחת עדכונים לטלגרם.
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

# ── הגדרות ניהול סיכונים וכניסה ──────────────────────────
FORCE_ENTRY_FOR_DATA = True       # במצב True: מאשר כניסה מיידית לצורך איסוף נתונים ראשוני
RISK_PER_TRADE_USD = 100.0        # סיכון מקסימלי בעסקה (USD)
DEFAULT_POSITION_SIZE_USD = 1000.0 # תקציב גג לפוזיציה בודדת (USD)
STOP_LOSS_PCT = 0.03              # סטופ לוס: 3%
TAKE_PROFIT_PCT = 0.06            # יעד רווח: 6%

COOLDOWN_FILE = os.path.join(BASE_DIR, "data", "cooldown_history.json")


class TradeManager:
    def __init__(self, api: Optional[tradeapi.REST] = None):
        """
        אתחול חיבור ל-Alpaca במידה ולא נמסר אובייקט API קיים
        """
        if api:
            self.api = api
        else:
            self.api = tradeapi.REST(
                ALPACA_API_KEY,
                ALPACA_SECRET_KEY,
                base_url='https://paper-api.alpaca.markets'
            )
        self.cooldown_data = self._load_cooldown()

    # ── טעינה ושמירה של Cooldown ───────────────────────
    def _load_cooldown(self) -> Dict[str, str]:
        if os.path.exists(COOLDOWN_FILE):
            try:
                with open(COOLDOWN_FILE, 'r') as f:
                    return json.load(f)
            except Exception as e:
                print(f"[TradeManager] Error loading cooldown file: {e}")
                return {}
        return {}

    def _save_cooldown(self) -> None:
        try:
            os.makedirs(os.path.dirname(COOLDOWN_FILE), exist_ok=True)
            with open(COOLDOWN_FILE, 'w') as f:
                json.dump(self.cooldown_data, f, indent=2)
        except Exception as e:
            print(f"[TradeManager] Error saving cooldown file: {e}")

    def is_in_cooldown(self, symbol: str) -> bool:
        """
        בודק אם המניה נמצאת בתקופת צינון (לא נסחרה ב-X השעות האחרונות)
        """
        if not ENABLE_COOLDOWN:
            return False
        
        last_traded_str = self.cooldown_data.get(symbol)
        if not last_traded_str:
            return False

        try:
            last_traded = datetime.fromisoformat(last_traded_str)
            time_diff = datetime.now() - last_traded
            if time_diff < timedelta(hours=COOLDOWN_HOURS):
                hours_left = COOLDOWN_HOURS - (time_diff.total_seconds() / 3600)
                print(f"[Cooldown] {symbol} in cooldown for another {hours_left:.1f} hours.")
                return True
        except Exception:
            pass

        return False

    def register_trade(self, symbol: str) -> None:
        """
        רושם מניה בצינון לאחר ביצוע עסקה
        """
        self.cooldown_data[symbol] = datetime.now().isoformat()
        self._save_cooldown()

    # ── בדיקת טריגר כניסה ─────────────────────────────
    def check_entry_trigger(self, candidate: Dict[str, Any]) -> bool:
        """
        בודק האם המועמדת עומדת בתנאי כניסה לפוזיציה
        """
        symbol = candidate.get('ticker')
        price = candidate.get('price', 0.0)

        if not symbol or price <= 0:
            print(f"[Entry Trigger] {symbol}: Invalid symbol or price (${price}). Rejected.")
            return False

        # בדיקת Cooldown
        if self.is_in_cooldown(symbol):
            return False

        # מצב 1: איסוף נתונים (FORCE ENTRY)
        if FORCE_ENTRY_FOR_DATA:
            print(f"[Entry Trigger] {symbol}: FORCE ENTRY active. Trade Approved at ${price:.2f}")
            return True

        # מצב 2: טריגר דינמי (1% מעל המחיר הנוכחי)
        trigger_price = candidate.get('trigger_price')
        if not trigger_price:
            trigger_price = round(price * 1.01, 2)

        if price >= trigger_price:
            print(f"[Entry Trigger] {symbol}: Current ${price:.2f} >= Trigger ${trigger_price:.2f}. Approved!")
            return True
        else:
            print(f"[Entry Trigger] {symbol}: Current ${price:.2f} < Trigger ${trigger_price:.2f}. Rejected.")
            return False

    # ── חישוב גודל פוזיציה ───────────────────────────
    def calculate_position_size(self, price: float, stop_loss_price: float) -> int:
        """
        מחשב את כמות המניות לקנייה לפי ניהול סיכונים
        """
        if price <= 0:
            return 0

        risk_per_share = abs(price - stop_loss_price)
        if risk_per_share > 0:
            qty_by_risk = int(RISK_PER_TRADE_USD / risk_per_share)
        else:
            qty_by_risk = 0

        qty_by_capital = int(DEFAULT_POSITION_SIZE_USD / price)

        qty = min(qty_by_risk, qty_by_capital) if qty_by_risk > 0 else qty_by_capital
        return max(1, qty)

    # ── שליחת התראות לטלגרם ───────────────────────────
    def send_telegram_notification(self, message: str) -> None:
        if not TELEGRAM_TOKEN or not TELEGRAM_CHAT_ID:
            return
        try:
            url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
            payload = {
                "chat_id": TELEGRAM_CHAT_ID,
                "text": message,
                "parse_mode": "Markdown"
            }
            requests.post(url, json=payload, timeout=5)
        except Exception as e:
            print(f"[Telegram Error] Could not send notification: {e}")

    # ── ביצוע הוראה ב-ALPACA ───────────────────────────
    def execute_trade(self, candidate: Dict[str, Any]) -> bool:
        """
        אחראי על בדיקת התנאים ושגור פקודת קנייה + Bracket (Stop Loss & Take Profit)
        """
        symbol = candidate.get('ticker')
        price = candidate.get('price', 0.0)

        if not self.check_entry_trigger(candidate):
            return False

        # חישוב יעדי סטופ ופרופיט
        stop_loss_price = round(price * (1.0 - STOP_LOSS_PCT), 2)
        take_profit_price = round(price * (1.0 + TAKE_PROFIT_PCT), 2)
        
        qty = self.calculate_position_size(price, stop_loss_price)

        try:
            print(f"[Executing Trade] Buying {qty} shares of {symbol} at ~${price:.2f}")
            print(f"                 SL: ${stop_loss_price:.2f} | TP: ${take_profit_price:.2f}")

            # שליחת פקודת Bracket מסודרת ב-Alpaca
            order = self.api.submit_order(
                symbol=symbol,
                qty=qty,
                side='buy',
                type='market',
                time_in_force='gtc',
                order_class='bracket',
                take_profit={'limit_price': take_profit_price},
                stop_loss={'stop_price': stop_loss_price}
            )

            # רישום בצינון
            self.register_trade(symbol)

            # עדכון בטלגרם
            msg = (
                f"🚀 *עסקה חדשה בוצעה ב-Paper Trading!*\n\n"
                f"📌 *סמל:* `{symbol}`\n"
                f"💰 *מחיר כניסה:* ${price:.2f}\n"
                f"📦 *כמות מניות:* {qty}\n"
                f"🎯 *Take Profit:* ${take_profit_price:.2f} (+{TAKE_PROFIT_PCT*100:.0f}%)\n"
                f"🛑 *Stop Loss:* ${stop_loss_price:.2f} (-{STOP_LOSS_PCT*100:.0f}%)\n"
                f"📊 *ניקוד בסריקה:* {candidate.get('score', 0):.1f}"
            )
            self.send_telegram_notification(msg)

            print(f"[Trade Success] Order ID: {order.id}")
            return True

        except Exception as e:
            print(f"[Trade Execution Failed] {symbol}: {e}")
            return False
