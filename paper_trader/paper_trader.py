"""
DAYS-BOT Paper Trader – submits and verifies Alpaca paper orders
"""
import sys
import time
from pathlib import Path

import alpaca_trade_api as tradeapi

BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))
sys.path.insert(0, str(BASE_DIR / "utils"))

from utils.config import ALPACA_API_KEY, ALPACA_SECRET_KEY


class PaperTrader:
    def __init__(self):
        print("[PaperTrader] Initializing Paper Trading...")
        if not ALPACA_API_KEY or not ALPACA_SECRET_KEY:
            raise ValueError("[PaperTrader] Missing Alpaca API keys.")
        self.api = tradeapi.REST(
            ALPACA_API_KEY,
            ALPACA_SECRET_KEY,
            base_url="https://paper-api.alpaca.markets"
        )
        print("[PaperTrader] Connected to Alpaca Paper Trading.")

    def get_account(self):
        return self.api.get_account()

    def get_order(self, order_id):
        return self.api.get_order(order_id)

    def enter_trade(self, symbol: str, price: float, shares: int = None,
                    wait_for_fill: bool = True, timeout_seconds: int = 30):
        """
        Submit LIMIT BUY and wait for fill.
        Returns dict with success, order_id, fill_price, filled_qty, status.
        """
        price = round(float(price), 2)
        if price <= 0:
            return {"success": False, "status": "INVALID_PRICE"}

        # Position sizing – 2% of account allocated (not risk-adjusted)
        if shares is None or shares <= 0:
            try:
                account = self.get_account()
                equity = float(account.equity)
                allocation = equity * 0.02
                shares = int(allocation / price)
            except Exception as e:
                print(f"[PaperTrader] Sizing error: {e}")
                shares = 1
        shares = max(1, shares)

        print(f"[PaperTrader] Submitting BUY {symbol} @ ${price:.2f} x {shares}")

        try:
            order = self.api.submit_order(
                symbol=symbol,
                qty=shares,
                side="buy",
                type="limit",
                limit_price=price,
                time_in_force="day"
            )
            print(f"[PaperTrader] Order submitted {order.id} | status={order.status}")
        except Exception as e:
            print(f"[PaperTrader] ❌ Order failed {symbol}: {e}")
            return {"success": False, "status": "SUBMIT_ERROR", "error": str(e)}

        if not wait_for_fill:
            return {
                "success": True,
                "order_id": order.id,
                "symbol": symbol,
                "requested_price": price,
                "fill_price": None,
                "filled_qty": 0,
                "status": str(order.status)
            }

        # Wait for fill
        start = time.time()
        while time.time() - start < timeout_seconds:
            try:
                order = self.api.get_order(order.id)
                status = str(order.status)
                print(f"[PaperTrader] {symbol} order={status}")

                if status == "filled":
                    fill_price = float(order.filled_avg_price)
                    filled_qty = int(float(order.filled_qty))
                    print(f"[PaperTrader] ✅ FILLED {symbol} @ ${fill_price:.2f} x {filled_qty}")
                    return {
                        "success": True,
                        "order_id": order.id,
                        "symbol": symbol,
                        "requested_price": price,
                        "fill_price": fill_price,
                        "filled_qty": filled_qty,
                        "status": "filled"
                    }

                if status in ("canceled", "cancelled", "expired", "rejected"):
                    print(f"[PaperTrader] ❌ Order ended: {status}")
                    return {
                        "success": False,
                        "order_id": order.id,
                        "symbol": symbol,
                        "requested_price": price,
                        "fill_price": None,
                        "filled_qty": 0,
                        "status": status
                    }
            except Exception as e:
                print(f"[PaperTrader] Poll error: {e}")
            time.sleep(2)

        print(f"[PaperTrader] ⏱ Fill timeout {symbol}")
        return {
            "success": False,
            "order_id": order.id,
            "symbol": symbol,
            "requested_price": price,
            "fill_price": None,
            "filled_qty": 0,
            "status": "TIMEOUT"
        }
