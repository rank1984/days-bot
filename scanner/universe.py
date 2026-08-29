"""
DAYS-BOT V3.0 – Universe Loader & Filter
"""

from typing import List
from alpaca_trade_api.rest import REST
from utils.config import (
    ALPACA_API_KEY,
    ALPACA_BASE_URL,
    ALPACA_SECRET_KEY,
)


def load_universe() -> List[str]:
    """
    Fetches active tradable US equities from Alpaca and filters out
    unwanted instruments (warrants, rights, preferred shares, etc.).
    """
    print("[Universe] Fetching from Alpaca (filtering)...")

    try:
        api = REST(
            ALPACA_API_KEY,
            ALPACA_SECRET_KEY,
            ALPACA_BASE_URL,
            api_version="v2",
        )

        assets = api.list_assets(status="active", asset_class="us_equity")
        print(f"[Universe] Raw stocks fetched: {len(assets):,}")

        filtered_universe = []

        for asset in assets:
            # בדיקת תקינות בסיסית - tradable ו-shortable במידת הצורך
            if not getattr(asset, "tradable", False):
                continue

            symbol = getattr(asset, "symbol", "")
            if not symbol:
                continue

            # גישה בטוחה לשם הנכס למניעת AttributeError
            name = getattr(asset, "name", "") or ""
            name_lower = name.lower()

            # סינון סוגי ניירות ערך לא רצויים
            if any(
                keyword in name_lower
                for keyword in ["warrant", "right", "unit", "preferred", "etf", "fund"]
            ):
                continue

            # סינון סימולים עם נקודה/מקף (זכויות/מניות בכורות)
            if "." in symbol or "-" in symbol:
                continue

            filtered_universe.append(symbol)

        print(f"[Universe] Filtered universe count: {len(filtered_universe):,}")
        return filtered_universe

    except Exception as e:
        print(f"[Universe] Error: {e}")
        return []
