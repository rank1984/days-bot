"""
Trade Manager – Dynamic Trade Plan Generator
Based on Real Data (Gap, ATR, Weighted Score) with Risk/Reward Filter
"""
import math
from typing import Dict, Any, Optional
from datetime import datetime
import json
import os

class TradeManager:
    # ✅ שלב 1: הוספת תמיכה ב-paper=True
    def __init__(self, data_dir: str = "data", paper: bool = False):
        self.data_dir = data_dir
        self.paper = paper
        os.makedirs(data_dir, exist_ok=True)
        self.performance_log = os.path.join(data_dir, "trades_history.json")
        
        self.weights = {
            'score': 0.40,
            'price_strength': 0.20,
            'pm_high': 0.15,
            'rvol': 0.10,
            'dvol': 0.10,
            'news': 0.05
        }

    def generate_plan(self, candidate: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        price = candidate.get('price', 0)
        ticker = candidate.get('ticker', '???')
        gap_pct = candidate.get('gap_pct', 0)
        
        quality_score = self._calculate_weighted_score(candidate)
        
        atr = candidate.get('atr', price * 0.04)
        stop_price = round(price - atr, 2)
        tp1_price = round(price + atr, 2)
        tp2_price = round(price + atr * 2, 2)
        
        risk = price - stop_price
        reward1 = tp1_price - price
        reward2 = tp2_price - price
        
        rr1 = reward1 / risk if risk > 0 else 0
        rr2 = reward2 / risk if risk > 0 else 0
        
        # ✅ שלב 2: סף RR הורד ל-1.0
        if rr1 < 1.0:
            print(f"[TradeManager] ⛔ {ticker} - RR1 ({rr1:.2f}) < 1.0. Skipping trade.")
            return None
        
        confidence_pct = quality_score
        stars = self._get_stars(confidence_pct)
        runner = quality_score >= 70
        
        pm_high = candidate.get('pm_high', price)
        trigger_price = round(pm_high * 1.005, 2)
        
        plan = {
            'ticker': ticker,
            'trigger': trigger_price,
            'entry_type': 'BREAKOUT',
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
            'exit_time': "15 min before close",
            'quality_score': round(quality_score, 1),
            'paper_trade': self.paper, # סימון שהעסקה היא בדמו
            'raw_data': {
                'score': candidate.get('score', 0),
                'rvol': candidate.get('rvol', 0),
                'gap': gap_pct,
                'dvol': candidate.get('dollar_volume', 0),
                'atr': atr,
                'catalyst': candidate.get('catalyst', '—'),
                'pm_high_dist': candidate.get('pm_high_dist', 0),
                'news_score': candidate.get('news_score', 0)
            }
        }
        
        self._save_trade_record(plan, candidate)
        return plan

    def _calculate_weighted_score(self, c: Dict[str, Any]) -> float:
        score_val = min(100, max(0, c.get('score', 50)))
        
        rvol = c.get('rvol', 1.0)
        rvol_val = min(100, (rvol / 5) * 100) if rvol > 0 else 0
        
        price_strength = min(100, c.get('gap_pct', 0) * 10)
        
        pm_high_dist = c.get('pm_high_dist', 0)
        pm_high_val = max(0, 100 - (pm_high_dist * 10))
        
        dvol = c.get('dollar_volume', 0)
        if dvol >= 10_000_000: dvol_val = 100
        elif dvol >= 5_000_000: dvol_val = 85
        elif dvol >= 1_000_000: dvol_val = 70
        elif dvol >= 500_000: dvol_val = 50
        else: dvol_val = 30
        
        catalyst = c.get('catalyst', '—')
        news_val = 70 if 'fda' in catalyst.lower() or 'approval' in catalyst.lower() else 50
        
        weighted = (
            (score_val * self.weights['score']) +
            (price_strength * self.weights['price_strength']) +
            (pm_high_val * self.weights['pm_high']) +
            (rvol_val * self.weights['rvol']) +
            (dvol_val * self.weights['dvol']) +
            (news_val * self.weights['news'])
        )
        return min(100, weighted)

    def _get_stars(self, confidence: float) -> str:
        if confidence >= 85: return "⭐⭐⭐⭐⭐"
        elif confidence >= 70: return "⭐⭐⭐⭐"
        elif confidence >= 55: return "⭐⭐⭐"
        elif confidence >= 40: return "⭐⭐"
        else: return "⭐"

    def _save_trade_record(self, plan: Dict, candidate: Dict):
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
            'catalyst': candidate.get('catalyst', '—'),
            'quality_score': plan['quality_score'],
            'paper_trade': plan['paper_trade']
        }
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

    def get_trade_summary(self, plan: Dict[str, Any]) -> str:
        lines = []
        mode = "🧪 PAPER TRADE" if plan.get('paper_trade') else "💵 REAL TRADE"
        lines.append(f"🎯 <b>{plan['ticker']}</b>  {plan['confidence']}  ({plan['confidence_pct']:.0f}%) - {mode}")
        lines.append(f"💰 כניסה: ${plan['entry']:.2f}")
        lines.append(f"⚡ Trigger: ${plan['trigger']:.2f} (BREAKOUT)")
        lines.append(f"🛑 סטופ:  ${plan['stop']:.2f}  (-{((plan['entry']-plan['stop'])/plan['entry']*100):.1f}%)")
        lines.append(f"━━━━━━━━━━━━━━━━━━")
        lines.append(f"🎯 TP1:   ${plan['tp1']:.2f}  (+{((plan['tp1']/plan['entry'])-1)*100:.1f}%)  |  RR: {plan['rr1']:.2f}")
        lines.append(f"🎯 TP2:   ${plan['tp2']:.2f}  (+{((plan['tp2']/plan['entry'])-1)*100:.1f}%)  |  RR: {plan['rr2']:.2f}")
        lines.append(f"🏃 Runner: {'✅' if plan['runner'] else '❌'}")
        lines.append(f"⏰ יציאה מומלצת: {plan['exit_time']}")
        lines.append(f"📊 Quality Score: {plan['quality_score']:.0f}/100")
        lines.append(f"━━━━━━━━━━━━━━━━━━")
        return "\n".join(lines)
