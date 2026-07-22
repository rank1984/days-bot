"""
Daily Backtest – tracks candidate performance
"""
import os
import json
import pandas as pd
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional
import yfinance as yf

class DailyBacktest:
    def __init__(self, data_dir: str = "data"):
        self.data_dir = data_dir
        self.backtest_file = os.path.join(data_dir, "daily_backtest.json")
        self.load_data()
    
    def load_data(self):
        if os.path.exists(self.backtest_file):
            with open(self.backtest_file, 'r') as f:
                self.data = json.load(f)
        else:
            self.data = {'trades': [], 'summary': {}}
    
    def save_data(self):
        with open(self.backtest_file, 'w') as f:
            json.dump(self.data, f, indent=2)
    
    def add_candidate(self, candidate: Dict[str, Any]):
        """הוסף מועמד לבדיקת Backtest"""
        entry = {
            'ticker': candidate['ticker'],
            'entry_price': candidate['price'],
            'date': datetime.now().strftime('%Y-%m-%d'),
            'gap_pct': candidate['gap_pct'],
            'score': candidate.get('score', 0),
            'checked': False,
        }
        self.data['trades'].append(entry)
        self.save_data()
    
    def run_backtest(self, days_back: int = 1):
        """בדוק ביצועים של כל המועמדויות"""
        cutoff = datetime.now() - timedelta(days=days_back)
        
        for trade in self.data['trades']:
            if trade.get('checked'):
                continue
            
            trade_date = datetime.strptime(trade['date'], '%Y-%m-%d')
            if trade_date < cutoff:
                self._evaluate_trade(trade)
        
        self._update_summary()
        self.save_data()
    
    def _evaluate_trade(self, trade: Dict):
        """בדוק איך המניה התנהלה ביום המסחר"""
        ticker = trade['ticker']
        entry = trade['entry_price']
        date = trade['date']
        
        try:
            ticker_obj = yf.Ticker(ticker)
            start = datetime.strptime(date, '%Y-%m-%d')
            end = start + timedelta(days=1)
            
            hist = ticker_obj.history(start=start.strftime('%Y-%m-%d'), 
                                      end=end.strftime('%Y-%m-%d'))
            if hist.empty:
                trade['checked'] = True
                return
            
            # נתוני היום
            open_price = hist['Open'].iloc[0]
            high = hist['High'].max()
            low = hist['Low'].min()
            close = hist['Close'].iloc[-1]
            
            # רווחים והפסדים
            high_pnl = ((high - open_price) / open_price) * 100
            low_pnl = ((low - open_price) / open_price) * 100
            close_pnl = ((close - open_price) / open_price) * 100
            
            # האם הגיע ליעדים?
            targets = [5, 10, 15, 20, 30]
            hit_targets = {}
            for t in targets:
                hit_targets[f'hit_{t}pct'] = high_pnl >= t
            
            # האם חטף סטופ?
            hit_stop = low_pnl <= -5
            
            # עדכון
            trade.update({
                'open': open_price,
                'high': high,
                'low': low,
                'close': close,
                'high_pnl': high_pnl,
                'low_pnl': low_pnl,
                'close_pnl': close_pnl,
                'hit_targets': hit_targets,
                'hit_stop': hit_stop,
                'checked': True,
            })
            
        except Exception as e:
            print(f"[Backtest] Error evaluating {ticker}: {e}")
            trade['checked'] = True
    
    def _update_summary(self):
        """עדכן סיכום מצטבר"""
        trades = [t for t in self.data['trades'] if t.get('checked')]
        if not trades:
            return
        
        total = len(trades)
        wins = sum(1 for t in trades if t.get('close_pnl', 0) > 0)
        losses = total - wins
        
        # הישגי יעדים
        targets = [5, 10, 15, 20, 30]
        hit_rates = {}
        for t in targets:
            hit = sum(1 for tr in trades if tr.get('hit_targets', {}).get(f'hit_{t}pct', False))
            hit_rates[f'{t}pct'] = (hit / total) * 100
        
        self.data['summary'] = {
            'total_trades': total,
            'wins': wins,
            'losses': losses,
            'win_rate': (wins / total) * 100 if total > 0 else 0,
            'avg_high_pnl': sum(t.get('high_pnl', 0) for t in trades) / total,
            'avg_low_pnl': sum(t.get('low_pnl', 0) for t in trades) / total,
            'avg_close_pnl': sum(t.get('close_pnl', 0) for t in trades) / total,
            'hit_rates': hit_rates,
            'hit_stop_rate': (sum(1 for t in trades if t.get('hit_stop', False)) / total) * 100,
            'last_updated': datetime.now().isoformat(),
        }
    
    def get_report(self) -> str:
        """הפקת דוח"""
        self.run_backtest()
        s = self.data.get('summary', {})
        
        lines = [
            "=" * 50,
            "📊 BACKTEST REPORT",
            "=" * 50,
            f"Total Trades:   {s.get('total_trades', 0)}",
            f"Win Rate:       {s.get('win_rate', 0):.1f}%",
            f"Avg High P&L:   {s.get('avg_high_pnl', 0):.2f}%",
            f"Avg Close P&L:  {s.get('avg_close_pnl', 0):.2f}%",
            f"Hit Stop Rate:  {s.get('hit_stop_rate', 0):.1f}%",
            "-" * 50,
            "🎯 Target Hit Rates:",
        ]
        
        for target, rate in s.get('hit_rates', {}).items():
            lines.append(f"  • {target}: {rate:.1f}%")
        
        lines.append("=" * 50)
        return "\n".join(lines)
