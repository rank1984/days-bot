"""
Paper Trading module using Alpaca Paper API
"""
import alpaca_trade_api as tradeapi
from datetime import datetime
from typing import Dict, List, Any

from utils.config import *

class PaperTrader:
    def __init__(self):
        self.api = tradeapi.REST(
            ALPACA_API_KEY,
            ALPACA_SECRET_KEY,
            base_url='https://paper-api.alpaca.markets'
        )
        self.positions = {}
    
    def get_account(self):
        """Get account info"""
        return self.api.get_account()
    
    def get_positions(self):
        """Get current positions"""
        return self.api.list_positions()
    
    def enter_trade(self, symbol: str, price: float, shares: int = None):
        """Enter a trade"""
        if shares is None:
            # Calculate shares based on risk
            account = self.get_account()
            equity = float(account.equity)
            risk_amount = equity * 0.02  # 2% risk per trade
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
            print(f"[PaperTrade] Entered {symbol} @ ${price} x {shares} shares")
            return order
        except Exception as e:
            print(f"[PaperTrade] Error entering trade: {e}")
            return None
    
    def set_stop_loss(self, symbol: str, stop_price: float):
        """Set stop-loss order"""
        try:
            order = self.api.submit_order(
                symbol=symbol,
                qty=self.get_position_qty(symbol),
                side='sell',
                type='stop',
                stop_price=stop_price,
                time_in_force='day'
            )
            print(f"[PaperTrade] Stop-loss set for {symbol} @ ${stop_price}")
            return order
        except Exception as e:
            print(f"[PaperTrade] Error setting stop-loss: {e}")
            return None
    
    def set_take_profit(self, symbol: str, target_price: float):
        """Set take-profit order"""
        try:
            order = self.api.submit_order(
                symbol=symbol,
                qty=self.get_position_qty(symbol),
                side='sell',
                type='limit',
                limit_price=target_price,
                time_in_force='day'
            )
            print(f"[PaperTrade] Take-profit set for {symbol} @ ${target_price}")
            return order
        except Exception as e:
            print(f"[PaperTrade] Error setting take-profit: {e}")
            return None
    
    def get_position_qty(self, symbol: str) -> int:
        """Get position quantity for a symbol"""
        try:
            pos = self.api.get_position(symbol)
            return int(pos.qty)
        except:
            return 0
    
    def close_position(self, symbol: str):
        """Close a position"""
        try:
            self.api.close_position(symbol)
            print(f"[PaperTrade] Closed position for {symbol}")
        except Exception as e:
            print(f"[PaperTrade] Error closing position: {e}")
    
    def get_portfolio_value(self) -> float:
        """Get total portfolio value"""
        account = self.get_account()
        return float(account.equity)
    
    def get_daily_pnl(self) -> float:
        """Get daily P&L"""
        account = self.get_account()
        return float(account.equity) - float(account.last_equity)
