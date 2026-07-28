"""
Trade Manager – converts scanner output into a trade plan
"""
from typing import Dict, Any, Optional
from datetime import datetime
import json
import os
import yfinance as yf

class TradeManager:
    def __init__(self, data_dir: str = "data"):
        self.data_dir = data_dir
        os.makedirs(data_dir, exist_ok=True)
        self.performance_log = os.path.join(data_dir, "trades_history.json")

    def get_market_regime(self) -> str:
        """
        מזהה את משטר השוק לפי התנהגות מדד SPY
        """
        try:
            spy = yf.Ticker("SPY")
            hist = spy.history(period="5d")
            if not hist.empty and len(hist) >= 2:
                pct_change = ((hist['Close'].iloc[-1] - hist['Close'].iloc[-2]) / hist['Close'].iloc[-2]) * 100
                if pct_change > 0.5:
                    return 'BULL'
                elif pct_change < -0.5:
                    return 'RISK_OFF'
        except Exception:
            pass
        return 'RANGE'

    def get_dynamic_weights() -> Dict[str, float]:
        """
        מחזירה משקלים דינמיים בהתאם למצב השוק (Regime)
        """
        regime = self.get_market_regime()
        if regime == 'BULL':
            return {'score': 0.45, 'rvol': 0.25, 'gap': 0.15, 'dvol': 0.10, 'news': 0.05}
        elif regime == 'RANGE':
            return {'score': 0.40, 'rvol': 0.25, 'gap': 0.15, 'dvol': 0.10, 'news': 0.10}
        else:  # RISK_OFF
            return {'score': 0.50, 'rvol': 0.20, 'gap': 0.10, 'dvol': 0.10, 'news': 0.10}

    def check_entry_trigger(self, candidate: Dict[str, Any]) -> bool:
        """
        בודק האם תנאי הכניסה מתקיימים:
        1. מחיר מעל Trigger (PM High + 0.5%)
        2. נפח עולה (לפחות לא במגמת ירידה)
        3. Relative Strength חיובי
        4. מחיר מעל VWAP (אם קים נתון)
        """
        ticker = candidate.get('ticker', '???')
        price = candidate.get('price', 0)
        pm_high = candidate.get('pm_high', price)
        trigger = candidate.get('trigger_price', round(pm_high * 1.005, 2))

        # 1. Trigger Price
        if price < trigger:
            print(f"[Trigger] {ticker}: Price ${price:.2f} < Trigger ${trigger:.2f}")
            return False

        # 2. Volume Trend
        vol_trend = candidate.get('volume_trend', 'rising')
        if vol_trend == 'declining':
            print(f"[Trigger] {ticker}: Volume declining")
            return False

        # 3. Relative Strength
        rs = candidate.get('relative_strength', 0)
        if isinstance(rs, (int, float)) and rs < 0:
            print(f"[Trigger] {ticker}: RS={rs:.1f} (negative)")
            return False

        # 4. VWAP
        vwap = candidate.get('vwap_est', 0)
        if isinstance(vwap, (int, float)) and vwap > 0 and price < vwap:
            print(f"[Trigger] {ticker}: Price ${price:.2f} < VWAP ${vwap:.2f}")
            return False

        return True

    def generate_plan(self, candidate: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """
        יוצר תוכנית מסחר דינמית.
        מחזיר None אם תנאי ה-Trigger או ה-Risk/Reward לא מתקיימים.
        """
        # --- 0. בדיקת Entry Trigger ---
        if not self.check_entry_trigger(candidate):
            ticker = candidate.get('ticker', '???')
            print(f"[TradeManager] ⛔ {ticker} - Entry trigger conditions not met. Skipping trade.")
            return None

        price = candidate.get('price', 0)
        ticker = candidate.get('ticker', '???')
        gap_pct = candidate.get('gap_pct', 0)

        # --- 1. חישוב איכות האות (Weighted Score) ---
        quality_score = self._calculate_weighted_score(candidate)

        # --- 2. סטופ דינמי (ATR או 5%) ---
        atr = candidate.get('atr', price * 0.04)
        stop_pct = max(0.05, (atr / price) * 1.5)
        stop_price = round(price * (1 - stop_pct), 2)

        # --- 3. TP1 מבוסס Gap + 3% ---
        tp1_pct = max(0.02, (gap_pct / 100) + 0.03)
        tp1_price = round(price * (1 + tp1_pct), 2)

        # --- 4. TP2 = TP1 + ATR ---
        tp2_price = round(tp1_price + atr, 2)

        # --- 5. Risk / Reward ---
        risk = price - stop_price
        reward1 = tp1_price - price
        reward2 = tp2_price - price

        rr1 = reward1 / risk if risk > 0 else 0
        rr2 = reward2 / risk if risk > 0 else 0

        # סינון: RR1 < 1.0 → לא נכנסים
        if rr1 < 1.0:
            print(f"[TradeManager] ⛔ {ticker} - RR1 ({rr1:.2f}) < 1.0. Skipping trade.")
            return None

        # --- 6. Confidence ---
        confidence_pct = quality_score
        stars = self._get_stars(confidence_pct)

        # --- 7. Runner ---
        runner = quality_score >= 70

        # --- 8. Trigger (BREAKOUT) ---
        pm_high = candidate.get('pm_high', price)
        trigger_price = candidate.get('trigger_price', round(pm_high * 1.005, 2))

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
            'exit_time': "15 min before close",
            'quality_score': round(quality_score, 1),
            'trigger': trigger_price,
            'raw_data': {
                'score': candidate.get('score', 0),
                'rvol': candidate.get('rvol', 0),
                'gap': gap_pct,
                'dvol': candidate.get('dollar_volume', 0),
                'atr': atr,
                'catalyst': candidate.get('catalyst', '—')
            }
        }

        self._save_trade_record(plan, candidate)
        return plan

    def _calculate_weighted_score(self, c: Dict[str, Any]) -> float:
        weights = self.get_dynamic_weights()

        score_val = min(100, max(0, c.get('score', 50)))

        rvol = c.get('rvol', 1.0)
        rvol_val = min(100, (rvol / 5) * 100) if rvol > 0 else 0

        gap = c.get('gap_pct', 0)
        gap_val = min(100, gap * 10)

        dvol = c.get('dollar_volume', 0)
        if dvol >= 10_000_000: dvol_val = 100
        elif dvol >= 5_000_000: dvol_val = 85
        elif dvol >= 1_000_000: dvol_val = 70
        elif dvol >= 500_000: dvol_val = 50
        else: dvol_val = 30

        catalyst = c.get('catalyst', '—')
        news_val = 70 if 'fda' in catalyst.lower() or 'approval' in catalyst.lower() else 50

        weighted = (
            (score_val * weights['score']) +
            (rvol_val * weights['rvol']) +
            (gap_val * weights['gap']) +
            (dvol_val * weights['dvol']) +
            (news_val * weights['news'])
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
        print(f"[TradeManager] ✅ Saved trade record for {plan['ticker']}")

    def get_trade_summary(self, plan: Dict[str, Any]) -> str:
        lines = []
        lines.append(f"🎯 <b>{plan['ticker']}</b>  {plan['confidence']}  ({plan['confidence_pct']:.0f}%)")
        lines.append(f"💰 כניסה: ${plan['entry']:.2f}")
        lines.append(f"🛑 סטופ:  ${plan['stop']:.2f}  (-{((plan['entry']-plan['stop'])/plan['entry']*100):.1f}%)")
        lines.append(f"⚡ Trigger: ${plan['trigger']:.2f} (BREAKOUT)")
        lines.append(f"━━━━━━━━━━━━━━━━━━")
        lines.append(f"🎯 TP1:   ${plan['tp1']:.2f}  (+{((plan['tp1']/plan['entry'])-1)*100:.1f}%)  |  RR: {plan['rr1']:.2f}")
        lines.append(f"🎯 TP2:   ${plan['tp2']:.2f}  (+{((plan['tp2']/plan['entry'])-1)*100:.1f}%)  |  RR: {plan['rr2']:.2f}")
        lines.append(f"🏃 Runner: {'✅' if plan['runner'] else '❌'}")
        lines.append(f"⏰ יציאה מומלצת: {plan['exit_time']}")
        lines.append(f"📊 Quality Score: {plan['quality_score']:.0f}/100")
        lines.append(f"━━━━━━━━━━━━━━━━━━")
        return "\n".join(lines)
