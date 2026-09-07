"""
DAYS-BOT V4.3 – Float Analyzer
Uses Financial Modeling Prep API (FMP) for Float, Short Interest.
"""

import requests
from utils.config import FMP_API_KEY

FMP_BASE_URL = "https://financialmodelingprep.com/api/v3"

# Fallback if FMP fails or no key
STATIC_FLOAT = {
    "AAPL": 15_000_000_000,
    "MSFT": 7_400_000_000,
    "NVDA": 2_400_000_000,
    "AMD": 1_600_000_000,
    "AMZN": 10_000_000_000,
    # ... add more as needed
}


def _get_from_fmp(endpoint: str, params: dict) -> dict:
    """Generic FMP API caller"""
    if not FMP_API_KEY:
        return {}
    try:
        url = f"{FMP_BASE_URL}/{endpoint}"
        params["apikey"] = FMP_API_KEY
        resp = requests.get(url, params=params, timeout=10)
        if resp.status_code == 200:
            data = resp.json()
            if data:
                return data[0] if isinstance(data, list) else data
        return {}
    except Exception as e:
        print(f"[Float] FMP error: {e}")
        return {}


def get_float_and_short(ticker: str) -> dict:
    """
    Fetch Float and Short Interest from FMP.
    Returns: {"float": float, "short_interest": float, "short_ratio": float, "status": str}
    """
    result = {
        "float": None,
        "short_interest": None,
        "short_ratio": None,
        "status": "UNAVAILABLE",
        "source": "fmp"
    }

    # Try FMP first
    if FMP_API_KEY:
        try:
            # 1. Get company profile (includes float)
            profile = _get_from_fmp("profile", {"symbol": ticker})
            if profile:
                result["float"] = profile.get("sharesOutstanding")  # or float
                result["status"] = "SUCCESS"
                result["source"] = "fmp_profile"

            # 2. Get short interest
            short_data = _get_from_fmp("short-interest", {"symbol": ticker})
            if short_data:
                result["short_interest"] = short_data.get("shortPercent")  # as decimal
                result["short_ratio"] = short_data.get("shortRatio")
                result["status"] = "SUCCESS"
                result["source"] = "fmp_short"

        except Exception as e:
            print(f"[Float] FMP request error: {e}")

    # Fallback: static list
    if result["float"] is None:
        result["float"] = STATIC_FLOAT.get(ticker)
        if result["float"]:
            result["status"] = "STATIC_FALLBACK"
            result["source"] = "static"

    return result
