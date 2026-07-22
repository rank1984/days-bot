"""
Trade Manager – Entry & Exit logic for big moves
"""
from datetime import datetime, timedelta
from typing import Dict, Any, Optional, List
import alpaca_trade_api as tradeapi
from utils.config import *

class TradeManager:
    def __init__(self, paper: bool = True):
        """אתחול – משתמש ב-Paper API כברירת מחדל"""
        base_url = 'https://paper-api.alpaca.markets' if paper else 'https://api.alpaca.markets'
        self.api = tradeapi.REST(ALPACA_API_KEY, ALPACA_SECRET_KEY, base_url=base_url)
        self.positions = {}
        self.trades_log = []
    
    # ─── ENTRY ────────────────────────────────────────────────
    def should_enter(self, candidate: Dict[str, Any]) -> bool:
        """
        קריטריוני כניסה קפדניים:
        1. Gap 3%–25% (מומנטום חזק)
        2. RVOL > 2.0 (עניין חריג)
        3. Dollar Volume > $1M (נזילות)
        4. מחיר > $0.50 (לא פני)
        5. Score > 50 (איכות)
        """
        gap = candidate.get('gap_pct', 0)
        rvol = candidate.get('rvol', 0)
        dvol = candidate.get('dollar_volume', 0)
        price = candidate.get('price', 0)
        score = candidate.get('score', 0)
        
        if not (3.0 <= gap <= 25.0):
            return False
        if rvol < 2.0:
            return False
        if dvol < 1_000_000:
            return False
        if price < 0.50:
            return False
        if score < 50:
            return False
        
        # בדיקת זמן – רק בין 09:30 ל-15:45 ET (למסחר רגיל)
        now = datetime.now()
        if now.weekday() >= 5:  # סוף שבוע
            return False
        et = datetime.now()  # נניח UTC=ET-4 (קיץ) – אבל נשתמש בבדיקה גמישה
        # נשתמש ב-Alpaca Clock לקביעת שעות מסחר
        clock = self.api.get_clock()
        if not clock.is_open:
            return False
        # ניתן להוסיף הגבלת כניסה אחרי 15:45 כדי להספיק לצאת
        return True
    
    def calculate_position_size(self, price: float, risk_per_trade: float = 0.02) -> int:
        """גודל פוזיציה לפי סיכון 2% מהתיק"""
        account = self.api.get_account()
        equity = float(account.equity)
        risk_amount = equity * risk_per_trade
        stop_loss_pct = 0.05  # 5% סטופ
        shares = int(risk_amount / (price * stop_loss_pct))
        return max(shares, 1)  # לפחות 1 מניה
    
    def enter_trade(self, candidate: Dict[str, Any]) -> Optional[Dict]:
        """בצע כניסה – שוק או לימיט"""
        if not self.should_enter(candidate):
            return None
        
        symbol = candidate['ticker']
        price = candidate['price']
        shares = self.calculate_position_size(price)
        
        try:
            # כניסה בלימיט (מחיר נוכחי + סובלנות)
            limit_price = round(price * 1.005, 2)  # 0.5% סובלנות
            order = self.api.submit_order(
                symbol=symbol,
                qty=shares,
                side='buy',
                type='limit',
                limit_price=limit_price,
                time_in_force='day'
            )
            print(f"[Trade] ENTER {symbol} @ {limit_price} x {shares} shares")
            
            # שמירת פרטי העסקה
            trade = {
                'symbol': symbol,
                'entry_price': limit_price,
                'shares': shares,
                'entry_time': datetime.now().isoformat(),
                'stop_loss': price * 0.95,   # 5% סטופ
                'take_profit_1': price * 1.10,  # 10% partial
                'take_profit_2': price * 1.20,  # 20% target
                'take_profit_3': price * 1.30,  # 30% target
            }
            self.trades_log.append(trade)
            return trade
        except Exception as e:
            print(f"[Trade] ENTRY ERROR {symbol}: {e}")
            return None
    
    # ─── EXIT RULES (אחרי הניתוח) ─────────────────────────────
TAKE_PROFIT_1 = 0.10   # 10% → סגור 30%
TAKE_PROFIT_2 = 0.15   # 15% → סגור 40%
TAKE_PROFIT_3 = 0.20   # 20% → סגור 30%
STOP_LOSS = 0.05       # 5% סטופ ראשוני
TRAILING_ACTIVATE = 0.05  # הפעל סטופ נגרר אחרי 5%+

def should_exit(self, position: Dict) -> str:
    symbol = position['symbol']
    entry = position['entry_price']
    current = self.get_current_price(symbol)
    if not current:
        return 'hold'
    
    change_pct = (current - entry) / entry * 100
    
    # 1. Stop-Loss
    if change_pct <= -STOP_LOSS * 100:
        return 'stop_loss'
    
    # 2. Trailing Stop (אחרי 5%+)
    if change_pct >= TRAILING_ACTIVATE * 100:
        high = self.get_high_since_entry(symbol, entry)
        if high:
            drawdown = (high - current) / high * 100
            if drawdown >= 3.0:  # ירידה של 3% מהשיא
                return 'trailing_stop'
    
    # 3. Take-Profit מדורג
    if change_pct >= TAKE_PROFIT_3 * 100:
        return 'take_profit_3'
    elif change_pct >= TAKE_PROFIT_2 * 100:
        return 'take_profit_2'
    elif change_pct >= TAKE_PROFIT_1 * 100:
        # אם הגיע ל-10% תוך 30 דקות – סגור חלק
        elapsed = (datetime.now() - datetime.fromisoformat(position['entry_time'])).seconds / 60
        if elapsed < 30:
            return 'take_profit_1'
    
    # 4. Time Stop
    elapsed = (datetime.now() - datetime.fromisoformat(position['entry_time'])).seconds / 60
    if elapsed > 60 and change_pct < 3.0:
        return 'time_stop'
    
    return 'hold'
        
        # 3. Time Stop – אם אחרי 60 דקות אין 5%+ – נצא
        elapsed = (datetime.now() - datetime.fromisoformat(position['entry_time'])).seconds / 60
        if elapsed > 60 and change_pct < 5.0:
            return 'time_stop'
        
        return 'hold'
    
    def execute_exit(self, position: Dict, exit_reason: str):
        """בצע יציאה לפי הסיבה"""
        symbol = position['symbol']
        shares = position['shares']
        current = self.get_current_price(symbol)
        if not current:
            return
        
        # מכירה בחלקים לפי הסיבה
        if exit_reason == 'stop_loss':
            qty = shares
        elif exit_reason == 'take_profit_3':
            qty = shares
        elif exit_reason == 'take_profit_2':
            qty = int(shares * 0.7)  # 70% מהפוזיציה
        elif exit_reason == 'take_profit_1':
            qty = int(shares * 0.3)  # 30%
        elif exit_reason == 'time_stop':
            qty = shares
        else:
            return
        
        if qty <= 0:
            return
        
        try:
            order = self.api.submit_order(
                symbol=symbol,
                qty=qty,
                side='sell',
                type='limit',
                limit_price=round(current * 0.995, 2),
                time_in_force='day'
            )
            print(f"[Trade] EXIT {symbol} @ {current:.2f} ({exit_reason}) x {qty} shares")
            
            # רישום הרווח/הפסד
            pnl = (current - position['entry_price']) / position['entry_price'] * 100
            self.trades_log.append({
                'symbol': symbol,
                'exit_price': current,
                'exit_time': datetime.now().isoformat(),
                'exit_reason': exit_reason,
                'pnl_pct': pnl,
                'shares': qty,
            })
        except Exception as e:
            print(f"[Trade] EXIT ERROR {symbol}: {e}")
    
    # ─── HELPERS ──────────────────────────────────────────────
    def get_current_price(self, symbol: str) -> Optional[float]:
        try:
            trade = self.api.get_last_trade(symbol)
            return trade.price
        except:
            return None
    
    def get_high_since_entry(self, symbol: str, entry_price: float) -> Optional[float]:
        # מחזיר את המחיר הגבוה ביותר מאז הכניסה (לפי נתונים היסטוריים)
        try:
            bars = self.api.get_bars(symbol, timeframe='1Min', limit=60)
            if bars:
                high = max(b.high for b in bars)
                return high
        except:
            pass
        return None
    
    def get_open_positions(self) -> List[Dict]:
        """קבל רשימת פוזיציות פתוחות מהחשבון"""
        positions = self.api.list_positions()
        result = []
        for p in positions:
            # התאם לעסקאות שלנו (נוכל לשמור ב-DB או בזיכרון)
            result.append({
                'symbol': p.symbol,
                'qty': int(p.qty),
                'entry_price': float(p.avg_entry_price),
                'current_price': float(p.current_price),
                'pnl_pct': float(p.unrealized_plpc),
            })
        return result
    
    def monitor_and_exit(self):
        """רוץ על כל הפוזיציות הפתוחות ובדוק יציאה"""
        positions = self.get_open_positions()
        for pos in positions:
            # שלוף את פרטי העסקה מה-log (או DB)
            trade = self._find_trade(pos['symbol'])
            if not trade:
                continue
            reason = self.should_exit(trade)
            if reason != 'hold':
                self.execute_exit(trade, reason)
    
    def _find_trade(self, symbol: str) -> Optional[Dict]:
        """מחזיר את העסקה הפתוחה עבור הסימבול מה-Log"""
        for t in reversed(self.trades_log):
            if t.get('symbol') == symbol and 'exit_time' not in t:
                return t
        return None
