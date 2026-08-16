"""
Live market data engine.

מקבל רשימת טיקרים ומחזיר Snapshot עדכני מ-Alpaca.
"""

from typing import List, Dict, Any
import alpaca_trade_api as tradeapi

from utils.config import ALPACA_API_KEY, ALPACA_SECRET_KEY


class LiveDataEngine:

    def __init__(self):
        self.api = tradeapi.REST(
            ALPACA_API_KEY,
            ALPACA_SECRET_KEY,
            base_url="https://paper-api.alpaca.markets"
        )

    def get_snapshots(
        self,
        candidates: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:

        if not candidates:
            return []

        symbols = [
            c["ticker"]
            for c in candidates
            if c.get("ticker")
        ]

        try:
            snapshots = self.api.get_snapshots(symbols)
        except Exception as e:
            print(f"[LiveData] Snapshot error: {e}")
            return []

        results = []

        for candidate in candidates:

            ticker = candidate["ticker"]

            try:
                snapshot = snapshots.get(ticker)

                if not snapshot:
                    print(f"[LiveData] No snapshot: {ticker}")
                    continue

                latest_trade = getattr(
                    snapshot,
                    "latest_trade",
                    None
                )

                latest_quote = getattr(
                    snapshot,
                    "latest_quote",
                    None
                )

                daily_bar = getattr(
                    snapshot,
                    "daily_bar",
                    None
                )

                prev_bar = getattr(
                    snapshot,
                    "prev_daily_bar",
                    None
                )

                price = (
                    float(latest_trade.price)
                    if latest_trade
                    and getattr(latest_trade, "price", None)
                    else candidate["price"]
                )

                bid = (
                    float(latest_quote.bid_price)
                    if latest_quote
                    and getattr(latest_quote, "bid_price", None)
                    else 0.0
                )

                ask = (
                    float(latest_quote.ask_price)
                    if latest_quote
                    and getattr(latest_quote, "ask_price", None)
                    else 0.0
                )

                volume = (
                    float(daily_bar.volume)
                    if daily_bar
                    else 0.0
                )

                prev_close = (
                    float(prev_bar.close)
                    if prev_bar
                    else 0.0
                )

                if prev_close > 0:
                    live_gap = (
                        (price - prev_close)
                        / prev_close
                    ) * 100
                else:
                    live_gap = candidate["gap_pct"]

                if bid > 0 and ask > 0 and price > 0:
                    spread_pct = (
                        (ask - bid) / price
                    ) * 100
                else:
                    spread_pct = None

                pm_high = (
                    float(daily_bar.high)
                    if daily_bar
                    else price
                )

                dollar_volume = price * volume

                # בסיס RVOL זמני.
                # בשלב הבא נחליף אותו ב-time-adjusted RVOL.
                if prev_bar and getattr(prev_bar, "volume", 0):
                    rvol = (
                        volume /
                        float(prev_bar.volume)
                    )
                else:
                    rvol = 0.0

                result = dict(candidate)

                result.update({
                    "live_price": price,
                    "live_gap_pct": live_gap,
                    "bid": bid,
                    "ask": ask,
                    "spread_pct": spread_pct,
                    "volume": volume,
                    "dollar_volume": dollar_volume,
                    "pm_high": pm_high,
                    "rvol": rvol,
                    "prev_close": prev_close,
                })

                results.append(result)

            except Exception as e:
                print(
                    f"[LiveData] Error {ticker}: {e}"
                )

        print(
            f"[LiveData] Validated "
            f"{len(results)}/{len(candidates)} candidates"
        )

        return results
