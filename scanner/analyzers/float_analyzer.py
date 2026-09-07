"""
DAYS-BOT V4.3 – Float Analyzer
Uses Financial Modeling Prep API (FMP) for Float.
"""
import requests
from utils.config import FMP_API_KEY

FMP_BASE_URL = "https://financialmodelingprep.com/api/v3"


def _get_from_fmp(endpoint: str, params: dict) -> dict:
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
    result = {
        "float": None,
        "short_interest": None,
        "short_ratio": None,
        "status": "UNAVAILABLE",
        "source": "none",
    }

    if not FMP_API_KEY:
        return result

    try:
        float_data = _get_from_fmp("float-shares", {"symbol": ticker})
        if float_data:
            float_val = float_data.get("floatShares")
            if float_val and float_val > 0:
                result["float"] = float(float_val)
                result["status"] = "SUCCESS"
                result["source"] = "fmp_float"

        short_data = _get_from_fmp("short-interest", {"symbol": ticker})
        if short_data:
            short_pct = short_data.get("shortPercent")
            if short_pct is not None:
                result["short_interest"] = float(short_pct)
                result["short_ratio"] = float(short_data.get("shortRatio", 0))
                result["status"] = "SUCCESS"
                result["source"] = "fmp_both"

    except Exception as e:
        print(f"[Float] Error for {ticker}: {e}")

    return result