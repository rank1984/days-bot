from .trade_manager import TradeManager
class PaperTrader:
    def __init__(self, paper: bool = True):
        base_url = 'https://paper-api.alpaca.markets' if paper else 'https://api.alpaca.markets'
        self.api = tradeapi.REST(ALPACA_API_KEY, ALPACA_SECRET_KEY, base_url=base_url)
        # ... שאר הקוד ...
