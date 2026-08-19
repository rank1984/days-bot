"""
Paper Trader – with REAL Stop Loss and Take Profit (Bracket Orders)
"""
import sys
import time
from pathlib import Path

import alpaca_trade_api as tradeapi

BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))
sys.path.insert(0, str(BASE_DIR / "utils"))

from utils.config import ALPACA_API_KEY, ALPACA_SECRET_KEY
from database.db import save_trade


class PaperTrader:
    def __init__(self):
        print("[PaperTrader] Initializing Paper Trading...")
        if not ALPACA_API_KEY or not ALPACA_SECRET_KEY:
            raise ValueError("[PaperTrader] ❌ Missing Alpaca API keys!")
        self.api = tradeapi.REST(
            ALPACA_API_KEY,
            ALPACA_SECRET_KEY,
            base_url="https://paper-api.alpaca.markets",
            api_version="v2"
        )
        print("[PaperTrader] ✅ Connected to Alpaca Paper Trading.")

    def get_account(self):
        return self.api.get_account()

    def get_order(self, order_id):
        try:
            return self.api.get_order(order_id)
        except Exception as e:
            print(f"[PaperTrader] ❌ Cannot get order {order_id}: {e}")
            return None

    def enter_trade(
        self,
        symbol: str,
        price: float,
        stop_price: float = None,
        tp1: float = None,
        tp2: float = None,
        rr1: float = None,
        rr2: float = None,
        score: float = 0,
        rvol: float = 0,
        gap: float = 0,
        dvol: float = 0,
        catalyst: str = "",
        trigger_price: float = None,
        pm_high: float = None,
        vwap: float = None,
        entry_type: str = "LIMIT",
        shares: int = None,
        wait_for_fill: int = 10
    ):
        price = round(float(price), 2)
        if price <= 0:
            return {"success": False, "filled": False, "order": None, "filled_price": None, "shares": 0}

        # ---- Position sizing ----
        if shares is None or shares <= 0:
            try:
                account = self.get_account()
                equity = float(account.equity)
                if stop_price is not None and float(stop_price) < price:
                    risk_amount = equity * 0.02
                    risk_per_share = price - float(stop_price)
                    shares = int(risk_amount / risk_per_share)
                else:
                    allocation = equity * 0.02
                    shares = int(allocation / price)
            except Exception as e:
                print(f"[PaperTrader] ⚠️ Sizing error: {e}")
                shares = 1
        shares = max(1, int(shares))

        print(f"[PaperTrader] ORDER {symbol} @ ${price:.2f} x {shares}")

        # ---- Submit LIMIT order ----
        try:
            order = self.api.submit_order(
                symbol=symbol,
                qty=shares,
                side="buy",
                type="limit",
                limit_price=price,
                time_in_force="day"
            )
            print(f"[PaperTrader] 📤 Order submitted {symbol} | ID={order.id}")
        except Exception as e:
            print(f"[PaperTrader] ❌ Order failed {symbol}: {e}")
            return {"success": False, "filled": False, "order": None, "filled_price": None, "shares": shares}

        # ---- Wait for fill ----
        filled_order = None
        for attempt in range(wait_for_fill):
            time.sleep(1)
            current = self.get_order(order.id)
            if current is None:
                continue
            status = str(current.status).lower()
            print(f"[PaperTrader] {symbol} order status: {status}")
            if status == "filled":
                filled_order = current
                break
            if status in ("canceled", "cancelled", "rejected", "expired"):
                print(f"[PaperTrader] ❌ {symbol} order {status}")
                return {"success": False, "filled": False, "order": current, "filled_price": None, "shares": shares}

        if filled_order is None:
            print(f"[PaperTrader] ⏳ {symbol} not filled after {wait_for_fill}s")
            try:
                self.api.cancel_order(order.id)
                print(f"[PaperTrader] Cancelled unfilled order {symbol}")
            except:
                pass
            return {"success": False, "filled": False, "order": order, "filled_price": None, "shares": shares}

        # ---- FILLED ----
        filled_price = float(filled_order.filled_avg_price)
        filled_qty = int(float(filled_order.filled_qty))
        print(f"[PaperTrader] ✅ FILLED {symbol} @ ${filled_price:.2f} x {filled_qty}")

        # ---- SAVE TRADE ----
        try:
            save_trade(
                ticker=symbol,
                entry=filled_price,
                stop=stop_price,
                tp1=tp1,
                tp2=tp2,
                rr1=rr1,
                rr2=rr2,
                score=score,
                rvol=rvol,
                gap=gap,
                dvol=dvol,
                catalyst=catalyst,
                trigger_price=trigger_price,
                pm_high=pm_high,
                vwap=vwap,
                entry_type=entry_type
            )
            print(f"[PaperTrader] 💾 {symbol} saved to DB")
        except Exception as e:
            print(f"[PaperTrader] ❌ DB save failed for {symbol}: {e}")

        # ---- BRACKET ORDERS ----
        if stop_price is not None and stop_price > 0:
            self.set_stop_loss(symbol, stop_price, filled_qty)
        if tp1 is not None and tp1 > 0:
            self.set_take_profit(symbol, tp1, filled_qty)
        if tp2 is not None and tp2 > 0:
            self.set_take_profit(symbol, tp2, filled_qty)

        return {
            "success": True,
            "filled": True,
            "order": filled_order,
            "filled_price": filled_price,
            "shares": filled_qty
        }

    def set_stop_loss(self, symbol: str, stop_price: float, qty: int = None):
        stop_price = round(float(stop_price), 2)
        if qty is None:
            try:
                pos = self.api.get_position(symbol)
                qty = int(float(pos.qty))
            except:
                print(f"[PaperTrader] ⚠️ Cannot get position for {symbol}, skipping stop")
                return None
        if qty <= 0:
            return None
        try:
            order = self.api.submit_order(
                symbol=symbol,
                qty=qty,
                side="sell",
                type="stop",
                stop_price=stop_price,
                time_in_force="day"
            )
            print(f"[PaperTrader] 🛑 STOP-LOSS set for {symbol} @ ${stop_price:.2f} (Order: {order.id})")
            return order
        except Exception as e:
            print(f"[PaperTrader] ❌ Stop-loss failed for {symbol}: {e}")
            return None

    def set_take_profit(self, symbol: str, target_price: float, qty: int = None):
        target_price = round(float(target_price), 2)
        if qty is None:
            try:
                pos = self.api.get_position(symbol)
                qty = int(float(pos.qty))
            except:
                print(f"[PaperTrader] ⚠️ Cannot get position for {symbol}, skipping TP")
                return None
        if qty <= 0:
            return None
        try:
            order = self.api.submit_order(
                symbol=symbol,
                qty=qty,
                side="sell",
                type="limit",
                limit_price=target_price,
                time_in_force="day"
            )
            print(f"[PaperTrader] 🎯 TAKE-PROFIT set for {symbol} @ ${target_price:.2f} (Order: {order.id})")
            return order
        except Exception as e:
            print(f"[PaperTrader] ❌ Take-profit failed for {symbol}: {e}")
            return None
