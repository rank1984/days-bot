"""
AI Quant Agent V1 - Live Market Data

מביא Snapshot חי לכל מועמד של DAYS-BOT.

מקור הנתונים:
Alpaca
"""

import sys
from pathlib import Path
from typing import Dict, Any, List

import alpaca_trade_api as tradeapi

BASE_DIR = Path(__file__).resolve().parent.parent

sys.path.insert(0, str(BASE_DIR))
sys.path.insert(0, str(BASE_DIR / "utils"))

from utils.config import ALPACA_API_KEY, ALPACA_SECRET_KEY


class LiveDataEngine:

    def __init__(self):
        self.api = tradeapi.REST(
            ALPACA_API_KEY,
            ALPACA_SECRET_KEY,
            base_url="https://paper-api.alpaca.markets"
        )

    def get_snapshots(self, symbols: List[str]) -> Dict[str, Any]:
        """
        Get Alpaca snapshots for multiple symbols.
        """

        if not symbols:
            return {}

        try:
            return self.api.get_snapshots(symbols)
        except Exception as e:
            print(f"[AI LiveData] Snapshot error: {e}")
            return {}

    @staticmethod
    def _safe_float(value, default=0.0):
        try:
            if value is None:
                return default
            return float(value)
        except (TypeError, ValueError):
            return default

    def build_snapshot(
        self,
        ticker: str,
        snapshot: Any,
        days_data: Dict[str, Any]
    ) -> Dict[str, Any]:

        if snapshot is None:
            return {
                **days_data,
                "ticker": ticker,
                "data_ok": False,
                "rejection_reason": "NO_SNAPSHOT"
            }

        latest_trade = getattr(snapshot, "latest_trade", None)
        latest_quote = getattr(snapshot, "latest_quote", None)

        price = self._safe_float(
            getattr(latest_trade, "price", None),
            days_data.get("price", 0)
        )

        bid = self._safe_float(
            getattr(latest_quote, "bid_price", None)
        )

        ask = self._safe_float(
            getattr(latest_quote, "ask_price", None)
        )

        daily_bar = getattr(snapshot, "daily_bar", None)
        prev_bar = getattr(snapshot, "prev_daily_bar", None)

        volume = self._safe_float(
            getattr(daily_bar, "volume", None)
        )

        prev_volume = self._safe_float(
            getattr(prev_bar, "volume", None)
        )

        day_high = self._safe_float(
            getattr(daily_bar, "high", None),
            price
        )

        day_low = self._safe_float(
            getattr(daily_bar, "low", None),
            price
        )

        prev_close = self._safe_float(
            getattr(prev_bar, "close", None)
        )

        # Spread
        spread_pct = 0.0

        if bid > 0 and ask > 0 and ask >= bid:
            midpoint = (bid + ask) / 2

            if midpoint > 0:
                spread_pct = ((ask - bid) / midpoint) * 100

        # RVOL V1
        #
        # חשוב:
        # זה עדיין אינו PM-RVOL היסטורי אמיתי.
        # בשלב הבא נחליף אותו במנוע PM-RVOL.
        rvol = 1.0

        if prev_volume > 0:
            rvol = volume / prev_volume

        dollar_volume = price * volume

        # Distance from PM/day high
        pm_high = max(day_high, price)

        distance_to_high_pct = 0.0

        if pm_high > 0 and pm_high >= price:
            distance_to_high_pct = (
                (pm_high - price) / pm_high
            ) * 100

        # VWAP approximation
        #
        # V1:
        # אין לנו עדיין סדרת trades מלאה.
        # משתמשים ב-Typical Price כקירוב בלבד.
        vwap_est = (
            (day_high + day_low + price) / 3
        )

        return {
            **days_data,

            "ticker": ticker,

            "live_price": price,
            "bid": bid,
            "ask": ask,

            "spread_pct": spread_pct,

            "volume": volume,
            "prev_volume": prev_volume,
            "dollar_volume": dollar_volume,

            "rvol": rvol,

            "pm_high": pm_high,
            "pm_low": day_low,
            "distance_to_high_pct": distance_to_high_pct,

            "vwap": vwap_est,

            "prev_close": prev_close,

            "data_ok": True,
            "rejection_reason": None,
        }

    def enrich_candidates(
        self,
        candidates: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:

        if not candidates:
            return []

        symbols = [
            c["ticker"]
            for c in candidates
        ]

        snapshots = self.get_snapshots(symbols)

        enriched = []

        for candidate in candidates:

            ticker = candidate["ticker"]

            snapshot = snapshots.get(ticker)

            data = self.build_snapshot(
                ticker,
                snapshot,
                candidate
            )

            enriched.append(data)

        return enriched
