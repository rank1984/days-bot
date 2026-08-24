"""
backtest_candidates.py
=======================
Replays candidates already saved in alerts.db (watchlist table) against
REAL historical intraday price data, to answer the only question that
actually matters right now: does this signal have positive expectancy?

IMPORTANT - run this locally, not in a sandbox:
This script needs live/historical market data (yfinance or Alpaca).
Plug in ONE of the two fetch functions below (marked TODO) with your
own credentials before running.

KEY FIX applied here vs. the current watchlist_manager.py:
  Entry  = pm_high * 1.005            (NOT current price * anything)
  Stop   = Entry * 0.95
  TP1    = Entry * 1.06
  TP2    = Entry * 1.12
This matches the original strategy doc. The live code currently anchors
stop/tp1/tp2 to `price` instead of `trigger_price` (entry) - fix that in
watchlist_manager.py too, this script does NOT patch your live DB.

Usage:
    python backtest_candidates.py --db data/alerts.db --days 30 --out results.csv
"""

import argparse
import sqlite3
import sys
from dataclasses import dataclass, asdict
from datetime import datetime, timedelta
from typing import Optional, List, Dict, Any

# ──────────────────────────────────────────────────────────────────
# 1. DATA SOURCE — plug in your real market data provider here
# ──────────────────────────────────────────────────────────────────

def fetch_intraday_bars(ticker: str, date: str) -> Optional[List[Dict[str, Any]]]:
    """
    Returns 1-minute bars for `ticker` on `date` (YYYY-MM-DD), from
    market open (09:30 ET) through end of day, as a list of dicts:
        [{"time": "09:30", "open": .., "high": .., "low": .., "close": .., "volume": ..}, ...]

    TODO: implement with your provider. Two starting points below.
    """

    # ---- Option A: yfinance (free, rate-limited, ok for research) ----
    # import yfinance as yf
    # start = datetime.strptime(date, "%Y-%m-%d")
    # end = start + timedelta(days=1)
    # df = yf.download(ticker, start=start, end=end, interval="1m", prepost=True)
    # if df.empty:
    #     return None
    # bars = []
    # for ts, row in df.iterrows():
    #     bars.append({
    #         "time": ts.strftime("%H:%M"),
    #         "open": float(row["Open"]), "high": float(row["High"]),
    #         "low": float(row["Low"]), "close": float(row["Close"]),
    #         "volume": float(row["Volume"]),
    #     })
    # return bars

    # ---- Option B: Alpaca (better PM data quality, needs API key) ----
    # from alpaca.data.historical import StockHistoricalDataClient
    # from alpaca.data.requests import StockBarsRequest
    # from alpaca.data.timeframe import TimeFrame
    # client = StockHistoricalDataClient(API_KEY, API_SECRET)
    # req = StockBarsRequest(symbol_or_symbols=ticker, timeframe=TimeFrame.Minute,
    #                         start=date, end=date)
    # bars_resp = client.get_stock_bars(req)
    # ... convert to the same dict format ...

    raise NotImplementedError(
        "Plug in yfinance or Alpaca here before running. "
        "See the commented-out options above."
    )


# ──────────────────────────────────────────────────────────────────
# 2. TRADE SIMULATION
# ──────────────────────────────────────────────────────────────────

@dataclass
class TradeResult:
    ticker: str
    date: str
    price_at_signal: float
    pm_high: float
    entry: float
    stop: float
    tp1: float
    tp2: float
    triggered: bool
    time_to_trigger_min: Optional[int]
    mfe_pct: Optional[float]
    mae_pct: Optional[float]
    hit_stop_first: Optional[bool]
    hit_tp1_first: Optional[bool]
    hit_tp2_first: Optional[bool]
    exit_price: Optional[float]
    gross_r: Optional[float]
    net_r: Optional[float]
    valid: bool = True
    exclusion_reason: str = ""
    note: str = ""


# Cost model — adjust to your real numbers (commission + IL capital gains tax)
COMMISSION_PCT = 0.0005   # 0.05% round trip, EDIT to your broker's real rate
TAX_PCT_ON_GAIN = 0.25    # Israeli capital gains tax, applied only on positive net gain


def simulate_trade(candidate: Dict[str, Any], bars: List[Dict[str, Any]]) -> TradeResult:
    ticker = candidate["ticker"]
    date = candidate["added_time"][:10]
    price_at_signal = float(candidate["price"])

    # ── NO SILENT FALLBACK ──
    # If pm_high is missing/zero/null, this candidate never had real PM data.
    # Excluding it from the valid backtest rather than pretending
    # pm_high == price_at_signal (which would fabricate PM Dist = 0%).
    raw_pm_high = candidate.get("pm_high")
    if raw_pm_high is None or float(raw_pm_high) <= 0:
        return TradeResult(ticker, date, price_at_signal, 0.0, 0.0, 0.0, 0.0, 0.0,
                            False, None, None, None, None, None, None, None, None, None,
                            valid=False, exclusion_reason="PM_HIGH_MISSING",
                            note="excluded: no real PM data, refusing to fabricate pm_high=price")
    pm_high = float(raw_pm_high)

    # ── Entry/Stop/TP — anchored to ENTRY (trigger_price), not signal price ──
    entry = round(pm_high * 1.005, 4)
    stop = round(entry * 0.95, 4)
    tp1 = round(entry * 1.06, 4)
    tp2 = round(entry * 1.12, 4)

    spread_pct = candidate.get("spread_pct")
    spread_note = "SPREAD_UNKNOWN" if spread_pct is None else f"spread={spread_pct}%"
    catalyst_status = "UNKNOWN" if not candidate.get("catalyst") or candidate.get("catalyst") in ("—", "N/A") else "AVAILABLE"

    if not bars:
        return TradeResult(ticker, date, price_at_signal, pm_high, entry, stop, tp1, tp2,
                            False, None, None, None, None, None, None, None, None,
                            valid=True, exclusion_reason="",
                            note=f"no bar data | {spread_note} | catalyst={catalyst_status}")

    triggered = False
    trigger_idx = None
    for i, bar in enumerate(bars):
        if bar["high"] >= entry:
            triggered = True
            trigger_idx = i
            break

    if not triggered:
        return TradeResult(ticker, date, price_at_signal, pm_high, entry, stop, tp1, tp2,
                            False, None, None, None, None, None, None, None, None,
                            valid=True, exclusion_reason="",
                            note=f"never triggered entry | {spread_note} | catalyst={catalyst_status}")

    post_entry_bars = bars[trigger_idx:]
    highs = [b["high"] for b in post_entry_bars]
    lows = [b["low"] for b in post_entry_bars]
    mfe_pct = round((max(highs) - entry) / entry * 100, 2)
    mae_pct = round((min(lows) - entry) / entry * 100, 2)

    hit_stop_first = hit_tp1_first = hit_tp2_first = False
    exit_price = None
    for bar in post_entry_bars:
        if bar["low"] <= stop:
            hit_stop_first = True
            exit_price = stop
            break
        if bar["high"] >= tp2:
            hit_tp2_first = True
            exit_price = tp2
            break
        if bar["high"] >= tp1:
            hit_tp1_first = True
            exit_price = tp1
            break

    if exit_price is None:
        # never hit stop/tp1/tp2 by end of data — mark-to-close
        exit_price = post_entry_bars[-1]["close"]

    gross_r = round((exit_price - entry) / (entry - stop), 3) if (entry - stop) != 0 else None

    # net R after commission + tax on gains only
    gross_pct_gain = (exit_price - entry) / entry
    net_pct_gain = gross_pct_gain - COMMISSION_PCT
    if net_pct_gain > 0:
        net_pct_gain *= (1 - TAX_PCT_ON_GAIN)
    net_r = round((net_pct_gain * entry) / (entry - stop), 3) if (entry - stop) != 0 else None

    return TradeResult(
        ticker, date, price_at_signal, pm_high, entry, stop, tp1, tp2,
        True, trigger_idx, mfe_pct, mae_pct,
        hit_stop_first, hit_tp1_first, hit_tp2_first,
        round(exit_price, 4), gross_r, net_r,
        valid=True, exclusion_reason="",
        note=f"{spread_note} | catalyst={catalyst_status}",
    )


# ──────────────────────────────────────────────────────────────────
# 3. DB READ
# ──────────────────────────────────────────────────────────────────

def load_candidates(db_path: str, days: int) -> List[Dict[str, Any]]:
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    cutoff = (datetime.now() - timedelta(days=days)).isoformat()
    cur = conn.execute(
        "SELECT * FROM watchlist WHERE added_time > ? ORDER BY added_time", (cutoff,)
    )
    rows = [dict(r) for r in cur.fetchall()]
    conn.close()
    return rows


# ──────────────────────────────────────────────────────────────────
# 4. MAIN
# ──────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--db", default="data/alerts.db")
    parser.add_argument("--days", type=int, default=30)
    parser.add_argument("--out", default="backtest_results.csv")
    args = parser.parse_args()

    candidates = load_candidates(args.db, args.days)
    if not candidates:
        print("No candidates found in the given window. Nothing to backtest.")
        sys.exit(0)

    print(f"Loaded {len(candidates)} candidates. Fetching bars and simulating...")

    results: List[TradeResult] = []
    for c in candidates:
        date = c["added_time"][:10]
        try:
            bars = fetch_intraday_bars(c["ticker"], date)
        except NotImplementedError as e:
            print(str(e))
            sys.exit(1)
        result = simulate_trade(c, bars)
        results.append(result)
        print(f"  {result.ticker} ({result.date}): triggered={result.triggered} "
              f"net_r={result.net_r} note={result.note}")

    # ── Write CSV ──
    import csv
    with open(args.out, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=list(asdict(results[0]).keys()))
        writer.writeheader()
        for r in results:
            writer.writerow(asdict(r))

    # ── Summary stats ──
    excluded = [r for r in results if not r.valid]
    valid_results = [r for r in results if r.valid]
    triggered = [r for r in valid_results if r.triggered and r.net_r is not None]
    n_total = len(results)
    n_excluded = len(excluded)
    n_triggered = len(triggered)
    n_wins = sum(1 for r in triggered if r.net_r > 0)
    n_losses = sum(1 for r in triggered if r.net_r <= 0)
    win_rate = round(n_wins / n_triggered * 100, 1) if n_triggered else 0
    avg_r = round(sum(r.net_r for r in triggered) / n_triggered, 3) if n_triggered else 0
    gross_win = sum(r.net_r for r in triggered if r.net_r > 0)
    gross_loss = abs(sum(r.net_r for r in triggered if r.net_r <= 0))
    profit_factor = round(gross_win / gross_loss, 2) if gross_loss > 0 else float("inf")

    print("\n" + "=" * 50)
    print(f"Total candidates:     {n_total}")
    print(f"Excluded (bad data):  {n_excluded}")
    if excluded:
        reasons = {}
        for r in excluded:
            reasons[r.exclusion_reason] = reasons.get(r.exclusion_reason, 0) + 1
        for reason, count in reasons.items():
            print(f"    - {reason}: {count}")
    print(f"Valid candidates:     {len(valid_results)}")
    print(f"Triggered entry:      {n_triggered} ({round(n_triggered/len(valid_results)*100,1) if valid_results else 0}%)")
    print(f"Wins / Losses:        {n_wins} / {n_losses}")
    print(f"Win rate:             {win_rate}%")
    print(f"Avg net R:            {avg_r}")
    print(f"Profit factor:        {profit_factor}")
    print(f"Results saved to:     {args.out}")
    print("=" * 50)


if __name__ == "__main__":
    main()
