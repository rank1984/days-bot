"""
Paper Trading module using Alpaca Paper API
"""
import alpaca_trade_api as tradeapi
from datetime import datetime
from typing import Dict, List, Any, Optional

from utils.config import ALPACA_API_KEY, ALPACA_SECRET_KEY

class PaperTrader:
    def __init__(self, paper: bool = True):
        """
        אתחול בוט המסחר.
        paper=True → משתמש ב-Paper API (כסף דמה)
        paper=False → משתמש ב-Live API (כסף אמיתי)
        """
        base_url = 'https://paper-api.alpaca.markets' if paper else 'https://api.alpaca.markets'
        self.api = tradeapi.REST(ALPACA_API_KEY, ALPACA_SECRET_KEY, base_url=base_url)
        self.paper = paper
        print(f"[PaperTrader] Initialized {'PAPER' if paper else 'LIVE'} trading")
    
    def get_account(self):
        return self.api.get_account()
    
    def get_positions(self):
        return self.api.list_positions()
    
    def enter_trade(self, symbol: str, price: float, shares: int = None):
        if shares is None:
            account = self.get_account()
            equity = float(account.equity)
            risk_amount = equity * 0.02
            shares = int(risk_amount / price)
            if shares < 1:
                shares = 1
        
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
            print(f"[PaperTrade] Error entering trade: {e}")
            return None
    
    def set_stop_loss(self, symbol: str, stop_price: float):
        qty = self.get_position_qty(symbol)
        if qty <= 0:
            return None
        try:
            order = self.api.submit_order(
                symbol=symbol,
                qty=qty,
                side='sell',
                type='stop',
                stop_price=stop_price,
                time_in_force='day'
            )
            print(f"[PaperTrade] STOP-LOSS set for {symbol} @ ${stop_price:.2f}")
            return order
        except Exception as e:
            print(f"[PaperTrade] Error setting stop-loss: {e}")
            return None
    
    def set_take_profit(self, symbol: str, target_price: float):
        qty = self.get_position_qty(symbol)
        if qty <= 0:
            return None
        try:
            order = self.api.submit_order(
                symbol=symbol,
                qty=qty,
                side='sell',
                type='limit',
                limit_price=target_price,
                time_in_force='day'
            )
            print(f"[PaperTrade] TAKE-PROFIT set for {symbol} @ ${target_price:.2f}")
            return order
        except Exception as e:
            print(f"[PaperTrade] Error setting take-profit: {e}")
            return None
    
    def get_position_qty(self, symbol: str) -> int:
        try:
            pos = self.api.get_position(symbol)
            return int(pos.qty)
        except:
            return 0
    
    def close_position(self, symbol: str):
        try:
            self.api.close_position(symbol)
            print(f"[PaperTrade] Closed position for {symbol}")
        except Exception as e:
            print(f"[PaperTrade] Error closing position: {e}")
    
    def get_portfolio_value(self) -> float:
        account = self.get_account()
        return float(account.equity)
    
    def get_daily_pnl(self) -> float:
        account = self.get_account()
        return float(account.equity) - float(account.last_equity)