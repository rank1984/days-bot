"""
DAYS-BOT V5.0.5.2.4 – Float Analyzer
yfinance primary (FMP gated behind FMP_ENABLED flag)

FIXES:
- FMP calls gated (Free tier is dead: shares-float = 402, quota = 429)
- Short-interest query removed (404 on stable endpoint, wasted quota)
- yfinance .info timing logged (known slow: 1-3s/call; can return {} for micro-caps)
- Returns elapsed_ms + reason so Discovery can track per-source health
"""
import time
import requests
from utils.config import FMP_API_KEY, FMP_ENABLED

FMP_STABLE_URL = "https://financialmodelingprep.com/stable"


def _log(msg: str):
    print(f"[Float] {msg}")


def _get_from_fmp(endpoint: str, params: dict) -> dict:
    """Call FMP stable API. Returns dict or {}."""
    if not FMP_ENABLED:
        return {}
    if not FMP_API_KEY:
        _log("FMP_API_KEY missing – skipping FMP call")
        return {}
    try:
        url = f"{FMP_STABLE_URL}/{endpoint}"
        params["apikey"] = FMP_API_KEY
        resp = requests.get(url, params=params, timeout=10)
        body_preview = resp.text[:200] if resp.text else "<empty>"
        _log(f"FMP GET {endpoint} | status={resp.status_code} | body={body_preview}")
        if resp.status_code != 200:
            return {}
        data = resp.json()
        if not data:
            return {}
        if isinstance(data, list):
            return data[0] if data else {}
        return data
    except Exception as e:
        _log(f"FMP EXCEPTION on {endpoint}: {type(e).__name__}: {e}")
        return {}


def _get_float_yfinance(ticker: str) -> dict:
    """
    yfinance .info — known slow (1-3s) and may return {} or None for micro-caps.
    Returns:
        {
            "float": int | None,
            "source": "yfinance",
            "elapsed_ms": int,
            "reason": "OK" | "NO_KEY" | "EXCEPTION" | "EMPTY_INFO"
        }
    """
    t0 = time.time()
    try:
        import yfinance as yf
        info = yf.Ticker(ticker).info or {}
        elapsed_ms = int((time.time() - t0) * 1000)

        if not info:
            _log(f"{ticker}: yfinance EMPTY_INFO | {elapsed_ms}ms")
            return {
                "float": None,
                "source": "yfinance",
                "elapsed_ms": elapsed_ms,
                "reason": "EMPTY_INFO",
            }

        float_shares = info.get("floatShares")
        if float_shares and float_shares > 0:
            _log(f"{ticker}: yfinance OK | float={int(float_shares):,} | {elapsed_ms}ms")
            return {
                "float": int(float_shares),
                "source": "yfinance",
                "elapsed_ms": elapsed_ms,
                "reason": "OK",
            }

        _log(f"{ticker}: yfinance NO_KEY | keys={len(info)} | {elapsed_ms}ms")
        return {
            "float": None,
            "source": "yfinance",
            "elapsed_ms": elapsed_ms,
            "reason": "NO_KEY",
        }

    except Exception as e:
        elapsed_ms = int((time.time() - t0) * 1000)
        _log(f"{ticker}: yfinance EXCEPTION {type(e).__name__} | {elapsed_ms}ms")
        return {
            "float": None,
            "source": "yfinance",
            "elapsed_ms": elapsed_ms,
            "reason": "EXCEPTION",
        }


def get_float_and_short(ticker: str) -> dict:
    """
    Unified float fetch.
    Priority:
      1. FMP (only if FMP_ENABLED=True)
      2. yfinance fallback / primary
    Returns dict with: float, short_interest, short_ratio, status, source, elapsed_ms, reason
    """
    result = {
        "float": None,
        "short_interest": None,   # reserved; not fetched (FMP stable has no free endpoint)
        "short_ratio": None,      # reserved
        "status": "UNAVAILABLE",
        "source": "none",
        "elapsed_ms": 0,
        "reason": None,
    }

    # ================================================================
    # 1. FMP (only if enabled + key present)
    # ================================================================
    if FMP_ENABLED and FMP_API_KEY:
        float_data = _get_from_fmp("shares-float", {"symbol": ticker})
        if float_data:
            float_val = float_data.get("floatShares")
            if float_val and float_val > 0:
                result["float"] = float(float_val)
                result["status"] = "SUCCESS_FMP"
                result["source"] = "fmp"
                result["reason"] = "OK"
                _log(f"{ticker}: FMP float OK = {float_val:,.0f}")
                return result

    # ================================================================
    # 2. yfinance (primary while FMP disabled)
    # ================================================================
    yf_result = _get_float_yfinance(ticker)
    result["elapsed_ms"] = yf_result.get("elapsed_ms", 0)
    result["reason"] = yf_result.get("reason")

    if yf_result.get("float"):
        result["float"] = yf_result["float"]
        result["status"] = "SUCCESS_YFINANCE"
        result["source"] = "yfinance"
    else:
        result["status"] = "UNAVAILABLE"
        result["source"] = "yfinance"

    return result
