import yfinance as yf
import pandas as pd
import numpy as np
from datetime import datetime

class RiskEngine:
    def __init__(self, alpaca_client=None, account_size=5000.0, base_risk_pct=0.005):
        """
        account_size: $5,000 default for Paper Trading
        base_risk_pct: 0.5% max risk per trade
        """
        self.alpaca = alpaca_client
        self.account_size = account_size
        self.base_risk_pct = base_risk_pct

    def get_market_regime(self):
        """ Fetch SPY, IWM, VIX to determine market regime """
        try:
            tickers = yf.download("SPY IWM VIX", period="2d", interval="1d", progress=False)['Close']
            
            # Simple momentum calculation (today vs yesterday)
            spy_change = (tickers['SPY'].iloc[-1] - tickers['SPY'].iloc[-2]) / tickers['SPY'].iloc[-2]
            iwm_change = (tickers['IWM'].iloc[-1] - tickers['IWM'].iloc[-2]) / tickers['IWM'].iloc[-2]
            vix_level = tickers['VIX'].iloc[-1]
            
            score = 0
            if iwm_change > 0: score += 40
            if spy_change > 0: score += 30
            if vix_level < 20: score += 30

            if score >= 70:
                return "FAVORABLE", 1.0, f"IWM: {iwm_change:.2%}, SPY: {spy_change:.2%}, VIX: {vix_level:.2f}"
            elif score >= 40:
                return "NEUTRAL", 0.5, f"IWM: {iwm_change:.2%}, SPY: {spy_change:.2%}, VIX: {vix_level:.2f}"
            else:
                return "HOSTILE", 0.0, f"IWM: {iwm_change:.2%}, SPY: {spy_change:.2%}, VIX: {vix_level:.2f}"
        except Exception as e:
            print(f"[RiskEngine] Failed to fetch market regime: {e}")
            return "NEUTRAL", 0.5, "Data unavailable"

    def calculate_trade_plan(self, price, pm_high, pm_vwap, regime_multiplier):
        """ Math-based Trade Plan Calculation """
        trigger = pm_high + 0.01  # Breakout trigger
        entry_min = trigger
        entry_max = trigger * 1.01 # 1% slippage allowance
        
        # Stop loss logic (Use VWAP or max 5% drop to protect capital)
        stop_price = min(pm_vwap, entry_min * 0.95)
        
        risk_per_share = entry_min - stop_price
        if risk_per_share <= 0.0:
            risk_per_share = entry_min * 0.02 # fallback to 2% risk
            stop_price = entry_min - risk_per_share

        # Targets (1:2 and 1:3 Reward/Risk)
        t1 = entry_min + (risk_per_share * 2)
        t2 = entry_min + (risk_per_share * 3)

        # Position Sizing
        max_dollar_risk = self.account_size * self.base_risk_pct * regime_multiplier
        if max_dollar_risk == 0:
            shares = 0
        else:
            shares = int(max_dollar_risk // risk_per_share)

        return {
            "trigger": round(trigger, 2),
            "entry_min": round(entry_min, 2),
            "entry_max": round(entry_max, 2),
            "stop": round(stop_price, 2),
            "t1": round(t1, 2),
            "t2": round(t2, 2),
            "risk_dollar": round(max_dollar_risk, 2),
            "shares": shares
        }
