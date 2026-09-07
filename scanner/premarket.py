"""
DAYS-BOT V4.3 – Premarket Discovery
"""
from datetime import datetime, time
from typing import List, Tuple
import pytz
import pandas as pd
import yfinance as yf
from scanner.universe import load_universe
from scanner.discovery_fast import fast_discovery
from utils.config import (
    DISCOVERY_MIN_PRICE,
    DISCOVERY_MAX_PRICE,
    DISCOVERY_MIN_GAP,
    DISCOVERY_MAX_GAP,
    DISCOVERY_MIN_VOLUME,
)

ET = pytz.timezone("America/New_York")
PM_START = time(4, 0)
PM_END = time(9, 30)


def _is_in_pm_window(now_et: datetime) -> bool:
    return PM_START <= now_et.time() < PM_END


def scan_premarket(target_date_str: str = None, manual: bool = False) -> Tuple[List[dict], dict]:
    now_et = datetime.now(ET)
    if not target_date_str:
        target_date_str = now_et.strftime("%Y-%m-%d")

    in_pm = _is_in_pm_window(now_et)
    print(f"[Discovery] Premarket scan for {target_date_str} | ET: {now_et.strftime('%H:%M:%S')} | PM window: {in_pm}")

    if not in_pm:
        print("[Discovery] Outside PM window – using Alpaca fast discovery.")
        candidates, diagnostics = fast_discovery()
        return candidates, diagnostics

    # PM window: use yfinance for premarket data
    universe = load_universe()
    if not universe:
        return [], {}

    # ... (keep existing PM logic) ...
    # For now, return fast_discovery as fallback
    return fast_discovery()
