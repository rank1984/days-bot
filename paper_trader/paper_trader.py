"""
Paper Trader Module for DAYS-BOT
מנהל את הביצוע מול ה-API של Alpaca (Paper Trading) עם עיגול מחירים הרמטי (2 ספרות עשרוניות).
"""
import sys
from pathlib import Path
import alpaca_trade_api as tradeapi

BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))
sys.path.insert(0, str(BASE_DIR / "utils"))

from utils.config import ALPACA_API_KEY, ALPACA_SECRET_KEY


class PaperTrader:
    def __init__(self):
        print("[PaperTrader] Initializing Paper Trading...")
        self.api = tradeapi.REST(
            ALPACA_API_KEY,
            ALPACA_SECRET_KEY,
            base_url='https://paper-api.alpaca.markets'
        )

    def get_account(self):
        return self.api.get_account()

    def enter_trade(self, symbol: str, price: float, shares: int = None):
        """
        ביצוע פקודת קנייה ב-Limit Price מעוגל ל-2 ספרות עשרוניות
        """
        price = round(float(price), 2)  # עיגול ל-2 ספרות עשרוניות למניעת Sub-penny error

        if shares is None or shares <= 0:
            try:
                account = self.get_account()
                equity = float(account.equity)
                risk_amount = equity * 0.02  # 2% סיכון מהתיק
                shares = int(risk_amount / price) if price > 0 else 1
            except Exception:
                shares = 1

        shares = max(1, shares)

        try:
            order = self.api.submit_order(
                symbol=symbol,
                qty=shares,
                side='buy',
                type='limit',
                limit_price=price,
                time_in_force='day'
            )
            print(f"[PaperTrade] ENTER {symbol} @ ${price:.2f} x {shares} shares")
            return order
        except Exception as e:
            print(f"[PaperTrade] Error entering trade for {symbol}: {e}")
            return None

    def set_stop_loss(self, symbol: str, stop_price: float):
        """
        הגדרת הוראת Stop Loss מעוגלת
        """
        stop_price = round(float(stop_price), 2)
        print(f"[PaperTrade] Set Stop Loss for {symbol} @ ${stop_price:.2f}")
        # כאן ניתן להרחיב למעקב/פקודה ייעודית ב-Alpaca במידת הצורך

    def set_take_profit(self, symbol: str, target_price: float):
        """
        הגדרת הוראת Take Profit מעוגלת
        """
        target_price = round(float(target_price), 2)
        print(f"[PaperTrade] Set Take Profit for {symbol} @ ${target_price:.2f}")
        # כאן ניתן להרחיב למעקב/פקודה ייעודית ב-Alpaca במידת הצורך
