"""
DAYS-BOT V5.0.5.2.2 – Float Analyzer (FMP Stable + Fallback)
FIXES:
- Migrated from deprecated /api/v3/float-shares to /stable/shares-float
- Added detailed logging (status, body, endpoint) for diagnosis
- Added yfinance fallback when FMP returns nothing
- Tracks float_source so DB can distinguish FMP vs yfinance
"""
import os
import requests
from utils.config import FMP_API_KEY

FMP_STABLE_URL = "https://financialmodelingprep.com/stable"


def _log(msg: str):
    print(f"[Float] {msg}")


def _get_from_fmp(endpoint: str, params: dict) -> dict:
    """
    Call FMP stable API. Returns dict or {}.
    Logs status_code and body (truncated) for every call.
    """
    if not FMP_API_KEY:
        _log("FMP_API_KEY missing – skipping FMP call")
        return {}

    try:
        url = f"{FMP_STABLE_URL}/{endpoint}"
        params["apikey"] = FMP_API_KEY
        resp = requests.get(url, params=params, timeout=10)

        # Diagnostic log
        body_preview = resp.text[:300] if resp.text else "<empty>"
        _log(f"FMP GET {endpoint} | status={resp.status_code} | body={body_preview}")

        if resp.status_code != 200:
            return {}

        data = resp.json()
        if not data:
            return {}

        # FMP returns list for some endpoints, dict for others
        if isinstance(data, list):
            return data[0] if data else {}
        return data

    except Exception as e:
        _log(f"FMP EXCEPTION on {endpoint}: {type(e).__name__}: {e}")
        return {}


def _get_float_yfinance(ticker: str) -> dict:
    """
    Fallback: yfinance info dict.
    Returns {'float': int|None, 'source': 'yfinance'} or empty.
    """
    try:
        import yfinance as yf
        info = yf.Ticker(ticker).info or {}
        float_shares = info.get("floatShares")
        if float_shares and float_shares > 0:
            _log(f"yfinance fallback OK for {ticker}: float={float_shares:,}")
            return {"float": int(float_shares), "source": "yfinance"}
        _log(f"yfinance fallback: no floatShares for {ticker}")
        return {}
    except Exception as e:
        _log(f"yfinance fallback EXCEPTION for {ticker}: {type(e).__name__}: {e}")
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
        _log(f"{ticker}: FMP_API_KEY not set")
        return result

    # ================================================================
    # 1. FMP stable: shares-float
    #    Correct endpoint (v3 'float-shares' is dead)
    # ================================================================
    float_data = _get_from_fmp("shares-float", {"symbol": ticker})

    if float_data:
        float_val = float_data.get("floatShares")
        if float_val and float_val > 0:
            result["float"] = float(float_val)
            result["status"] = "SUCCESS"
            result["source"] = "fmp_float"
            _log(f"{ticker}: FMP float OK = {float_val:,.0f}")
        else:
            _log(f"{ticker}: FMP returned dict but no floatShares (keys={list(float_data.keys())})")
    else:
        _log(f"{ticker}: FMP shares-float returned empty")

    # ================================================================
    # 2. FMP stable: short-interest (optional, non-blocking)
    # ================================================================
    if result["float"] is not None:
        short_data = _get_from_fmp("short-interest", {"symbol": ticker})
        if short_data:
            short_pct = short_data.get("shortPercent")
            if short_pct is not None:
                result["short_interest"] = float(short_pct)
                result["short_ratio"] = float(short_data.get("shortRatio", 0))
                result["source"] = "fmp_both"
                _log(f"{ticker}: FMP short OK = {short_pct}%")

    # ================================================================
    # 3. Fallback: yfinance (only if FMP float missing)
    # ================================================================
    if result["float"] is None:
        _log(f"{ticker}: FMP float missing → trying yfinance fallback")
        yf_result = _get_float_yfinance(ticker)
        if yf_result.get("float"):
            result["float"] = yf_result["float"]
            result["status"] = "SUCCESS_FALLBACK"
            result["source"] = yf_result["source"]

    return result
