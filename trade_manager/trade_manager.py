"""
Trade Manager – Dynamic Trade Plan Generator
Based on Real Data (PM High, ATR, Weighted Score) with Risk/Reward Filter
"""
import math
from typing import Dict, Any, Optional
from datetime import datetime
import json
import os

class TradeManager:
    def __init__(self, data_dir: str = "data"):
        self.data_dir = data_dir
        os.makedirs(data_dir, exist_ok=True)
        self.performance_log = os.path.join(data_dir, "trades_history.json")
        
        # 1. משקלים לחישוב איכות האות (Weighted Quality Engine)
        self.weights = {
            'score': 0.40,      # הציון המקורי מהסורק
            'rvol': 0.25,       # נפח יחסי
            'pm_high': 0.15,    # קרבה לשיא הטרום-מסחר
            'dvol': 0.10,       # נפח בדולרים
            'news': 0.10        # קטליזטור (אם קיים)
        }

    def generate_plan(self, candidate: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """
        יוצר תוכנית מסחר דינמית.
        מחזיר None אם ה-Risk/Reward לא מספיק טוב (RR < 1.5)
        """
        price = candidate.get('price', 0)
        ticker = candidate.get('ticker', '???')
        
        # --- 1. חישוב איכות האות (Weighted Score) ---
        quality_score = self._calculate_weighted_score(candidate)
        
        # --- 2. סטופ דינמי (על בסיס ATR או 5% כגיבוי) ---
        atr = candidate.get('atr', price * 0.04)  # אם אין ATR, נניח 4% תנודתיות
        stop_pct = max(0.05, (atr / price) * 1.5)  # 5% מינימום, או 1.5x ATR
        stop_price = round(price * (1 - stop_pct), 2)
        
        # --- 3. יעדים דינמיים (על בסיס PM High ו-ATR) ---
        pm_high = candidate.get('pm_high', price * 1.05)  # שיא טרום-מסחר
        
        # TP1 = PM High (ההתנגדות הטכנית הראשונה)
        if pm_high > price:
            tp1_price = round(pm_high, 2)
        else:
            tp1_price = round(price * 1.04, 2)  # גיבוי: 4%
        
        # TP2 = PM High + ATR (מעבר להתנגדות)
        tp2_price = round(tp1_price + atr, 2)
        
        # --- 4. Risk / Reward ---
        risk = price - stop_price
        reward1 = tp1_price - price
        reward2 = tp2_price - price
        
        rr1 = reward1 / risk if risk > 0 else 0
        rr2 = reward2 / risk if risk > 0 else 0
        
        # סינון: אם RR1 < 1.5, לא נכנסים (גם אם זה נראה טוב)
        if rr1 < 1.5:
            print(f"[TradeManager] ⛔ {ticker} - RR1 ({rr1:.2f}) < 1.5. Skipping trade.")
            return None
        
        # --- 5. דירוג אמון (Confidence) ---
        confidence_pct = quality_score  # 0-100%
        stars = self._get_stars(confidence_pct)
        
        # --- 6. תוכנית Runner ---
        runner = quality_score >= 70  # Runner רק לאיכות גבוהה
        
        # --- 7. זמן יציאה מומלץ ---
        exit_time = "15 min before close"  # או דינמי לפי תנודתיות
        
        plan = {
            'ticker': ticker,
            'entry': price,
            'stop': stop_price,
            'tp1': tp1_price,
            'tp2': tp2_price,
            'runner': runner,
            'confidence': stars,
            'confidence_pct': round(confidence_pct, 1),
            'risk': round(risk, 3),
            'reward1': round(reward1, 3),
            'reward2': round(reward2, 3),
            'rr1': round(rr1, 2),
            'rr2': round(rr2, 2),
            'exit_time': exit_time,
            'quality_score': round(quality_score, 1),
            # שמירת הנתונים הגולמיים ללמידה עתידית
            'raw_data': {
                'score': candidate.get('score', 0),
                'rvol': candidate.get('rvol', 0),
                'gap': candidate.get('gap_pct', 0),
                'dvol': candidate.get('dollar_volume', 0),
                'pm_high': pm_high,
                'atr': atr,
                'catalyst': candidate.get('catalyst', '—')
            }
        }
        
        # שמירה אוטומטית להיסטוריית הלמידה
        self._save_trade_record(plan, candidate)
        
        return plan

    # --- 1. מנוע איכות משוקלל (Weighted Quality) ---
    def _calculate_weighted_score(self, c: Dict[str, Any]) -> float:
        """מחזיר ניקוד 0-100 לפי משקלים"""
        # Score (0-100) - כבר מנורמל
        score_val = min(100, max(0, c.get('score', 50)))
        
        # RVOL (1-10+)
        rvol = c.get('rvol', 1.0)
        rvol_val = min(100, (rvol / 5) * 100) if rvol > 0 else 0
        
        # PM High Distance (ככל שקרוב יותר לשיא - יותר טוב)
        pm_dist = c.get('pm_high_dist', 999)
        if pm_dist <= 1.0:
            pm_val = 100
        elif pm_dist <= 3.0:
            pm_val = 80
        elif pm_dist <= 5.0:
            pm_val = 60
        elif pm_dist <= 10.0:
            pm_val = 40
        else:
            pm_val = 20
        
        # Dollar Volume (נורמליזציה לוגריתמית)
        dvol = c.get('dollar_volume', 0)
        if dvol >= 10_000_000:
            dvol_val = 100
        elif dvol >= 5_000_000:
            dvol_val = 85
        elif dvol >= 1_000_000:
            dvol_val = 70
        elif dvol >= 500_000:
            dvol_val = 50
        else:
            dvol_val = 30
        
        # News (קטליזטור)
        catalyst = c.get('catalyst', '—')
        news_val = 70 if catalyst != '—' and 'fda' in catalyst.lower() or 'approval' in catalyst.lower() else 50
        
        # חישוב ממוצע משוקלל
        weighted = (
            (score_val * self.weights['score']) +
            (rvol_val * self.weights['rvol']) +
            (pm_val * self.weights['pm_high']) +
            (dvol_val * self.weights['dvol']) +
            (news_val * self.weights['news'])
        )
        return min(100, weighted)

    # --- 2. המרת אחוז אמון לכוכבים ---
    def _get_stars(self, confidence: float) -> str:
        if confidence >= 85:
            return "⭐⭐⭐⭐⭐"
        elif confidence >= 70:
            return "⭐⭐⭐⭐"
        elif confidence >= 55:
            return "⭐⭐⭐"
        elif confidence >= 40:
            return "⭐⭐"
        else:
            return "⭐"

    # --- 3. למידה אוטומטית (Probability Engine - Data Collector) ---
    def _save_trade_record(self, plan: Dict, candidate: Dict):
        """שומר את כל הנתונים הגולמיים ל-JSON בשביל Probability Engine עתידי"""
        record = {
            'timestamp': datetime.now().isoformat(),
            'ticker': plan['ticker'],
            'entry': plan['entry'],
            'stop': plan['stop'],
            'tp1': plan['tp1'],
            'tp2': plan['tp2'],
            'rr1': plan['rr1'],
            'rr2': plan['rr2'],
            'confidence': plan['confidence_pct'],
            'score': candidate.get('score', 0),
            'rvol': candidate.get('rvol', 0),
            'gap': candidate.get('gap_pct', 0),
            'dvol': candidate.get('dollar_volume', 0),
            'pm_high': candidate.get('pm_high', 0),
            'catalyst': candidate.get('catalyst', '—'),
            'quality_score': plan['quality_score'],
        }
        
        # קרא קובץ קיים או צור חדש
        history = []
        if os.path.exists(self.performance_log):
            try:
                with open(self.performance_log, 'r') as f:
                    history = json.load(f)
            except:
                history = []
        
        history.append(record)
        with open(self.performance_log, 'w') as f:
            json.dump(history, f, indent=2)

    # --- 4. פורמט טלגרם (UI) ---
    def get_trade_summary(self, plan: Dict[str, Any]) -> str:
        """מייצר הודעה נקיה לטלגרם"""
        lines = []
        lines.append(f"🎯 <b>{plan['ticker']}</b>  {plan['confidence']}  ({plan['confidence_pct']:.0f}%)")
        lines.append(f"💰 כניסה: ${plan['entry']:.2f}")
        lines.append(f"🛑 סטופ:  ${plan['stop']:.2f}  (-{((plan['entry']-plan['stop'])/plan['entry']*100):.1f}%)")
        lines.append(f"━━━━━━━━━━━━━━━━━━")
        lines.append(f"🎯 TP1:   ${plan['tp1']:.2f}  (+{((plan['tp1']/plan['entry'])-1)*100:.1f}%)  |  RR: {plan['rr1']:.2f}")
        lines.append(f"🎯 TP2:   ${plan['tp2']:.2f}  (+{((plan['tp2']/plan['entry'])-1)*100:.1f}%)  |  RR: {plan['rr2']:.2f}")
        lines.append(f"🏃 Runner: {'✅' if plan['runner'] else '❌'}")
        lines.append(f"⏰ יציאה מומלצת: {plan['exit_time']}")
        lines.append(f"📊 Quality Score: {plan['quality_score']:.0f}/100")
        lines.append(f"━━━━━━━━━━━━━━━━━━")
        return "\n".join(lines)
