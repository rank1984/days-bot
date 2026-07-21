"""
Feedback Loop – learns from past candidates
"""
import os
import json
import pandas as pd
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional
import yfinance as yf

class FeedbackLearner:
    def __init__(self, data_dir: str = "data"):
        self.data_dir = data_dir
        self.history_file = os.path.join(data_dir, "candidates_history.json")
        self.performance_file = os.path.join(data_dir, "performance_metrics.json")
        os.makedirs(data_dir, exist_ok=True)
        self.load_data()
    
    def load_data(self):
        """טען היסטוריית מועמדויות ונתוני ביצועים"""
        if os.path.exists(self.history_file):
            with open(self.history_file, 'r') as f:
                self.history = json.load(f)
        else:
            self.history = {'candidates': [], 'trades': []}
        
        if os.path.exists(self.performance_file):
            with open(self.performance_file, 'r') as f:
                self.metrics = json.load(f)
        else:
            self.metrics = {
                'total_candidates': 0,
                'trades_taken': 0,
                'wins': 0,
                'losses': 0,
                'total_pnl': 0,
                'avg_gain': 0,
                'avg_loss': 0,
                'win_rate': 0,
                'best_filters': {},
            }
    
    def save_data(self):
        """שמור נתונים"""
        with open(self.history_file, 'w') as f:
            json.dump(self.history, f, indent=2)
        with open(self.performance_file, 'w') as f:
            json.dump(self.metrics, f, indent=2)
    
    def add_candidate(self, candidate: Dict[str, Any]):
        """הוסף מועמד להיסטוריה עם חותמת זמן"""
        entry = {
            'ticker': candidate['ticker'],
            'price': candidate['price'],
            'gap_pct': candidate['gap_pct'],
            'volume': candidate.get('volume', 0),
            'score': candidate.get('score', 0),
            'timestamp': datetime.now().isoformat(),
            'entry_price': candidate['price'],  # נשתמש במחיר המועמדות
            'checked': False,
            'result': None,  # 'win', 'loss', 'pending'
            'pnl': 0,
            'exit_price': None,
            'exit_time': None,
        }
        self.history['candidates'].append(entry)
        self.metrics['total_candidates'] += 1
        self.save_data()
    
    def check_results(self, days_back: int = 1):
        """בדוק תוצאות של מועמדויות קודמות"""
        cutoff = datetime.now() - timedelta(days=days_back)
        for c in self.history['candidates']:
            if c['checked']:
                continue
            if datetime.fromisoformat(c['timestamp']) < cutoff:
                self._evaluate_candidate(c)
        self.save_data()
    
    def _evaluate_candidate(self, candidate: Dict):
        """בדוק איך המניה התנהלה אחרי המועמדות"""
        ticker = candidate['ticker']
        entry_price = candidate['entry_price']
        entry_time = datetime.fromisoformat(candidate['timestamp'])
        
        try:
            # הורד נתוני 1 יום אחרי המועמדות
            ticker_obj = yf.Ticker(ticker)
            end_date = entry_time + timedelta(days=1)
            hist = ticker_obj.history(start=entry_time.strftime('%Y-%m-%d'), 
                                      end=end_date.strftime('%Y-%m-%d'))
            if hist.empty:
                candidate['checked'] = True
                return
            
            # מצא את המחיר הגבוה ביותר ביום המסחר
            high_price = hist['High'].max() if 'High' in hist else 0
            close_price = hist['Close'].iloc[-1] if 'Close' in hist else 0
            
            # רווח מקסימלי אפשרי
            max_pnl = ((high_price - entry_price) / entry_price) * 100 if entry_price > 0 else 0
            
            # רווח בסגירה
            close_pnl = ((close_price - entry_price) / entry_price) * 100 if entry_price > 0 else 0
            
            candidate['max_pnl'] = max_pnl
            candidate['close_pnl'] = close_pnl
            candidate['high_price'] = high_price
            candidate['close_price'] = close_price
            candidate['checked'] = True
            
            # הגדר תוצאה לפי סף רווח של 3% (אחרי מס 2.25% נטו)
            if max_pnl >= 10.0:
                candidate['result'] = 'win'
                self.metrics['wins'] += 1
                self.metrics['total_pnl'] += max_pnl
            elif max_pnl < -5.0:
                candidate['result'] = 'loss'
                self.metrics['losses'] += 1
                self.metrics['total_pnl'] += max_pnl
            else:
                candidate['result'] = 'neutral'
            
            # עדכון המטא-למידה
            self._update_filters_learning(candidate)
            
        except Exception as e:
            print(f"[Feedback] Error evaluating {ticker}: {e}")
            candidate['checked'] = True
    
    def _update_filters_learning(self, candidate: Dict):
        """עדכן איזה פילטרים הכי מנבאים הצלחה"""
        filters = {
            'gap_high': candidate['gap_pct'] >= 5.0,
            'gap_medium': 2.0 <= candidate['gap_pct'] < 5.0,
            'volume_high': candidate['volume'] >= 200_000,
            'score_high': candidate['score'] >= 60,
        }
        
        result = candidate['result']
        for f_name, passed in filters.items():
            if f_name not in self.metrics['best_filters']:
                self.metrics['best_filters'][f_name] = {'wins': 0, 'losses': 0, 'total': 0}
            if passed:
                self.metrics['best_filters'][f_name]['total'] += 1
                if result == 'win':
                    self.metrics['best_filters'][f_name]['wins'] += 1
                elif result == 'loss':
                    self.metrics['best_filters'][f_name]['losses'] += 1
    
    def get_insights(self) -> Dict[str, Any]:
        """הפקת תובנות מנתוני הלמידה"""
        self.check_results()
        
        total = self.metrics['wins'] + self.metrics['losses']
        win_rate = (self.metrics['wins'] / total * 100) if total > 0 else 0
        
        # מציאת הפילטרים הטובים ביותר
        best_filters = []
        for f_name, data in self.metrics['best_filters'].items():
            if data['total'] > 0:
                rate = (data['wins'] / data['total'] * 100) if data['total'] > 0 else 0
                best_filters.append({
                    'filter': f_name,
                    'win_rate': rate,
                    'total': data['total'],
                })
        best_filters.sort(key=lambda x: -x['win_rate'])
        
        insights = {
            'total_candidates': self.metrics['total_candidates'],
            'trades_taken': total,
            'win_rate': win_rate,
            'total_pnl': self.metrics['total_pnl'],
            'avg_pnl': self.metrics['total_pnl'] / total if total > 0 else 0,
            'best_filters': best_filters[:5],
            'recommendation': self._get_recommendation(win_rate, self.metrics['total_pnl']),
        }
        return insights
    
    def _get_recommendation(self, win_rate: float, total_pnl: float) -> str:
        """המלצה המבוססת על הנתונים"""
        if win_rate >= 60 and total_pnl > 0:
            return "🚀 האסטרטגיה עובדת! המשך עם הפילטרים הנוכחיים."
        elif win_rate >= 50 and total_pnl > 0:
            return "📈 האסטרטגיה סבירה. שקול להדק פילטרים."
        elif win_rate >= 40 and total_pnl > 0:
            return "📊 האסטרטגיה זקוקה לשיפור. בדוק פילטרים נוספים."
        elif total < 10:
            return "📚 אסוף עוד נתונים (לפחות 10 מועמדויות) לפני מסקנות."
        else:
            return "⚠️ האסטרטגיה לא עובדת. שנה פילטרים באופן משמעותי."
    
    def get_top_performers(self, n: int = 10) -> List[Dict]:
        """החזרת המועמדויות הטובות ביותר"""
        checked = [c for c in self.history['candidates'] if c.get('checked')]
        sorted_candidates = sorted(checked, key=lambda x: x.get('max_pnl', -999), reverse=True)
        return sorted_candidates[:n]
    
    def get_bottom_performers(self, n: int = 10) -> List[Dict]:
        """החזרת המועמדויות הגרועות ביותר"""
        checked = [c for c in self.history['candidates'] if c.get('checked')]
        sorted_candidates = sorted(checked, key=lambda x: x.get('max_pnl', 999))
        return sorted_candidates[:n]
    
    def generate_report(self) -> str:
        """הפקת דוח קריא"""
        insights = self.get_insights()
        lines = []
        lines.append("=" * 50)
        lines.append("📊 FEEDBACK REPORT")
        lines.append("=" * 50)
        lines.append(f"Total candidates:  {insights['total_candidates']}")
        lines.append(f"Trades taken:      {insights['trades_taken']}")
        lines.append(f"Win rate:          {insights['win_rate']:.1f}%")
        lines.append(f"Total P&L:         {insights['total_pnl']:.2f}%")
        lines.append(f"Avg P&L per trade: {insights['avg_pnl']:.2f}%")
        lines.append("-" * 50)
        lines.append("🏆 Best filters:")
        for f in insights['best_filters']:
            lines.append(f"  • {f['filter']}: {f['win_rate']:.0f}% ({f['total']} trades)")
        lines.append("-" * 50)
        lines.append(f"💡 Recommendation: {insights['recommendation']}")
        lines.append("=" * 50)
        return "\n".join(lines)
