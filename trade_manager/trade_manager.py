"""
Trade Manager – converts scanner output into a trade plan
"""
from typing import Dict, Any

class TradeManager:
    def __init__(self):
        # מטריצת איכות – קובעת יעדים דינמיים לפי ציון ו-RVOL
        self.score_matrix = {
            'excellent': {'min_score': 85, 'min_rvol': 4.0, 'tp1': 0.07, 'tp2': 0.15, 'runner': True},
            'good':      {'min_score': 75, 'min_rvol': 3.0, 'tp1': 0.06, 'tp2': 0.12, 'runner': True},
            'average':   {'min_score': 65, 'min_rvol': 2.0, 'tp1': 0.05, 'tp2': 0.10, 'runner': True},
            'watch':     {'min_score': 55, 'min_rvol': 1.5, 'tp1': 0.04, 'tp2': 0.08, 'runner': False},
        }
    
    def generate_plan(self, candidate: Dict[str, Any]) -> Dict[str, Any]:
        """
        מקבל מועמד מהסורק, מחזיר תוכנית מסחר מלאה
        
        Args:
            candidate: dict עם ticker, price, gap_pct, rvol, score
        
        Returns:
            dict: תוכנית מסחר עם entry, stop, tp1, tp2, runner, confidence
        """
        score = candidate.get('score', 50)
        rvol = candidate.get('rvol', 1.0)
        price = candidate.get('price', 0)
        ticker = candidate.get('ticker', '???')
        gap = candidate.get('gap_pct', 0)
        
        # מציאת רמת איכות
        level = self._get_level(score, rvol)
        matrix = self.score_matrix[level]
        
        # סטופ – 5% (קבוע, אבל ניתן לשנות)
        stop_pct = 0.05
        stop_price = round(price * (1 - stop_pct), 2)
        
        # יעדי רווח דינמיים לפי המטריצה
        tp1_pct = matrix['tp1']
        tp2_pct = matrix['tp2']
        runner = matrix['runner']
        
        tp1_price = round(price * (1 + tp1_pct), 2)
        tp2_price = round(price * (1 + tp2_pct), 2)
        
        # דירוג אמון בכוכבים
        confidence = self._get_confidence(score, rvol)
        
        return {
            'ticker': ticker,
            'entry': price,
            'stop': stop_price,
            'tp1': tp1_price,
            'tp2': tp2_price,
            'runner': runner,
            'level': level,
            'confidence': confidence,
            'score': score,
            'rvol': rvol,
            'gap_pct': gap,
        }
    
    def _get_level(self, score: float, rvol: float) -> str:
        """החזר את רמת האיכות לפי Score ו-RVOL"""
        if score >= 85 and rvol >= 4.0:
            return 'excellent'
        elif score >= 75 and rvol >= 3.0:
            return 'good'
        elif score >= 65 and rvol >= 2.0:
            return 'average'
        else:
            return 'watch'  # ברירת מחדל
    
    def _get_confidence(self, score: float, rvol: float) -> str:
        """החזר דירוג אמון בכוכבים"""
        if score >= 85 and rvol >= 4.0:
            return "⭐⭐⭐⭐⭐"
        elif score >= 75 and rvol >= 3.0:
            return "⭐⭐⭐⭐"
        elif score >= 65 and rvol >= 2.0:
            return "⭐⭐⭐"
        elif score >= 55 and rvol >= 1.5:
            return "⭐⭐"
        else:
            return "⭐"
    
    def get_trade_summary(self, plan: Dict[str, Any]) -> str:
        """החזר סיכום קצר של תוכנית המסחר (לדוגמה לשליחה לטלגרם)"""
        lines = []
        lines.append(f"🎯 <b>{plan['ticker']}</b>  {plan['confidence']}")
        lines.append(f"💰 כניסה: ${plan['entry']:.2f}")
        lines.append(f"🛑 סטופ:  ${plan['stop']:.2f}  (-5%)")
        lines.append(f"🎯 TP1:   ${plan['tp1']:.2f}  (+{((plan['tp1']/plan['entry'])-1)*100:.0f}%)")
        lines.append(f"🎯 TP2:   ${plan['tp2']:.2f}  (+{((plan['tp2']/plan['entry'])-1)*100:.0f}%)")
        lines.append(f"🏃 Runner: {'כן' if plan['runner'] else 'לא'}")
        lines.append(f"📊 Level: {plan['level'].upper()}  |  Score: {plan['score']:.0f}  |  RVOL: {plan['rvol']:.1f}x")
        lines.append(f"━━━━━━━━━━━━━━━━━━")
        return "\n".join(lines)
